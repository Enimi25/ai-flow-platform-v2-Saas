
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import hashlib
import hmac
import base64
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import secrets
import urllib.parse
import urllib.error
import urllib.request
import uuid
import time

import psycopg2
from psycopg2.extras import RealDictCursor
import stripe
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"


def _is_production_runtime() -> bool:
    env_name = (
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or os.getenv("FASTAPI_ENV")
        or os.getenv("ENVIRONMENT")
        or ""
    ).strip().lower()
    if env_name in {"prod", "production"}:
        return True
    return any(
        (os.getenv(name) or "").strip()
        for name in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_HOSTNAME")
    )


def _load_secret_key() -> str:
    secret_key = (os.getenv("SECRET_KEY") or "").strip()
    if secret_key:
        return secret_key

    legacy_session_secret = (os.getenv("SESSION_SECRET") or "").strip()
    if legacy_session_secret:
        print("WARNING: SECRET_KEY is missing; using legacy SESSION_SECRET. Set SECRET_KEY on Render.")
        return legacy_session_secret

    if _is_production_runtime():
        raise RuntimeError("SECRET_KEY must be set in production for stable signed sessions.")

    print("WARNING: SECRET_KEY is missing; using local development fallback secret.")
    return "dev-secret-change-this"


_secret_key = _load_secret_key()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=_secret_key,
    session_cookie="ai_flow_session",
    # Keep an authenticated browser session for 30 days instead of Starlette's
    # short default, so users are not unexpectedly redirected to login.
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=True,
)


@app.middleware("http")
async def meta_oauth_callback_400_redirect(request: Request, call_next):
    if request.url.path != "/api/meta/callback":
        return await call_next(request)

    state = request.query_params.get("state", "")
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()[:12] if state else ""

    try:
        response = await call_next(request)
    except Exception as e:
        if getattr(e, "status_code", None) == 400:
            print(
                "META CALLBACK 400 SAFETY REDIRECT:",
                {"source": "exception", "state_hash": state_hash, "error_type": type(e).__name__},
            )
            return RedirectResponse(url=META_OAUTH_INVALID_STATE_REDIRECT, status_code=302)
        raise

    if response.status_code == 400:
        print(
            "META CALLBACK 400 SAFETY REDIRECT:",
            {"source": "response", "state_hash": state_hash},
        )
        return RedirectResponse(url=META_OAUTH_INVALID_STATE_REDIRECT, status_code=302)

    return response

# =========================================================
# AUTH / RBAC HELPERS
# =========================================================

ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_COMPANY_ADMIN = "company_admin"
ROLE_EMPLOYEE = "employee"
ROLE_CLIENT = "client"
FIXED_PLATFORM_ADMIN_EMAILS = (
    "baskinltd@gmail.com",
    "baskinltd@yahoo.com",
)
PLATFORM_COMPANY_PROFILE = {
    "companyName": "Baskin Ltd",
    "country": "Singapore",
    "address": "1 Raffles Place, Singapore 048616 (temporary mailing address)",
    "supportEmail": "baskinltd@gmail.com",
    "backupEmail": "baskinltd@yahoo.com",
    "phone": "+972 55 966 5585",
    "whatsapp": "+972 55 966 5585",
    "registrationStatus": "Registration details pending verification",
    "registrationNumber": "Not configured",
}

USER_STATUS_ACTIVE = "active"
USER_STATUS_INVITED = "invited"
USER_STATUS_SUSPENDED = "suspended"


def now_utc_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def hash_password(password: str, iterations: int = 200_000) -> str:
    password = (password or "").strip()
    if not password:
        return ""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return f"pbkdf2_sha256${iterations}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    password = (password or "").strip()
    stored = (stored or "").strip()
    if not password or not stored:
        return False

    # New format: pbkdf2_sha256$iterations$salt$hash
    if stored.startswith("pbkdf2_sha256$"):
        try:
            parts = stored.split("$")
            if len(parts) != 4:
                return False
            iterations = int(parts[1])
            salt = _b64d(parts[2])
            expected = _b64d(parts[3])
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
            return secrets.compare_digest(dk, expected)
        except Exception:
            return False

    # Legacy format: sha256 hex (64 chars)
    if len(stored) == 64:
        try:
            int(stored, 16)
        except Exception:
            return False
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, stored)

    return False


def get_session_user(request: Request) -> dict | None:
    sess = getattr(request, "session", None)
    if sess and sess.get("user_id"):
        return {
            "user_id": sess.get("user_id"),
            "email": sess.get("email") or "",
            "role": sess.get("role") or "",
            "company_id": sess.get("company_id") or "",
        }

    # The original app relied only on Starlette's signed session cookie.  If the
    # signing secret ever changes during a deploy, every user looks logged out.
    # Fall back to a database-backed, HttpOnly remember token instead.
    token = (request.cookies.get("ai_flow_remember") or "").strip()
    if not token:
        return None
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.role, u.company_id
                FROM v2_auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                  AND s.expires_at > %s
                  AND s.revoked_at = ''
                  AND COALESCE(u.status, 'active') = 'active'
                LIMIT 1
                """,
                (hashlib.sha256(token.encode("utf-8")).hexdigest(), now_utc_iso()),
            )
            user = cur.fetchone()
            if not user:
                return None
            return {
                "user_id": user.get("id"),
                "email": user.get("email") or "",
                "role": user.get("role") or "",
                "company_id": user.get("company_id") or "",
            }
    except Exception as e:
        print("PERSISTENT SESSION LOOKUP ERROR:", str(e))
        return None
    finally:
        conn.close()


def require_login(request: Request) -> dict | None:
    user = get_session_user(request)
    if not user:
        return None
    return user


def is_role(user: dict, *roles: str) -> bool:
    return bool(user) and (user.get("role") in set(roles))


def json_error(message: str, status_code: int = 400):
    return JSONResponse({"error": message}, status_code=status_code)


def _company_exists_and_active(conn, company_id: str) -> bool:
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT status FROM companies WHERE company_id = %s",
                (company_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            status = (row.get("status") or "active").strip() or "active"
            return status == "active"
    except Exception:
        return False


def resolve_company_id(
    request: Request,
    provided_company_id: str,
    *,
    allow_public: bool = False,
    allow_platform_admin_any: bool = True,
):
    """
    Enforces that non-platform users can only act on their own company_id.
    For public callers (widget), allow_public=True validates company exists and is active.
    Returns: (company_id, user_dict_or_none, error_response_or_none)
    """
    provided_company_id = (provided_company_id or "").strip()
    user = get_session_user(request)

    if user:
        role = (user.get("role") or "").strip()
        user_company_id = (user.get("company_id") or "").strip()

        if role == ROLE_PLATFORM_ADMIN and allow_platform_admin_any:
            if not provided_company_id:
                return "", user, json_error("Missing companyId", 400)
            return provided_company_id, user, None

        if not user_company_id:
            return "", user, json_error("User has no company access", 403)

        if provided_company_id and provided_company_id != user_company_id:
            return "", user, json_error("Forbidden company access", 403)

        return user_company_id, user, None

    if not allow_public:
        return "", None, json_error("Not logged in", 401)

    if not provided_company_id:
        return "", None, json_error("Missing companyId", 400)

    conn = get_db_connection()
    if not conn:
        return "", None, json_error("Database error", 500)
    try:
        if not _company_exists_and_active(conn, provided_company_id):
            return "", None, json_error("Unknown companyId", 404)
        return provided_company_id, None, None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def guard_page(request: Request, *roles: str):
    """
    Server-side guard for static app pages. Keeps existing client-side localStorage checks,
    but prevents direct access without a valid session cookie.
    """
    user = require_login(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if roles and not is_role(user, *roles):
        email = (user.get("email") or "").strip()
        role = (user.get("role") or "").strip()
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI FLOW - Access Denied</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{
      min-height:100vh;
      background:
        radial-gradient(980px 720px at 14% -10%, rgba(184,255,122,0.18), transparent 58%),
        radial-gradient(900px 700px at 110% 10%, rgba(65,220,255,0.14), transparent 55%),
        radial-gradient(760px 640px at 70% 120%, rgba(139,92,246,0.10), transparent 58%),
        #061923;
      color:#f7fbff;
      font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,"Noto Sans","Helvetica Neue",sans-serif;
      display:flex;align-items:center;justify-content:center;padding:24px 16px;
    }}
    .box{{
      width:520px;max-width:100%;
      background:rgba(255,255,255,0.06);
      border:1px solid rgba(255,255,255,0.12);
      border-radius:32px;
      padding:28px;
      box-shadow:0 30px 80px rgba(0,0,0,.16);
      backdrop-filter: blur(18px);
    }}
    .logo{{font-size:32px;font-weight:950;margin-bottom:8px}}
    .logo span{{color:#b8ff7a}}
    .sub{{color:#9fb7c3;line-height:1.5;margin-top:10px}}
    .pill{{display:inline-block;margin-top:12px;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);font-size:12px;font-weight:950;color:#d7e6eb}}
    .row{{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}}
    a.btn{{text-decoration:none;display:inline-block;padding:12px 14px;border-radius:14px;font-weight:950;background:linear-gradient(135deg, rgba(184,255,122,0.98) 0%, rgba(65,220,255,0.72) 100%);color:#071820;box-shadow:0 22px 70px rgba(184,255,122,0.14)}}
    a.btn2{{text-decoration:none;display:inline-block;padding:12px 14px;border-radius:14px;font-weight:950;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:#f7fbff}}
  </style>
</head>
<body>
  <div class="box">
    <div class="logo">AI <span>FLOW</span></div>
    <div class="sub">Access denied for this page.</div>
    <div class="sub" style="margin-top:8px;">Signed in as: <strong>{email or "unknown"}</strong></div>
    <div class="pill">Role: {role or "unknown"}</div>
    <div class="row">
      <a class="btn" href="/dashboard">Go to Dashboard</a>
      <a class="btn2" href="/settings">Settings</a>
    </div>
  </div>
</body>
</html>
"""
        return HTMLResponse(html, status_code=403)
    return None


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("DATABASE_URL is missing")
        return None

    try:
        return psycopg2.connect(database_url, sslmode="require")
    except Exception as e:
        print("DATABASE CONNECTION ERROR:", str(e))
        return None


def init_db():
    conn = get_db_connection()

    if not conn:
        return False

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    company_id TEXT PRIMARY KEY,
                    company_name TEXT DEFAULT '',
                    owner_email TEXT DEFAULT '',
                    plan TEXT DEFAULT 'Growth Studio',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            # Backward-compatible migrations for older DBs (CREATE TABLE IF NOT EXISTS won't add columns).
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS company_name TEXT DEFAULT ''")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_email TEXT DEFAULT ''")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'Growth Studio'")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_at TEXT DEFAULT ''")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'unpaid'")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_user_id INTEGER")
            cur.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS updated_at TEXT DEFAULT ''")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    password_hash TEXT DEFAULT '',
                    role TEXT DEFAULT 'client',
                    company_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            # Backward-compatible migrations for older DBs.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT DEFAULT ''")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'client'")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id TEXT DEFAULT ''")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TEXT DEFAULT ''")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TEXT DEFAULT ''")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data TEXT DEFAULT ''")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_company_id ON users(company_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

            # Durable browser login tokens. These survive a harmless Render
            # restart or signed-cookie secret rotation; only a SHA-256 digest is
            # retained in the database.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_auth_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_auth_sessions_token_hash ON v2_auth_sessions(token_hash)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_auth_sessions_user_id ON v2_auth_sessions(user_id)")

            # Invite system (MVP): company admins can invite employees/clients.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_invites (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TEXT DEFAULT '',
                    accepted_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_invites_company_id ON v2_invites(company_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_invites_email ON v2_invites(email)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_leads (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    status TEXT DEFAULT 'new',
                    message TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_content_posts (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    post_type TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    created_by TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_content_campaigns (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    campaign_name TEXT DEFAULT '',
                    goal TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_bookings (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    client_name TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    meeting_time TEXT DEFAULT '',
                    meeting_link TEXT DEFAULT '',
                    status TEXT DEFAULT 'booked',
                    created_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("ALTER TABLE v2_bookings ADD COLUMN IF NOT EXISTS service TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_bookings ADD COLUMN IF NOT EXISTS address TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_bookings ADD COLUMN IF NOT EXISTS calendar_event_id TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_bookings ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'awaiting_payment'")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_google_calendar_tokens (
                    company_id TEXT PRIMARY KEY,
                    token_json TEXT NOT NULL DEFAULT '{}',
                    calendar_id TEXT DEFAULT 'primary',
                    timezone TEXT DEFAULT 'Asia/Bangkok',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_social_accounts (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    status TEXT DEFAULT 'not_connected',
                    account_name TEXT DEFAULT '',
                    account_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            # Store OAuth access tokens separately so we never expose tokens via /social-data.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_social_tokens (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    provider TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    account_id TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    token_expires_at TEXT DEFAULT '',
                    refresh_token TEXT DEFAULT '',
                    refresh_expires_at TEXT DEFAULT '',
                    scope TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            # Backward-compatible migrations for older DBs.
            cur.execute("ALTER TABLE v2_social_tokens ADD COLUMN IF NOT EXISTS refresh_token TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_social_tokens ADD COLUMN IF NOT EXISTS refresh_expires_at TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_social_tokens ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT ''")

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_social_tokens_unique
                ON v2_social_tokens (company_id, provider, platform, account_id);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_instagram_publish_jobs (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    provider TEXT DEFAULT 'instagram',
                    post_type TEXT DEFAULT '',
                    ig_user_id TEXT DEFAULT '',
                    page_id TEXT DEFAULT '',
                    media_urls TEXT DEFAULT '[]',
                    caption TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    creation_id TEXT DEFAULT '',
                    media_id TEXT DEFAULT '',
                    permalink TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    published_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_instagram_publish_jobs_company ON v2_instagram_publish_jobs(company_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_instagram_publish_jobs_status ON v2_instagram_publish_jobs(status)")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_ai_media_jobs (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    media_type TEXT DEFAULT '',
                    prompt TEXT DEFAULT '',
                    style TEXT DEFAULT '',
                    format TEXT DEFAULT '',
                    provider TEXT DEFAULT '',
                    provider_job_id TEXT DEFAULT '',
                    status TEXT DEFAULT 'queued',
                    public_urls TEXT DEFAULT '[]',
                    preview_urls TEXT DEFAULT '[]',
                    caption TEXT DEFAULT '',
                    reel_script TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("ALTER TABLE v2_ai_media_jobs ADD COLUMN IF NOT EXISTS provider_job_id TEXT DEFAULT ''")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_ai_media_jobs_company ON v2_ai_media_jobs(company_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_v2_ai_media_jobs_status ON v2_ai_media_jobs(status)")

            # Short-lived OAuth state store for Meta connect flow.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_meta_oauth_states (
                    state TEXT PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    consumed_at TEXT DEFAULT '',
                    success TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )
            cur.execute("ALTER TABLE v2_meta_oauth_states ADD COLUMN IF NOT EXISTS consumed_at TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_meta_oauth_states ADD COLUMN IF NOT EXISTS success TEXT DEFAULT ''")
            cur.execute("ALTER TABLE v2_meta_oauth_states ADD COLUMN IF NOT EXISTS updated_at TEXT DEFAULT ''")

            # Short-lived OAuth state store for TikTok connect flow.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_tiktok_oauth_states (
                    state TEXT PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_tiktok_accounts (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    tiktok_open_id TEXT DEFAULT '',
                    username TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    refresh_token TEXT DEFAULT '',
                    expires_in TEXT DEFAULT '',
                    status TEXT DEFAULT 'connected',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_tiktok_accounts_company
                ON v2_tiktok_accounts (company_id);
                """
            )

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_tiktok_accounts_unique
                ON v2_tiktok_accounts (company_id, tiktok_open_id);
                """
            )

            # Social content automation drafts (daily).
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_social_content_drafts (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    content_date TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    draft_type TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    caption TEXT DEFAULT '',
                    hook TEXT DEFAULT '',
                    hashtags TEXT DEFAULT '',
                    visual_idea TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    publish_message TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_social_content_drafts_company_date
                ON v2_social_content_drafts (company_id, content_date);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_social_automation_settings (
                    company_id TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT FALSE,
                    daily_content_units INTEGER DEFAULT 1,
                    timezone TEXT DEFAULT 'UTC',
                    publish_mode TEXT DEFAULT 'approval',
                    posting_times TEXT DEFAULT '["09:00","14:00","19:00"]',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_social_publish_log (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    content_kind TEXT DEFAULT '',
                    external_id TEXT DEFAULT '',
                    permalink TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    scheduled_for TEXT DEFAULT '',
                    published_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_social_publish_log_company
                ON v2_social_publish_log (company_id, created_at DESC);
                """
            )

            # Stripe payment records (MVP).
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_payments (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    project_name TEXT DEFAULT '',
                    stripe_session_id TEXT DEFAULT '',
                    customer_email TEXT DEFAULT '',
                    amount INTEGER DEFAULT 0,
                    currency TEXT DEFAULT '',
                    status TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_payments_session
                ON v2_payments (stripe_session_id);
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_v2_payments_company
                ON v2_payments (company_id);
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_ai_replies (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    customer_name TEXT DEFAULT '',
                    customer_message TEXT DEFAULT '',
                    ai_reply TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    source TEXT DEFAULT 'Website',
                    created_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_company_settings (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    industry TEXT DEFAULT '',
                    website TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    assistant_name TEXT DEFAULT 'AI FLOW Assistant',
                    ai_tone TEXT DEFAULT 'Friendly',
                    ai_goal TEXT DEFAULT 'Capture leads',
                    business_description TEXT DEFAULT '',
                    welcome_message TEXT DEFAULT '',
                    lead_question TEXT DEFAULT '',
                    email_notifications TEXT DEFAULT 'Enabled',
                    lead_alerts TEXT DEFAULT 'Enabled',
                    weekly_reports TEXT DEFAULT 'Enabled',
                    updated_at TEXT DEFAULT ''
                );
                """
            )

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_v2_company_settings_company_id
                ON v2_company_settings (company_id);
                """
            )

        conn.commit()
        print("DATABASE READY")
        return True

    except Exception as e:
        print("DATABASE INIT ERROR:", str(e))
        return False

    finally:
        conn.close()


@app.on_event("startup")
def startup_event():
    init_db()
    bootstrap_platform_admin()
    bootstrap_platform_company()
    _log_social_env_debug()


def bootstrap_platform_admin():
    """
    Guarantees one durable platform owner after every database recreation.
    The owner can always sign in with Google. PLATFORM_ADMIN_PASSWORD is an
    optional Render secret that also enables password login.
    """
    password = (os.getenv("PLATFORM_ADMIN_PASSWORD") or "").strip()

    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # A project has exactly one platform owner. Existing business
            # owners keep access to their own companies, but not the platform.
            cur.execute(
                """
                UPDATE users
                SET role = CASE WHEN COALESCE(company_id, '') <> '' THEN %s ELSE %s END,
                    updated_at = %s
                WHERE LOWER(email) NOT IN (%s, %s)
                  AND role IN (%s, 'admin')
                """,
                (
                    ROLE_COMPANY_ADMIN,
                    ROLE_CLIENT,
                    now_utc_iso(),
                    FIXED_PLATFORM_ADMIN_EMAILS[0],
                    FIXED_PLATFORM_ADMIN_EMAILS[1],
                    ROLE_PLATFORM_ADMIN,
                ),
            )
            for email in FIXED_PLATFORM_ADMIN_EMAILS:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                existing = cur.fetchone()
                created_at = now_utc_iso()
                pw = hash_password(password) if password else ""

                if existing:
                    updates = ["role = %s", "company_id = %s", "status = %s", "updated_at = %s"]
                    values = [ROLE_PLATFORM_ADMIN, "", USER_STATUS_ACTIVE, created_at]
                    if pw:
                        updates.extend(["password = %s", "password_hash = %s"])
                        values.extend([pw, pw])
                    values.append(int(existing["id"]))
                    cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", tuple(values))
                else:
                    login_hash = pw or hash_password(secrets.token_urlsafe(64))
                    cur.execute(
                        """
                        INSERT INTO users (email, password, password_hash, role, company_id, status, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (email, login_hash, login_hash, ROLE_PLATFORM_ADMIN, "", USER_STATUS_ACTIVE, created_at, created_at),
                    )

        conn.commit()
        print(f"PLATFORM_ADMIN_BOOTSTRAP_OK emails={','.join(FIXED_PLATFORM_ADMIN_EMAILS)}")
    except Exception as e:
        print("BOOTSTRAP PLATFORM ADMIN ERROR:", str(e))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def bootstrap_platform_company():
    """Keep the platform's own AI FLOW workspace available after DB recreation.

    Social OAuth tokens still require an intentional reconnect, but the stable
    workspace ID prevents platform admins from landing in an unusable dashboard
    with no company to select.
    """
    company_id = (os.getenv("PLATFORM_COMPANY_ID") or "ai-flow").strip() or "ai-flow"
    company_name = (os.getenv("PLATFORM_COMPANY_NAME") or "AI FLOW").strip() or "AI FLOW"
    owner_email = FIXED_PLATFORM_ADMIN_EMAILS[0]
    timestamp = now_utc_iso()

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO companies (
                    company_id, company_name, owner_email, plan, status,
                    payment_status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id) DO UPDATE SET
                    company_name = CASE
                        WHEN COALESCE(companies.company_name, '') = '' THEN EXCLUDED.company_name
                        ELSE companies.company_name
                    END,
                    owner_email = CASE
                        WHEN COALESCE(companies.owner_email, '') = '' THEN EXCLUDED.owner_email
                        ELSE companies.owner_email
                    END,
                    status = 'active',
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    company_id,
                    company_name,
                    owner_email,
                    "Growth Studio",
                    "active",
                    "unpaid",
                    timestamp,
                    timestamp,
                ),
            )
        conn.commit()
        print(f"PLATFORM_COMPANY_BOOTSTRAP_OK company_id={company_id}")
    except Exception as e:
        print("BOOTSTRAP PLATFORM COMPANY ERROR:", str(e))
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =========================================================
# STATIC PAGES
# =========================================================

def page_response(filename: str, media_type: str | None = None, request: Request | None = None):
    """Serve a page without allowing stale browser storage to look like a logout.

    The legacy dashboard pages still read identity fields from localStorage during
    startup.  Authentication itself is cookie based, so re-hydrate those UI-only
    fields from the verified server session before the page's own scripts run.
    """
    headers = {"Cache-Control": "no-store, max-age=0"}
    user = get_session_user(request) if request else None
    if filename.endswith(".html"):
        brand = (
            '<link rel="icon" type="image/png" href="/media/brand/ai-flow-app-icon.png">'
            '<style>.logo{display:flex!important;align-items:center;gap:9px}'
            '.ai-flow-brand-icon{width:34px;height:34px;border-radius:10px;object-fit:cover;flex:none;'
            'box-shadow:0 8px 24px rgba(65,220,255,.18)}'
            '.brand-signature{position:fixed;left:16px;bottom:12px;z-index:70;display:flex;align-items:center;gap:7px;'
            'padding:6px 9px;border:1px solid rgba(255,255,255,.12);border-radius:10px;'
            'background:rgba(4,15,22,.82);backdrop-filter:blur(12px);color:#d7e6eb;'
            'font:800 10px/1 ui-sans-serif,system-ui;text-decoration:none}'
            '.brand-signature img{width:22px;height:22px;border-radius:7px;object-fit:cover}'
            '.page-brand{position:fixed;top:16px;left:18px;z-index:80;display:flex;align-items:center;gap:9px;'
            'color:#f3f7f5;text-decoration:none;font:900 15px/1 ui-sans-serif,system-ui;letter-spacing:-.02em}'
            '.page-brand img{width:34px;height:34px;border-radius:10px;object-fit:cover}'
            '@media(max-width:900px){.brand-signature{position:static;width:max-content;margin:18px auto}}'
            '</style>'
            '<script>document.addEventListener("DOMContentLoaded",function(){'
            'document.querySelectorAll(".logo").forEach(function(logo){if(logo.querySelector(".ai-flow-brand-icon"))return;'
            'var img=document.createElement("img");img.src="/media/brand/ai-flow-app-icon.png";'
            'img.alt="AI FLOW";img.className="ai-flow-brand-icon";logo.prepend(img);});'
            'var menu=document.querySelector(".menu");if(menu){['
            '["/dashboard","Overview"],["/leads-page","Leads"],["/ai-replies","Conversations"],'
            '["/calendar","Calendar"],["/content-factory","Content"],["/social-accounts","Connections"],'
            '["/analytics","Analytics"],["/billing","Billing"],["/settings","Settings"]'
            '].forEach(function(item){var link=menu.querySelector(`a[href="${item[0]}"]`);'
            'if(link){link.textContent=item[1];menu.appendChild(link);}});}'
            'if(!document.querySelector(".logo")&&!document.querySelector(".page-brand")){var p=document.createElement("a");'
            'p.href="/dashboard";p.className="page-brand";p.innerHTML=`<img src="/media/brand/ai-flow-app-icon.png" alt="AI FLOW">AI FLOW`;'
            'document.body.appendChild(p);}'
            'if(!document.querySelector(".brand-signature")){var a=document.createElement("a");'
            'a.href="/";a.className="brand-signature";a.setAttribute("aria-label","AI FLOW home");'
            'a.innerHTML=`<img src="/media/brand/ai-flow-app-icon.png" alt="">Powered by AI FLOW`;'
            'document.body.appendChild(a);}});</script>'
        )
        html = (BASE_DIR / filename).read_text(encoding="utf-8")
        html = html.replace("</head>", brand + "</head>", 1)

        if not user:
            return HTMLResponse(html, headers=headers)

        identity = json.dumps(
            {
                "email": user.get("email") or "",
                "role": user.get("role") or "",
                "companyId": user.get("company_id") or "",
            }
        ).replace("</", "<\\/")
        bootstrap = (
            "<style>.workspace-identity{margin:-10px 8px 18px;padding:9px 10px;"
            "border:1px solid #26332e;border-radius:8px;background:#11191e;"
            "font:700 11px/1.35 ui-sans-serif,system-ui;color:#aebbb5;word-break:break-word}"
            ".workspace-identity strong{display:block;color:#f3f7f5;font-size:12px;margin-bottom:2px}"
            ".workspace-identity.admin strong{color:#dfffbd}</style>"
            "<script>(function(){try{const u="
            + identity
            + ";if(u.email)localStorage.setItem('ai_flow_email',u.email);"
            + "if(u.role)localStorage.setItem('ai_flow_role',u.role);"
            + "if(u.companyId)localStorage.setItem('ai_flow_company_id',u.companyId);"
            + "document.addEventListener('DOMContentLoaded',function(){"
            + "const logo=document.querySelector('.sidebar .logo');if(!logo)return;"
            + "const box=document.createElement('div');box.className='workspace-identity'+(u.role==='platform_admin'?' admin':'');"
            + "if(u.role==='platform_admin'){box.innerHTML='<strong>Platform Admin</strong>'+String(u.email||'');}"
            + "else{const role=u.role==='company_admin'?'Business Owner':(u.role==='employee'?'Team Member':'Client');"
            + "box.innerHTML='<strong>'+role+'</strong>Client ID: '+String(u.companyId||'Not assigned');}"
            + "logo.insertAdjacentElement('afterend',box);});"
            + "}catch(e){}})();</script>"
        )
        assistant = '<script src="/app-assistant.js" defer></script>'
        return HTMLResponse(html.replace("</head>", bootstrap + assistant + "</head>", 1), headers=headers)
    return FileResponse(BASE_DIR / filename, media_type=media_type, headers=headers)

@app.get("/media/{path:path}")
def media_response(path: str):
    base = MEDIA_DIR.resolve()
    target = (MEDIA_DIR / (path or "")).resolve()

    # Disallow traversal and only serve files under MEDIA_DIR.
    if base != target and base not in target.parents:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if not target.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    suffix = target.suffix.lower()
    media_type = None
    if suffix == ".png":
        media_type = "image/png"
    elif suffix in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif suffix == ".webp":
        media_type = "image/webp"
    elif suffix == ".mp4":
        media_type = "video/mp4"

    return FileResponse(
        target,
        media_type=media_type,
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/")
def home():
    return page_response("index.html")


@app.get("/tiktok7cljl2bNmf2SJYQypLqNMYFTXdptPPPd.txt")
def tiktok_site_verification():
    return FileResponse(
        BASE_DIR / "tiktok7cljl2bNmf2SJYQypLqNMYFTXdptPPPd.txt",
        media_type="text/plain",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/login")
def login_page():
    return page_response("login.html")


@app.get("/dashboard")
def dashboard_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("dashboard.html", request=request)


@app.get("/leads-page")
def leads_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("leads.html", request=request)


@app.get("/content-factory")
@app.get("/content")
def content_factory_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("content.html", request=request)

@app.get("/settings")
def settings_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN)
    if guard:
        return guard
    return page_response("settings.html", request=request)

@app.get("/social-accounts")
def social_accounts_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN)
    if guard:
        return guard
    return page_response("social.html", request=request)


@app.get("/workspace-compact.css")
def workspace_compact_styles():
    return FileResponse(
        BASE_DIR / "workspace-compact.css",
        media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/ai-replies")
def ai_replies_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("replies.html", request=request)

@app.get("/billing")
def billing_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN)
    if guard:
        return guard
    return page_response("billing.html", request=request)

@app.get("/analytics")
def analytics_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("analytics.html", request=request)


@app.get("/calendar")
def calendar_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE)
    if guard:
        return guard
    return page_response("calendar.html", request=request)


@app.get("/admin")
def admin_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN)
    if guard:
        return guard
    return page_response("admin.html", request=request)

@app.get("/onboarding")
def onboarding_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN)
    if guard:
        return guard
    return page_response("onboarding.html", request=request)


@app.get("/team")
def team_page(request: Request):
    guard = guard_page(request, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN)
    if guard:
        return guard
    return page_response("team.html")


@app.get("/payment/success")
def payment_success_page():
    return page_response("payment_success.html")


@app.get("/payment/cancel")
def payment_cancel_page():
    return page_response("payment_cancel.html")

@app.get("/admin-data")
def admin_data(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    if not is_role(user, ROLE_PLATFORM_ADMIN):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM companies")
            total_companies = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM users")
            total_users = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM v2_leads")
            total_leads = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM v2_content_posts")
            total_posts = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM v2_bookings")
            total_bookings = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM v2_ai_replies")
            total_ai_replies = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM v2_social_accounts")
            total_social_accounts = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT *
                FROM companies
                ORDER BY created_at DESC NULLS LAST
                LIMIT 20
                """
            )
            recent_companies = cur.fetchall()

        return JSONResponse(
            {
                "success": True,
                "metrics": {
                    "total_companies": total_companies,
                    "total_users": total_users,
                    "total_leads": total_leads,
                    "total_posts": total_posts,
                    "total_bookings": total_bookings,
                    "total_ai_replies": total_ai_replies,
                    "total_social_accounts": total_social_accounts,
                },
                "recent_companies": recent_companies,
            }
        )

    except Exception as e:
        print("ADMIN DATA ERROR:", str(e))
        return JSONResponse({"error": "Admin data error"}, status_code=500)

    finally:
        conn.close()


@app.get("/widget.js")
def widget():
    return page_response("widget.js", media_type="application/javascript")


@app.get("/app-assistant.js")
def app_assistant_script():
    return FileResponse(
        BASE_DIR / "app-assistant.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/support/chat")
async def app_support_chat(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    data = await request.json()
    message = str(data.get("message") or "").strip()[:2000]
    page = str(data.get("page") or "").strip()[:120]
    if not message:
        return json_error("Enter a question", 400)

    fallback = (
        "I can help with AI FLOW setup, social channels, Google Calendar, "
        "bookings, payments, CRM, leads, and content publishing. For account-specific help, "
        "use Contact AI FLOW Support below."
    )
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        return JSONResponse({"success": True, "reply": fallback})
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AI FLOW product support inside an English-only SaaS dashboard. "
                        "Answer briefly and clearly. Help with Dashboard, Leads, Content Factory, "
                        "Social Accounts, Customer Conversations, Analytics, Google Calendar, "
                        "bookings, Stripe payments, CRM, Billing and Settings. Never invent connection "
                        "status or claim an action succeeded. Direct account-specific or unresolved "
                        "issues to the Contact AI FLOW Support button."
                    ),
                },
                {"role": "user", "content": f"Current page: {page}\nQuestion: {message}"},
            ],
            temperature=0.2,
            max_tokens=350,
        )
        reply = (completion.choices[0].message.content or "").strip() or fallback
        return JSONResponse({"success": True, "reply": reply})
    except Exception as e:
        print("APP SUPPORT CHAT ERROR:", type(e).__name__, str(e)[:200])
        return JSONResponse({"success": True, "reply": fallback})


@app.get("/privacy", response_class=HTMLResponse)
@app.get("/privacy.html", response_class=HTMLResponse)
def privacy_page():
    path = BASE_DIR / "privacy.html"
    if not path.exists():
        return HTMLResponse("<h1>Privacy Policy not found</h1>", status_code=404)

    return path.read_text(encoding="utf-8")


@app.get("/terms", response_class=HTMLResponse)
@app.get("/terms.html", response_class=HTMLResponse)
def terms_page():
    path = BASE_DIR / "terms.html"
    if not path.exists():
        return HTMLResponse("<h1>Terms not found</h1>", status_code=404)

    return path.read_text(encoding="utf-8")


@app.get("/data-deletion.html", response_class=HTMLResponse)
def data_deletion_page():
    path = BASE_DIR / "data-deletion.html"
    if not path.exists():
        return HTMLResponse("<h1>Data Deletion page not found</h1>", status_code=404)

    return path.read_text(encoding="utf-8")


# =========================================================
# AUTH
# =========================================================

@app.post("/register")
async def register(request: Request):
    data = await request.json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return JSONResponse(
            {"error": "Missing email or password"},
            status_code=400,
        )

    pw_hash = hash_password(password)
    if not pw_hash:
        return JSONResponse({"error": "Invalid password"}, status_code=400)

    # New signups create their own company workspace. Keep company_id=email for backward compatibility.
    company_id = email
    created_at = now_utc_iso()

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(
                """
                INSERT INTO companies (
                    company_id,
                    company_name,
                    owner_email,
                    plan,
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id) DO NOTHING
                """,
                (
                    company_id,
                    "New Client Company",
                    email,
                    "Growth Studio",
                    "active",
                    created_at,
                ),
            )

            cur.execute(
                """
                INSERT INTO users (
                    email,
                    password,
                    password_hash,
                    role,
                    company_id,
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    email,
                    pw_hash,
                    pw_hash,
                    ROLE_COMPANY_ADMIN,
                    company_id,
                    USER_STATUS_ACTIVE,
                    created_at,
                ),
            )
            user_row = cur.fetchone() or {}
            user_id = user_row.get("id")

            if user_id:
                cur.execute(
                    """
                    UPDATE companies
                    SET owner_user_id = %s,
                        updated_at = %s
                    WHERE company_id = %s
                    """,
                    (int(user_id), created_at, company_id),
                )

        conn.commit()

        return JSONResponse(
            {
                "success": True,
                "email": email,
                "companyId": company_id,
            }
        )

    except Exception as e:
        print("REGISTER ERROR:", str(e))

        return JSONResponse(
            {"error": "User already exists"},
            status_code=400,
        )

    finally:
        conn.close()


@app.post("/login-api")
async def login_api(request: Request):
    data = await request.json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (
                    email,
                ),
            )

            user = cur.fetchone()

            if not user:
                return JSONResponse(
                    {"error": "Invalid credentials"},
                    status_code=401,
                )

            # Status checks
            status = (user.get("status") or USER_STATUS_ACTIVE).strip() or USER_STATUS_ACTIVE
            if status == USER_STATUS_SUSPENDED:
                return JSONResponse({"error": "Account suspended"}, status_code=403)

            # Password check (supports legacy sha256 in users.password)
            stored_hash = (user.get("password_hash") or "").strip() or (user.get("password") or "").strip()
            if not verify_password(password, stored_hash):
                return JSONResponse({"error": "Invalid credentials"}, status_code=401)

            # If legacy SHA256 was used, upgrade to PBKDF2 on successful login.
            if not (user.get("password_hash") or "").strip() and (user.get("password") or "").strip():
                upgraded = hash_password(password)
                if upgraded:
                    try:
                        cur.execute(
                            """
                            UPDATE users
                            SET password_hash = %s,
                                password = %s,
                                updated_at = %s
                            WHERE id = %s
                            """,
                            (upgraded, upgraded, now_utc_iso(), int(user["id"])),
                        )
                        conn.commit()
                        user["password_hash"] = upgraded
                        user["password"] = upgraded
                    except Exception:
                        # Do not fail login on upgrade problems.
                        conn.rollback()

            role = (user.get("role") or ROLE_CLIENT).strip() or ROLE_CLIENT
            if role == "admin":
                role = ROLE_PLATFORM_ADMIN
            # Backward-compat: older signups used role="client" for the company owner.
            if role == ROLE_CLIENT and (user.get("company_id") or "").strip():
                role = ROLE_COMPANY_ADMIN
                try:
                    cur.execute(
                        "UPDATE users SET role = %s, updated_at = %s WHERE id = %s",
                        (ROLE_COMPANY_ADMIN, now_utc_iso(), int(user["id"])),
                    )
                    conn.commit()
                    user["role"] = ROLE_COMPANY_ADMIN
                except Exception:
                    conn.rollback()

            # The platform owner identity is fixed in code and cannot drift
            # when Render recreates the free database.
            if email in FIXED_PLATFORM_ADMIN_EMAILS and role != ROLE_PLATFORM_ADMIN:
                role = ROLE_PLATFORM_ADMIN
                try:
                    cur.execute(
                        "UPDATE users SET role = %s, company_id = %s, status = %s, updated_at = %s WHERE id = %s",
                        (ROLE_PLATFORM_ADMIN, "", USER_STATUS_ACTIVE, now_utc_iso(), int(user["id"])),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
            elif email not in FIXED_PLATFORM_ADMIN_EMAILS and role == ROLE_PLATFORM_ADMIN:
                role = ROLE_COMPANY_ADMIN if (user.get("company_id") or "").strip() else ROLE_CLIENT
                try:
                    cur.execute(
                        "UPDATE users SET role = %s, updated_at = %s WHERE id = %s",
                        (role, now_utc_iso(), int(user["id"])),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()

            company_id = (user.get("company_id") or "").strip()
            if role != ROLE_PLATFORM_ADMIN:
                if not company_id:
                    return JSONResponse({"error": "Account missing company access"}, status_code=403)
                if not _company_exists_and_active(conn, company_id):
                    return JSONResponse({"error": "Company suspended"}, status_code=403)

            # Session (server-side signed cookie)
            try:
                request.session.clear()
                request.session["user_id"] = int(user["id"])
                request.session["email"] = user.get("email") or ""
                request.session["role"] = role
                request.session["company_id"] = company_id
            except Exception as e:
                print("SESSION SET ERROR:", str(e))

            # Keep a durable login token in Postgres as a recovery path when a
            # signed session cookie becomes invalid after an infrastructure
            # restart. The browser receives only the random token; the database
            # stores its one-way hash.
            remember_token = secrets.token_urlsafe(48)
            remember_hash = hashlib.sha256(remember_token.encode("utf-8")).hexdigest()
            remember_expires = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
            try:
                cur.execute(
                    """
                    INSERT INTO v2_auth_sessions (user_id, token_hash, expires_at, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (int(user["id"]), remember_hash, remember_expires, now_utc_iso()),
                )
                cur.execute("DELETE FROM v2_auth_sessions WHERE expires_at <= %s", (now_utc_iso(),))
                conn.commit()
            except Exception as e:
                conn.rollback()
                print("PERSISTENT SESSION CREATE ERROR:", str(e))

            response = JSONResponse(
                {
                    "success": True,
                    "email": user["email"],
                    "role": role,
                    "companyId": company_id,
                    "userId": user.get("id"),
                }
            )
            response.set_cookie(
                key="ai_flow_remember",
                value=remember_token,
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
            )
            return response

    except Exception as e:
        print("LOGIN ERROR:", str(e))

        return JSONResponse(
            {"error": "Login failed"},
            status_code=500,
        )

    finally:
        conn.close()


@app.post("/logout-api")
async def logout_api(request: Request):
    token = (request.cookies.get("ai_flow_remember") or "").strip()
    if token:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE v2_auth_sessions SET revoked_at = %s WHERE token_hash = %s",
                        (now_utc_iso(), hashlib.sha256(token.encode("utf-8")).hexdigest()),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                conn.close()
    try:
        request.session.clear()
    except Exception:
        pass
    response = JSONResponse({"success": True})
    response.delete_cookie("ai_flow_remember", path="/")
    return response

@app.get("/api/me")
def api_me(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    active_company_id = ""
    try:
        active_company_id = (request.session.get("active_company_id") or "").strip()
    except Exception:
        active_company_id = ""
    return JSONResponse({"success": True, "user": user, "activeCompanyId": active_company_id})


@app.get("/api/profile/avatar")
def get_profile_avatar(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT avatar_data FROM users WHERE email = %s", ((user.get("email") or "").strip().lower(),))
            row = cur.fetchone() or {}
        return JSONResponse({"success": True, "avatar": row.get("avatar_data") or ""})
    finally:
        conn.close()


@app.post("/api/profile/avatar")
async def save_profile_avatar(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    data = await request.json()
    avatar = str(data.get("avatar") or "").strip()
    allowed = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
    if not avatar.startswith(allowed):
        return json_error("Use a PNG, JPEG, or WebP image", 400)
    if len(avatar) > 1_450_000:
        return json_error("Avatar must be smaller than 1 MB", 400)
    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET avatar_data = %s, updated_at = %s WHERE email = %s",
                (avatar, now_utc_iso(), (user.get("email") or "").strip().lower()),
            )
        conn.commit()
        return JSONResponse({"success": True})
    except Exception:
        conn.rollback()
        return json_error("Could not save avatar", 500)
    finally:
        conn.close()


@app.get("/api/platform-info")
def platform_info(request: Request):
    if not require_login(request):
        return json_error("Not logged in", 401)
    return JSONResponse({"success": True, "company": PLATFORM_COMPANY_PROFILE})


@app.get("/api/companies")
def api_companies(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    if not is_role(user, ROLE_PLATFORM_ADMIN):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT company_id, company_name, owner_email, plan, status, created_at
                FROM companies
                ORDER BY created_at DESC NULLS LAST, company_id ASC
                LIMIT 500
                """
            )
            companies = cur.fetchall()
        return JSONResponse({"success": True, "companies": companies})
    except Exception as e:
        print("API COMPANIES ERROR:", str(e))
        return json_error("Companies data error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/set-active-company")
async def api_set_active_company(request: Request):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    if not is_role(user, ROLE_PLATFORM_ADMIN):
        return json_error("Forbidden", 403)

    data = await request.json()
    company_id = (data.get("companyId") or "").strip()
    if not company_id:
        return json_error("Missing companyId", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        if not _company_exists_and_active(conn, company_id):
            return json_error("Unknown companyId", 404)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    try:
        request.session["active_company_id"] = company_id
    except Exception:
        pass

    return JSONResponse({"success": True, "companyId": company_id})


# =========================================================
# TEAM / INVITES
# =========================================================

@app.get("/team-data")
def team_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, role, status, created_at, updated_at
                FROM users
                WHERE company_id = %s
                ORDER BY id ASC
                """,
                (company_id,),
            )
            users = cur.fetchall()

            cur.execute(
                """
                SELECT id, email, role, token, expires_at, accepted_at, created_at
                FROM v2_invites
                WHERE company_id = %s
                AND (accepted_at IS NULL OR accepted_at = '')
                ORDER BY id DESC
                LIMIT 100
                """,
                (company_id,),
            )
            invites = cur.fetchall()

        base = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
        if not base:
            base = str(request.base_url).rstrip("/")

        for inv in invites:
            tok = (inv.get("token") or "").strip()
            inv["invite_url"] = f"{base}/accept-invite?token={urllib.parse.quote(tok)}" if tok else ""

        return JSONResponse({"success": True, "users": users, "invites": invites})

    except Exception as e:
        print("TEAM DATA ERROR:", str(e))
        return json_error("Team data error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/invite-user")
async def invite_user(request: Request):
    data = await request.json()
    company_id = (data.get("companyId") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or ROLE_EMPLOYEE).strip() or ROLE_EMPLOYEE

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    if not email or "@" not in email:
        return json_error("Invalid email", 400)

    if role not in {ROLE_EMPLOYEE, ROLE_CLIENT}:
        return json_error("Invalid role", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return json_error("User already exists", 400)

            token = secrets.token_urlsafe(24)
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
            created_at = now_utc_iso()

            cur.execute(
                """
                INSERT INTO v2_invites (email, role, company_id, token, expires_at, accepted_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (email, role, company_id, token, expires_at, "", created_at),
            )

        conn.commit()

        base = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
        if not base:
            base = str(request.base_url).rstrip("/")

        invite_url = f"{base}/accept-invite?token={urllib.parse.quote(token)}"
        return JSONResponse({"success": True, "inviteUrl": invite_url})

    except Exception as e:
        print("INVITE USER ERROR:", str(e))
        return json_error("Invite error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/remove-user")
async def remove_user(request: Request):
    data = await request.json()
    company_id = (data.get("companyId") or "").strip()
    user_id = data.get("userId")

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    try:
        user_id_int = int(user_id)
    except Exception:
        return json_error("Invalid userId", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, role, company_id, email FROM users WHERE id = %s",
                (user_id_int,),
            )
            target = cur.fetchone()
            if not target:
                return json_error("User not found", 404)
            if (target.get("company_id") or "") != company_id:
                return json_error("Forbidden", 403)
            if (target.get("role") or "") != ROLE_EMPLOYEE and not is_role(user, ROLE_PLATFORM_ADMIN):
                return json_error("Only employees can be suspended in this MVP", 400)

            cur.execute(
                """
                UPDATE users
                SET status = %s, updated_at = %s
                WHERE id = %s AND company_id = %s
                """,
                (USER_STATUS_SUSPENDED, now_utc_iso(), user_id_int, company_id),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("REMOVE USER ERROR:", str(e))
        return json_error("Remove user error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/accept-invite")
def accept_invite_page(token: str = ""):
    # Static page reads token from query and calls /accept-invite-api
    return page_response("accept_invite.html")


@app.post("/accept-invite-api")
async def accept_invite_api(request: Request):
    data = await request.json()
    token = (data.get("token") or "").strip()
    password = (data.get("password") or "").strip()

    if not token:
        return json_error("Missing token", 400)
    if not password or len(password) < 6:
        return json_error("Password must be at least 6 characters", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_invites
                WHERE token = %s
                """,
                (token,),
            )
            inv = cur.fetchone()
            if not inv:
                return json_error("Invalid invite token", 400)
            if (inv.get("accepted_at") or "").strip():
                return json_error("Invite already accepted", 400)
            expires_at = (inv.get("expires_at") or "").strip()
            if expires_at:
                try:
                    if datetime.utcnow() > datetime.fromisoformat(expires_at.replace("Z", "")):
                        return json_error("Invite expired", 400)
                except Exception:
                    pass

            email = (inv.get("email") or "").strip().lower()
            role = (inv.get("role") or ROLE_EMPLOYEE).strip() or ROLE_EMPLOYEE
            company_id = (inv.get("company_id") or "").strip()
            if not email or not company_id:
                return json_error("Invalid invite", 400)

            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return json_error("User already exists", 400)

            pw = hash_password(password)
            if not pw:
                return json_error("Invalid password", 400)

            created_at = now_utc_iso()
            cur.execute(
                """
                INSERT INTO users (email, password, password_hash, role, company_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (email, pw, pw, role, company_id, USER_STATUS_ACTIVE, created_at, created_at),
            )
            user_id = (cur.fetchone() or {}).get("id")

            cur.execute(
                """
                UPDATE v2_invites
                SET accepted_at = %s
                WHERE token = %s
                """,
                (created_at, token),
            )

        conn.commit()

        # Do not auto-login invited users; they can login via /login.
        return JSONResponse({"success": True, "email": email, "userId": user_id})

    except Exception as e:
        print("ACCEPT INVITE ERROR:", str(e))
        return json_error("Accept invite error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =========================================================
# DASHBOARD DATA
# =========================================================

@app.get("/dashboard-data")
def dashboard_data(request: Request, companyId: str = ""):
    user = require_login(request)
    if not user:
        return json_error("Not logged in", 401)
    if not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    provided = (companyId or "").strip()
    if is_role(user, ROLE_PLATFORM_ADMIN):
        if not provided:
            provided = (request.session.get("active_company_id") or "").strip()
        if not provided:
            return json_error("Select a company to view its dashboard", 400)
        companyId = provided
    else:
        companyId = (user.get("company_id") or "").strip()
        if not companyId:
            return json_error("Missing company access", 403)
        if provided and provided != companyId:
            return json_error("Forbidden company access", 403)

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s",
                (companyId,),
            )
            total_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "new"),
            )
            new_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "in_progress"),
            )
            in_progress_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "converted"),
            )
            converted_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_content_posts WHERE company_id = %s",
                (companyId,),
            )
            total_posts = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_bookings WHERE company_id = %s",
                (companyId,),
            )
            total_bookings = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_ai_replies WHERE company_id = %s",
                (companyId,),
            )
            total_ai_replies = cur.fetchone()["count"]

            conversion_rate = 0
            if total_leads and int(total_leads) > 0:
                conversion_rate = int(round((converted_leads / total_leads) * 100))

            cur.execute(
                """
                SELECT *
                FROM v2_leads
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (companyId,),
            )
            leads = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM v2_content_posts
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (companyId,),
            )
            posts = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM v2_bookings
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 20
                """,
                (companyId,),
            )
            recent_bookings = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM v2_ai_replies
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 20
                """,
                (companyId,),
            )
            recent_replies = cur.fetchall()

        return JSONResponse(
            {
                "success": True,
                "stats": {
                    "total_leads": total_leads,
                    "new_leads": new_leads,
                    "in_progress_leads": in_progress_leads,
                    "converted_leads": converted_leads,
                    "total_ai_replies": total_ai_replies,
                    # Back-compat key used by existing dashboard.html
                    "ai_conversations": total_ai_replies,
                    "total_posts": total_posts,
                    "social_posts": total_posts,
                    "total_bookings": total_bookings,
                    "bookings": total_bookings,
                    # Prefer numeric conversion_rate; keep text key for older callers
                    "conversion_rate": conversion_rate,
                    "conversion_rate_text": f"{conversion_rate}%",
                    # Back-compat: older callers may expect ai_replies
                    "ai_replies": total_ai_replies,
                },
                "leads": leads,
                "posts": posts,
                "recent_leads": leads[:5],
                "recent_posts": posts[:5],
                "recent_bookings": recent_bookings,
                "recent_replies": recent_replies,
            }
        )

    except Exception as e:
        print("DASHBOARD DATA ERROR:", str(e))

        return JSONResponse(
            {"error": "Dashboard data error"},
            status_code=500,
        )

    finally:
        conn.close()

#
# =========================================================
# LEADS CRM
# =========================================================
#

@app.post("/create-lead")
async def create_lead(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    source = (data.get("source") or "").strip()
    status = (data.get("status") or "new").strip() or "new"
    message = (data.get("message") or "").strip()

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=True,  # website widget can create leads without login
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if user and not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    now = now_utc_iso()

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_leads (
                    company_id,
                    name,
                    email,
                    phone,
                    source,
                    status,
                    message,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    name,
                    email,
                    phone,
                    source,
                    status,
                    message,
                    now,
                ),
            )
            lead_id = cur.fetchone()[0]

        conn.commit()

        return JSONResponse({"success": True, "id": lead_id})

    except Exception as e:
        print("CREATE LEAD ERROR:", str(e))
        return JSONResponse({"error": "Create lead error"}, status_code=500)

    finally:
        conn.close()


@app.post("/update-lead")
async def update_lead(request: Request):
    """
    Minimal MVP update endpoint for CRM actions.
    Contract (flexible):
    - companyId (required)
    - id (required)
    - optional: name, email, phone, source, status, message
    """
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    lead_id = data.get("id")

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    if lead_id is None or str(lead_id).strip() == "":
        return JSONResponse({"error": "Missing id"}, status_code=400)

    updates = {}
    for key in ("name", "email", "phone", "source", "status", "message"):
        if key in data and data.get(key) is not None:
            updates[key] = str(data.get(key)).strip()

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    allowed = ("name", "email", "phone", "source", "status", "message")
    set_parts = []
    values = []
    for key in allowed:
        if key in updates:
            set_parts.append(f"{key} = %s")
            values.append(updates[key])

    values.extend([company_id, lead_id])

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE v2_leads
                SET {", ".join(set_parts)}
                WHERE company_id = %s
                AND id = %s
                """,
                tuple(values),
            )

            if cur.rowcount == 0:
                return JSONResponse({"error": "Lead not found"}, status_code=404)

        conn.commit()
        return JSONResponse({"success": True, "id": int(lead_id)})

    except Exception as e:
        print("UPDATE LEAD ERROR:", str(e))
        return JSONResponse({"error": "Update lead error"}, status_code=500)

    finally:
        conn.close()

@app.post("/delete-lead")
async def delete_lead(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    lead_id = data.get("id")

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    try:
        lead_id_int = int(lead_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM v2_leads
                WHERE company_id = %s
                AND id = %s
                """,
                (company_id, lead_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("DELETE LEAD ERROR:", str(e))
        return JSONResponse({"error": "Delete lead error"}, status_code=500)

    finally:
        conn.close()


@app.post("/update-content-post")
async def update_content_post(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    post_id = data.get("id")
    status = (data.get("status") or "").strip().lower()

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

    try:
        post_id_int = int(post_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    if status not in ("draft", "approved", "published"):
        return JSONResponse({"error": "Invalid status"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE v2_content_posts
                SET status = %s
                WHERE company_id = %s
                AND id = %s
                """,
                (status, company_id, post_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("UPDATE CONTENT POST ERROR:", str(e))
        return JSONResponse({"error": "Update content post error"}, status_code=500)

    finally:
        conn.close()


@app.post("/delete-content-post")
async def delete_content_post(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    post_id = data.get("id")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

    try:
        post_id_int = int(post_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM v2_content_posts
                WHERE company_id = %s
                AND id = %s
                """,
                (company_id, post_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("DELETE CONTENT POST ERROR:", str(e))
        return JSONResponse({"error": "Delete content post error"}, status_code=500)

    finally:
        conn.close()


# =========================================================
# SOCIAL ACCOUNTS
# =========================================================

def _meta_config():
    app_id = (os.getenv("META_APP_ID") or "").strip()
    app_secret = (os.getenv("META_APP_SECRET") or "").strip()
    redirect_uri = (os.getenv("META_REDIRECT_URI") or "").strip()
    return app_id, app_secret, redirect_uri


def _http_get_json(url: str, timeout_sec: int = 15):
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "AI-FLOW/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}


def _http_post_form_json(url: str, form_data: dict, timeout_sec: int = 20):
    body = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "AI-FLOW/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}


def _iso_z(dt: datetime):
    return dt.isoformat() + "Z"


def _parse_iso_z(s: str):
    try:
        if not s:
            return None
        v = str(s).strip()
        if v.endswith("Z"):
            v = v[:-1]
        return datetime.fromisoformat(v)
    except Exception:
        return None


def _company_exists(company_id: str):
    company_id = (company_id or "").strip()
    if not company_id:
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM companies WHERE company_id = %s LIMIT 1", (company_id,))
            return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def _oauth_state_is_fresh(created_at: str, ttl_minutes: int = 20):
    dt = _parse_iso_z(created_at)
    if not dt:
        return False
    return dt >= (datetime.utcnow() - timedelta(minutes=ttl_minutes))


OAUTH_STATE_TTL_MINUTES = 20
OAUTH_STATE_TABLES = {
    "meta": "v2_meta_oauth_states",
    "tiktok": "v2_tiktok_oauth_states",
}
META_OAUTH_SUCCESS_REDIRECT = "/social-accounts?meta_connected=1"
META_OAUTH_ALREADY_CONNECTED_REDIRECT = "/social-accounts?meta_status=already_connected"
META_OAUTH_INVALID_STATE_REDIRECT = "/social-accounts?meta_error=invalid_state"
META_OAUTH_MISSING_PARAMS_REDIRECT = "/social-accounts?meta_error=missing_callback_params"
META_OAUTH_CONFIG_ERROR_REDIRECT = "/social-accounts?meta_error=config"
META_OAUTH_TOKEN_ERROR_REDIRECT = "/social-accounts?meta_error=token_exchange"
META_OAUTH_SAVE_ERROR_REDIRECT = "/social-accounts?meta_error=save_failed"
META_OAUTH_STATE_ERROR_REDIRECT = "/social-accounts?meta_error=state_lookup"


def _oauth_state_table(provider: str) -> str:
    table = OAUTH_STATE_TABLES.get((provider or "").strip().lower())
    if not table:
        raise ValueError("Unknown OAuth provider")
    return table


def _oauth_state_signature(payload: str) -> str:
    digest = hmac.new(
        _secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64e(digest)


def _create_oauth_state(provider: str, company_id: str, *, include_company_prefix: bool = False) -> str:
    payload = _b64e(
        json.dumps(
            {
                "provider": (provider or "").strip().lower(),
                "company_id": (company_id or "").strip(),
                "issued_at": int(datetime.utcnow().timestamp()),
                "nonce": secrets.token_urlsafe(24),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    token = f"{payload}.{_oauth_state_signature(payload)}"
    if include_company_prefix:
        return f"{company_id}.{token}"
    return token


def _verify_signed_oauth_state(state: str, provider: str, ttl_minutes: int = OAUTH_STATE_TTL_MINUTES):
    parts = (state or "").strip().split(".")
    if len(parts) < 2:
        return "", "unsigned"

    payload = parts[-2]
    provided_sig = parts[-1]
    expected_sig = _oauth_state_signature(payload)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return "", "bad_signature"

    try:
        data = json.loads(_b64d(payload).decode("utf-8"))
    except Exception:
        return "", "bad_payload"

    expected_provider = (provider or "").strip().lower()
    if (data.get("provider") or "").strip().lower() != expected_provider:
        return "", "wrong_provider"

    company_id = (data.get("company_id") or "").strip()
    try:
        issued_at = int(data.get("issued_at") or 0)
    except Exception:
        return "", "bad_issued_at"

    now_ts = int(datetime.utcnow().timestamp())
    if not company_id or not issued_at:
        return "", "bad_payload"
    if issued_at > now_ts + 300:
        return "", "issued_in_future"
    if issued_at < now_ts - (ttl_minutes * 60):
        return "", "expired"

    return company_id, ""


def _store_oauth_state_in_session(request: Request, provider: str, state: str, company_id: str):
    try:
        current_states = request.session.get("oauth_states") or {}
        if not isinstance(current_states, dict):
            current_states = {}

        current_states[state] = {
            "provider": (provider or "").strip().lower(),
            "company_id": (company_id or "").strip(),
            "created_at": _iso_z(datetime.utcnow()),
        }
        newest_states = sorted(
            current_states.items(),
            key=lambda item: (item[1] or {}).get("created_at", ""),
            reverse=True,
        )[:5]
        request.session["oauth_states"] = dict(newest_states)
    except Exception as e:
        print("OAUTH SESSION STATE STORE ERROR:", type(e).__name__)


def _consume_oauth_state_from_session(request: Request, provider: str, state: str) -> str:
    try:
        current_states = request.session.get("oauth_states") or {}
        if not isinstance(current_states, dict):
            return ""

        entry = current_states.pop(state, None)
        request.session["oauth_states"] = current_states
        if not isinstance(entry, dict):
            return ""

        if (entry.get("provider") or "").strip().lower() != (provider or "").strip().lower():
            return ""
        if not _oauth_state_is_fresh(entry.get("created_at") or "", OAUTH_STATE_TTL_MINUTES):
            return ""
        return (entry.get("company_id") or "").strip()
    except Exception as e:
        print("OAUTH SESSION STATE CONSUME ERROR:", type(e).__name__)
        return ""


def _store_oauth_state_in_db(provider: str, state: str, company_id: str) -> str:
    table = _oauth_state_table(provider)
    now = _iso_z(datetime.utcnow())
    cutoff = _iso_z(datetime.utcnow() - timedelta(minutes=30))

    conn = get_db_connection()
    if not conn:
        return "Database error"

    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE created_at < %s", (cutoff,))
            cur.execute(
                f"""
                INSERT INTO {table} (state, company_id, created_at)
                VALUES (%s, %s, %s)
                """,
                (state, company_id, now),
            )
        conn.commit()
        return ""
    except Exception as e:
        print(f"{provider.upper()} OAUTH STATE STORE ERROR:", type(e).__name__)
        return "OAuth state store error"
    finally:
        conn.close()


def _consume_oauth_state_from_db(provider: str, state: str):
    table = _oauth_state_table(provider)
    conn = get_db_connection()
    if not conn:
        return "", "Database error"

    company_id = ""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT company_id, created_at FROM {table} WHERE state = %s",
                (state,),
            )
            row = cur.fetchone()
            if row and _oauth_state_is_fresh(row.get("created_at") or "", OAUTH_STATE_TTL_MINUTES):
                company_id = (row.get("company_id") or "").strip()
            cur.execute(f"DELETE FROM {table} WHERE state = %s", (state,))
        conn.commit()
        return company_id, ""
    except Exception as e:
        print(f"{provider.upper()} OAUTH STATE CONSUME ERROR:", type(e).__name__)
        return "", "OAuth state lookup error"
    finally:
        conn.close()


def _resolve_oauth_company_from_state_with_source(request: Request, provider: str, state: str):
    company_id, lookup_error = _consume_oauth_state_from_db(provider, state)
    if lookup_error:
        return "", lookup_error, "db_error"
    if company_id:
        return company_id, "", "db"

    company_id = _consume_oauth_state_from_session(request, provider, state)
    if company_id:
        return company_id, "", "session"

    company_id, verify_error = _verify_signed_oauth_state(state, provider)
    if company_id and _company_exists(company_id):
        print(f"{provider.upper()} OAUTH STATE RECOVERED FROM SIGNED STATE")
        return company_id, "", "signed"

    print(
        f"{provider.upper()} OAUTH INVALID STATE:",
        {"reason": verify_error or "not_found", "state_length": len(state or "")},
    )
    return "", "Invalid state", verify_error or "not_found"


def _resolve_oauth_company_from_state(request: Request, provider: str, state: str):
    company_id, state_error, _source = _resolve_oauth_company_from_state_with_source(request, provider, state)
    return company_id, state_error


def _meta_connection_exists(company_id: str) -> bool:
    company_id = (company_id or "").strip()
    if not company_id:
        return False

    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM v2_social_tokens
                WHERE company_id = %s
                AND provider = %s
                LIMIT 1
                """,
                (company_id, "meta"),
            )
            if cur.fetchone() is not None:
                return True

            cur.execute(
                """
                SELECT 1
                FROM v2_social_accounts
                WHERE company_id = %s
                AND platform IN ('Facebook', 'Instagram')
                LIMIT 1
                """,
                (company_id,),
            )
            return cur.fetchone() is not None
    except Exception as e:
        print("META CONNECTION CHECK ERROR:", type(e).__name__)
        return False
    finally:
        conn.close()


def _oauth_value_hash(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _meta_oauth_redirect(url: str, reason: str, state: str = "", company_id: str = ""):
    print(
        "META OAUTH REDIRECT:",
        {
            "reason": reason,
            "target": url,
            "company_id": (company_id or "").strip(),
            "state_hash": _oauth_value_hash(state),
        },
    )
    return RedirectResponse(url=url, status_code=302)


def _meta_oauth_success_value(success) -> bool:
    return str(success or "").strip().lower() in {"1", "true", "yes", "success"}


def _mark_meta_oauth_state_result(state: str, success: bool):
    state = (state or "").strip()
    if not state:
        return

    conn = get_db_connection()
    if not conn:
        print("META OAUTH STATE RESULT UPDATE SKIPPED: database unavailable")
        return

    now = _iso_z(datetime.utcnow())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE v2_meta_oauth_states
                SET
                    success = %s,
                    consumed_at = CASE
                        WHEN COALESCE(consumed_at, '') = '' THEN %s
                        ELSE consumed_at
                    END,
                    updated_at = %s
                WHERE state = %s
                """,
                ("1" if success else "0", now, now, state),
            )
        conn.commit()
    except Exception as e:
        print("META OAUTH STATE RESULT UPDATE ERROR:", type(e).__name__)
    finally:
        conn.close()


def _consumed_meta_state_result(row: dict, state: str):
    company_id = (row.get("company_id") or "").strip()
    success = _meta_oauth_success_value(row.get("success"))
    print(
        "META OAUTH STATE ALREADY CONSUMED:",
        {
            "company_id": company_id,
            "success": success,
            "state_hash": _oauth_value_hash(state),
        },
    )
    return {
        "status": "consumed",
        "company_id": company_id,
        "success": success,
        "source": "db",
    }


def _claim_meta_oauth_state(request: Request, state: str):
    """
    Claim a Meta OAuth state exactly once before exchanging the single-use code.
    Duplicate callbacks see the consumed state and never retry token exchange.
    """
    state = (state or "").strip()
    now = _iso_z(datetime.utcnow())

    conn = get_db_connection()
    if not conn:
        return {"status": "error", "reason": "database_unavailable"}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT company_id, created_at, consumed_at, success
                FROM v2_meta_oauth_states
                WHERE state = %s
                """,
                (state,),
            )
            row = cur.fetchone()

            if row:
                company_id = (row.get("company_id") or "").strip()
                consumed_at = (row.get("consumed_at") or "").strip()
                if consumed_at:
                    return _consumed_meta_state_result(row, state)

                if not _oauth_state_is_fresh(row.get("created_at") or "", OAUTH_STATE_TTL_MINUTES):
                    print(
                        "META OAUTH STATE EXPIRED:",
                        {"company_id": company_id, "state_hash": _oauth_value_hash(state)},
                    )
                    return {"status": "invalid", "reason": "expired", "company_id": company_id}

                cur.execute(
                    """
                    UPDATE v2_meta_oauth_states
                    SET consumed_at = %s, updated_at = %s
                    WHERE state = %s
                    AND COALESCE(consumed_at, '') = ''
                    RETURNING company_id
                    """,
                    (now, now, state),
                )
                claimed = cur.fetchone()
                conn.commit()

                if claimed:
                    print(
                        "META OAUTH STATE VALID:",
                        {"company_id": company_id, "source": "db", "state_hash": _oauth_value_hash(state)},
                    )
                    return {"status": "claimed", "company_id": company_id, "source": "db"}

                cur.execute(
                    """
                    SELECT company_id, created_at, consumed_at, success
                    FROM v2_meta_oauth_states
                    WHERE state = %s
                    """,
                    (state,),
                )
                row = cur.fetchone()
                if row and (row.get("consumed_at") or "").strip():
                    return _consumed_meta_state_result(row, state)

                return {"status": "invalid", "reason": "claim_race", "company_id": company_id}

        company_id = _consume_oauth_state_from_session(request, "meta", state)
        source = "session" if company_id else ""
        verify_error = ""

        if not company_id:
            company_id, verify_error = _verify_signed_oauth_state(state, "meta")
            if company_id and _company_exists(company_id):
                source = "signed"
            else:
                company_id = ""

        if not company_id:
            print(
                "META OAUTH STATE NOT FOUND:",
                {"reason": verify_error or "not_found", "state_hash": _oauth_value_hash(state)},
            )
            return {"status": "invalid", "reason": verify_error or "not_found"}

        if _meta_connection_exists(company_id):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_meta_oauth_states (state, company_id, created_at, consumed_at, success, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (state) DO NOTHING
                    """,
                    (state, company_id, now, now, "1", now),
                )
            conn.commit()
            print(
                "META OAUTH STATE RECOVERED FOR EXISTING CONNECTION:",
                {"company_id": company_id, "source": source, "state_hash": _oauth_value_hash(state)},
            )
            return {"status": "consumed", "company_id": company_id, "success": True, "source": source}

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO v2_meta_oauth_states (state, company_id, created_at, consumed_at, success, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (state) DO NOTHING
                """,
                (state, company_id, now, now, "", now),
            )
            inserted = cur.rowcount > 0
            conn.commit()

            if inserted:
                print(
                    "META OAUTH STATE VALID:",
                    {"company_id": company_id, "source": source, "state_hash": _oauth_value_hash(state)},
                )
                return {"status": "claimed", "company_id": company_id, "source": source}

            cur.execute(
                """
                SELECT company_id, created_at, consumed_at, success
                FROM v2_meta_oauth_states
                WHERE state = %s
                """,
                (state,),
            )
            row = cur.fetchone()
            if row and (row.get("consumed_at") or "").strip():
                return _consumed_meta_state_result(row, state)

            return {"status": "invalid", "reason": "claim_conflict", "company_id": company_id}

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print("META OAUTH STATE CLAIM ERROR:", type(e).__name__)
        return {"status": "error", "reason": "claim_error"}
    finally:
        conn.close()


def _tiktok_config():
    client_key = (os.getenv("TIKTOK_CLIENT_KEY") or "").strip()
    client_secret = (os.getenv("TIKTOK_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("TIKTOK_REDIRECT_URI") or "").strip()
    return client_key, client_secret, redirect_uri


def _mask_value(v: str, keep: int = 4):
    s = str(v or "")
    if not s:
        return ""
    if len(s) <= keep * 2:
        return "*" * len(s)
    return s[:keep] + ("*" * (len(s) - (keep * 2))) + s[-keep:]


def _is_placeholder_value(v: str):
    value = str(v or "").strip().lower()
    return value in {
        "",
        "undefined",
        "null",
        "none",
        "changeme",
        "placeholder",
        "your_token",
        "your_access_token",
        "your_verify_token",
        "your_phone_number_id",
        "your_business_account_id",
    }


def _tiktok_config_issue(client_key: str, client_secret: str, redirect_uri: str):
    missing = []
    if not client_key:
        missing.append("TIKTOK_CLIENT_KEY")
    if not client_secret:
        missing.append("TIKTOK_CLIENT_SECRET")
    if not redirect_uri:
        missing.append("TIKTOK_REDIRECT_URI")
    if missing:
        return "Missing " + " / ".join(missing)

    lower_key = client_key.lower()
    bad_values = {
        "undefined",
        "null",
        "none",
        "client_key",
        "your_client_key",
        "your-client-key",
        "changeme",
        "placeholder",
    }
    if lower_key in bad_values:
        return "TIKTOK_CLIENT_KEY is a placeholder value"

    if any(ch.isspace() for ch in client_key):
        return "TIKTOK_CLIENT_KEY contains whitespace"

    if client_key == client_secret:
        return "TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET cannot be equal"

    uri_err = _validate_redirect_uri(redirect_uri, "tiktok")
    if uri_err:
        return uri_err

    return ""


def _whatsapp_config_snapshot():
    whatsapp_access_token = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
    whatsapp_phone_number_id = (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    whatsapp_business_account_id = (os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID") or "").strip()
    whatsapp_verify_token = (os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()
    whatsapp_redirect_uri = (os.getenv("WHATSAPP_REDIRECT_URI") or "").strip()
    meta_app_id = (os.getenv("META_APP_ID") or "").strip()
    meta_app_secret = (os.getenv("META_APP_SECRET") or "").strip()
    meta_redirect_uri = (os.getenv("META_REDIRECT_URI") or "").strip()

    oauth_ready = (
        not _is_placeholder_value(meta_app_id)
        and not _is_placeholder_value(meta_app_secret)
        and not _is_placeholder_value(meta_redirect_uri)
    )
    manual_ready = (
        not _is_placeholder_value(whatsapp_access_token)
        and not _is_placeholder_value(whatsapp_phone_number_id)
    )

    missing = []
    if not oauth_ready and not manual_ready:
        if _is_placeholder_value(meta_app_id):
            missing.append("META_APP_ID")
        if _is_placeholder_value(meta_app_secret):
            missing.append("META_APP_SECRET")
        if _is_placeholder_value(meta_redirect_uri):
            missing.append("META_REDIRECT_URI")
        if _is_placeholder_value(whatsapp_access_token):
            missing.append("WHATSAPP_ACCESS_TOKEN")
        if _is_placeholder_value(whatsapp_phone_number_id):
            missing.append("WHATSAPP_PHONE_NUMBER_ID")

    return {
        "oauth_ready": oauth_ready,
        "manual_ready": manual_ready,
        "missing": missing,
        "meta_app_id": meta_app_id,
        "meta_app_secret": meta_app_secret,
        "meta_redirect_uri": meta_redirect_uri,
        "whatsapp_access_token": whatsapp_access_token,
        "whatsapp_phone_number_id": whatsapp_phone_number_id,
        "whatsapp_business_account_id": whatsapp_business_account_id,
        "whatsapp_verify_token": whatsapp_verify_token,
        "whatsapp_redirect_uri": whatsapp_redirect_uri,
    }


def _log_social_env_debug():
    tiktok_key, tiktok_secret, tiktok_redirect = _tiktok_config()
    wa = _whatsapp_config_snapshot()
    print(
        "SOCIAL ENV DEBUG:",
        {
            "tiktok_client_key_mask": _mask_value(tiktok_key),
            "tiktok_client_secret_mask": _mask_value(tiktok_secret),
            "tiktok_client_key_len": len(tiktok_key),
            "tiktok_client_secret_len": len(tiktok_secret),
            "tiktok_key_secret_equal": bool(tiktok_key and tiktok_secret and (tiktok_key == tiktok_secret)),
            "tiktok_redirect_uri": tiktok_redirect,
            "whatsapp_access_token_present": not _is_placeholder_value(wa["whatsapp_access_token"]),
            "whatsapp_access_token_mask": _mask_value(wa["whatsapp_access_token"]),
            "whatsapp_phone_number_id_present": not _is_placeholder_value(wa["whatsapp_phone_number_id"]),
            "whatsapp_business_account_id_present": not _is_placeholder_value(wa["whatsapp_business_account_id"]),
            "whatsapp_verify_token_present": not _is_placeholder_value(wa["whatsapp_verify_token"]),
            "whatsapp_redirect_uri_present": not _is_placeholder_value(wa["whatsapp_redirect_uri"]),
            "meta_app_id_present": not _is_placeholder_value(wa["meta_app_id"]),
            "meta_app_secret_present": not _is_placeholder_value(wa["meta_app_secret"]),
            "meta_redirect_uri_present": not _is_placeholder_value(wa["meta_redirect_uri"]),
        },
    )


def _build_tiktok_authorize_url(client_key: str, redirect_uri: str, state: str, scope: str = "user.info.basic"):
    qs = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    auth_url = f"https://www.tiktok.com/v2/auth/authorize/?{qs}"

    parsed = urllib.parse.urlparse(auth_url)
    safe_query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_pairs = []
    for k, v in safe_query:
        if k == "client_key":
            safe_pairs.append((k, _mask_value(v)))
        else:
            safe_pairs.append((k, v))
    safe_url = urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urllib.parse.urlencode(safe_pairs),
            parsed.fragment,
        )
    )

    # Safe debug log: confirms which key is used without exposing secrets.
    print(
        "TIKTOK OAUTH AUTHORIZE URL READY:",
        {
            "client_key_present": bool(client_key),
            "client_key_mask": _mask_value(client_key),
            "redirect_uri": redirect_uri,
            "state_prefix": state[:20],
            "authorize_url_safe": safe_url,
        },
    )
    return auth_url


def _validate_redirect_uri(uri: str, provider: str):
    u = (uri or "").strip()
    if not u:
        return "Missing redirect URI"
    # Both Meta + TikTok require an exact, pre-registered HTTPS redirect URI.
    if not (u.startswith("https://") or u.startswith("http://localhost")):
        return "Redirect URI must be https (localhost allowed for development)"
    if "#" in u:
        return "Redirect URI must not contain a # fragment"
    # TikTok explicitly disallows query parameters in redirect_uri for web apps.
    if provider == "tiktok" and "?" in u:
        return "TikTok redirect URI must not contain query parameters"
    return ""


@app.get("/api/meta/connect")
def meta_connect(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_admin_company(request, companyId)
    if err:
        return err

    app_id, app_secret, redirect_uri = _meta_config()
    if not app_id or not app_secret or not redirect_uri:
        return JSONResponse(
            {
                "error": "Meta OAuth is not configured",
                "detail": "Missing META_APP_ID / META_APP_SECRET / META_REDIRECT_URI",
            },
            status_code=500,
        )
    uri_err = _validate_redirect_uri(redirect_uri, "meta")
    if uri_err:
        return JSONResponse({"error": "Meta OAuth redirect URI is invalid", "detail": uri_err}, status_code=500)

    state = _create_oauth_state("meta", company_id)
    state_error = _store_oauth_state_in_db("meta", state, company_id)
    if state_error:
        return JSONResponse({"error": state_error}, status_code=500)
    _store_oauth_state_in_session(request, "meta", state, company_id)

    # Publishing scopes. Meta may require Advanced Access/app review before
    # non-role users can grant these permissions.
    scope = ",".join(
        [
            "public_profile",
            "email",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts",
            "instagram_basic",
            "instagram_content_publish",
        ]
    )

    qs = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": scope,
        }
    )
    auth_url = f"https://www.facebook.com/v20.0/dialog/oauth?{qs}"

    return HTMLResponse(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={auth_url}"></head>
<body style="font-family:Arial,sans-serif;background:#061923;color:#f7fbff;padding:24px;">
Redirecting to Meta OAuth...
</body></html>"""
    )


@app.get("/api/meta/callback")
def meta_callback(request: Request, code: str = "", state: str = ""):
    print(
        "META CALLBACK RECEIVED:",
        {
            "code_present": bool(code),
            "state_present": bool(state),
            "state_hash": _oauth_value_hash(state),
            "state_length": len(state or ""),
        },
    )

    if not code or not state:
        return _meta_oauth_redirect(META_OAUTH_MISSING_PARAMS_REDIRECT, "missing_code_or_state", state)

    app_id, app_secret, redirect_uri = _meta_config()
    if not app_id or not app_secret or not redirect_uri:
        print("META OAUTH CALLBACK CONFIG ERROR: missing Meta OAuth env")
        return _meta_oauth_redirect(META_OAUTH_CONFIG_ERROR_REDIRECT, "config_error", state)

    state_claim = _claim_meta_oauth_state(request, state)
    claim_status = state_claim.get("status") or ""
    company_id = (state_claim.get("company_id") or "").strip()

    if claim_status == "consumed":
        if state_claim.get("success") or _meta_connection_exists(company_id):
            return _meta_oauth_redirect(
                META_OAUTH_ALREADY_CONNECTED_REDIRECT,
                "state_already_consumed_connection_exists",
                state,
                company_id,
            )
        return _meta_oauth_redirect(
            META_OAUTH_INVALID_STATE_REDIRECT,
            "state_already_consumed_without_connection",
            state,
            company_id,
        )

    if claim_status == "error":
        return _meta_oauth_redirect(
            META_OAUTH_STATE_ERROR_REDIRECT,
            state_claim.get("reason") or "state_lookup_error",
            state,
            company_id,
        )

    if claim_status != "claimed" or not company_id:
        return _meta_oauth_redirect(
            META_OAUTH_INVALID_STATE_REDIRECT,
            state_claim.get("reason") or "invalid_state",
            state,
            company_id,
        )

    # Exchange code -> user access token (avoid logging any secrets)
    token_qs = urllib.parse.urlencode(
        {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "client_secret": app_secret,
            "code": code,
        }
    )
    token_url = f"https://graph.facebook.com/v20.0/oauth/access_token?{token_qs}"

    try:
        token_data = _http_get_json(token_url)
        user_token = token_data.get("access_token") or ""
        expires_in = token_data.get("expires_in")
    except Exception as e:
        print("META TOKEN EXCHANGE ERROR:", type(e).__name__)
        _mark_meta_oauth_state_result(state, False)
        return _meta_oauth_redirect(META_OAUTH_TOKEN_ERROR_REDIRECT, "token_exchange_error", state, company_id)

    if not user_token:
        print("META TOKEN EXCHANGE FAILED: no access token returned")
        _mark_meta_oauth_state_result(state, False)
        return _meta_oauth_redirect(META_OAUTH_TOKEN_ERROR_REDIRECT, "token_exchange_failed", state, company_id)

    expires_at = ""
    try:
        if expires_in is not None:
            expires_at = (datetime.utcnow() + timedelta(seconds=int(expires_in))).isoformat() + "Z"
    except Exception:
        expires_at = ""

    # Fetch Pages + IG business accounts
    accounts_url = (
        "https://graph.facebook.com/v20.0/me/accounts?"
        + urllib.parse.urlencode(
            {
                "fields": "id,name,access_token,instagram_business_account{id,username,name}",
                "access_token": user_token,
            }
        )
    )

    try:
        accounts_data = _http_get_json(accounts_url)
        pages = accounts_data.get("data") or []
    except Exception as e:
        print("META ACCOUNTS ERROR:", type(e).__name__)
        pages = []

    now = _iso_z(datetime.utcnow())
    conn = get_db_connection()
    if not conn:
        _mark_meta_oauth_state_result(state, False)
        return _meta_oauth_redirect(META_OAUTH_SAVE_ERROR_REDIRECT, "database_unavailable", state, company_id)

    saved_pages = 0
    saved_instagrams = 0
    try:
        with conn.cursor() as cur:
            # Store user token (company-level) for future calls (not exposed to frontend).
            cur.execute(
                """
                INSERT INTO v2_social_tokens (company_id, provider, platform, account_id, access_token, token_expires_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, provider, platform, account_id)
                DO UPDATE SET access_token = EXCLUDED.access_token, token_expires_at = EXCLUDED.token_expires_at, updated_at = EXCLUDED.updated_at
                """,
                (company_id, "meta", "meta_user", "me", user_token, expires_at, now, now),
            )

            for p in pages:
                page_id = str(p.get("id") or "")
                page_name = str(p.get("name") or "")
                page_token = str(p.get("access_token") or "")

                if page_id:
                    # Prevent duplicates (do not assume any unique index exists in the DB).
                    cur.execute(
                        "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s AND account_id = %s",
                        (company_id, "Facebook", page_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO v2_social_accounts (company_id, platform, status, account_name, account_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (company_id, "Facebook", "connected", page_name, page_id, now, now),
                    )
                    saved_pages += 1

                    # Store page token
                    if page_token:
                        cur.execute(
                            """
                            INSERT INTO v2_social_tokens (company_id, provider, platform, account_id, access_token, token_expires_at, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (company_id, provider, platform, account_id)
                            DO UPDATE SET access_token = EXCLUDED.access_token, token_expires_at = EXCLUDED.token_expires_at, updated_at = EXCLUDED.updated_at
                            """,
                            (company_id, "meta", "Facebook", page_id, page_token, "", now, now),
                        )

                ig = p.get("instagram_business_account") or {}
                ig_id = str(ig.get("id") or "")
                ig_name = str(ig.get("username") or ig.get("name") or "")
                if ig_id:
                    cur.execute(
                        "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s AND account_id = %s",
                        (company_id, "Instagram", ig_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO v2_social_accounts (company_id, platform, status, account_name, account_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (company_id, "Instagram", "connected", ig_name, ig_id, now, now),
                    )
                    saved_instagrams += 1
                    if page_token:
                        cur.execute(
                            """
                            INSERT INTO v2_social_tokens (company_id, provider, platform, account_id, access_token, token_expires_at, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (company_id, provider, platform, account_id)
                            DO UPDATE SET access_token = EXCLUDED.access_token, updated_at = EXCLUDED.updated_at
                            """,
                            (company_id, "meta", "Instagram", ig_id, page_token, "", now, now),
                        )

        conn.commit()
    except Exception as e:
        # Avoid logging token contents; keep logs minimal.
        print("META CALLBACK DB ERROR:", type(e).__name__)
        _mark_meta_oauth_state_result(state, False)
        return _meta_oauth_redirect(META_OAUTH_SAVE_ERROR_REDIRECT, "connection_save_error", state, company_id)
    finally:
        conn.close()

    _mark_meta_oauth_state_result(state, True)
    print(
        "META CONNECTION SAVED:",
        {
            "company_id": company_id,
            "pages": saved_pages,
            "instagrams": saved_instagrams,
            "state_hash": _oauth_value_hash(state),
        },
    )
    return _meta_oauth_redirect(META_OAUTH_SUCCESS_REDIRECT, "connection_saved", state, company_id)


@app.get("/api/meta/accounts")
def meta_accounts(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, platform, status, account_name, account_id, created_at, updated_at
                FROM v2_social_accounts
                WHERE company_id = %s
                AND platform IN ('Facebook', 'Instagram')
                ORDER BY id DESC
                """,
                (company_id,),
            )
            rows = cur.fetchall()

        pages = [r for r in rows if r.get("platform") == "Facebook"]
        instagrams = [r for r in rows if r.get("platform") == "Instagram"]
        return JSONResponse({"success": True, "pages": pages, "instagrams": instagrams})
    except Exception as e:
        print("META ACCOUNTS DATA ERROR:", type(e).__name__)
        return JSONResponse({"error": "Meta accounts error"}, status_code=500)
    finally:
        conn.close()


@app.post("/api/meta/disconnect")
async def meta_disconnect(request: Request):
    data = await request.json()
    company_id, user, err = resolve_company_id(
        request,
        (data.get("companyId") or "").strip(),
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM v2_social_tokens WHERE company_id = %s AND provider = %s",
                (company_id, "meta"),
            )
            cur.execute(
                "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform IN ('Facebook','Instagram')",
                (company_id,),
            )
        conn.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        print("META DISCONNECT ERROR:", type(e).__name__)
        return JSONResponse({"error": "Meta disconnect error"}, status_code=500)
    finally:
        conn.close()


# =========================================================
# INSTAGRAM PUBLISHING
# =========================================================

def _instagram_graph_version():
    return (os.getenv("META_GRAPH_VERSION") or "v20.0").strip() or "v20.0"


def _resolve_instagram_company(request: Request, provided_company_id: str):
    company_id, user, err = resolve_company_id(
        request,
        provided_company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return "", err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return "", json_error("Forbidden", 403)
    return company_id, None


def _safe_instagram_error(message: str) -> str:
    msg = str(message or "Instagram publish error").strip()
    if not msg:
        msg = "Instagram publish error"
    if len(msg) > 500:
        msg = msg[:500].rstrip() + "..."
    return msg


def _instagram_graph_error(data: dict, fallback: str = "Instagram Graph API error") -> str:
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        msg = (err.get("message") or fallback).strip()
        code = err.get("code")
        subcode = err.get("error_subcode")
        if code or subcode:
            suffix = " / ".join(str(x) for x in (code, subcode) if x)
            msg = f"{msg} ({suffix})"
        return _safe_instagram_error(msg)
    if isinstance(err, str) and err.strip():
        return _safe_instagram_error(err)
    return _safe_instagram_error(fallback)


def _http_post_form_json_graph(url: str, form_data: dict, timeout_sec: int = 30):
    body = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "AI-FLOW/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict) and data.get("error"):
                return data, _instagram_graph_error(data)
            return data, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return data, _instagram_graph_error(data, f"Instagram API HTTP {e.code}")
    except Exception as e:
        return {}, _safe_instagram_error(f"Instagram API request error: {type(e).__name__}")


def _http_get_json_graph(url: str, timeout_sec: int = 20):
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "AI-FLOW/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict) and data.get("error"):
                return data, _instagram_graph_error(data)
            return data, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return data, _instagram_graph_error(data, f"Instagram API HTTP {e.code}")
    except Exception as e:
        return {}, _safe_instagram_error(f"Instagram API request error: {type(e).__name__}")


def _parse_instagram_media_urls(value):
    if isinstance(value, list):
        urls = value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
            urls = parsed if isinstance(parsed, list) else [value]
        except Exception:
            urls = value.replace(",", "\n").splitlines()
    else:
        urls = []
    return [str(u or "").strip() for u in urls if str(u or "").strip()]


def _validate_instagram_public_urls(media_urls: list[str]) -> str:
    for url in media_urls:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Image/video URLs must be publicly accessible http(s) URLs."
    return ""


def _validate_instagram_draft_payload(post_type: str, media_urls: list[str]) -> str:
    if post_type not in {"image", "carousel", "reel"}:
        return "post_type must be image, carousel, or reel"
    url_err = _validate_instagram_public_urls(media_urls)
    if url_err:
        return url_err
    if post_type == "image" and len(media_urls) != 1:
        return "Image posts require exactly 1 image URL."
    if post_type == "reel" and len(media_urls) != 1:
        return "Reels require exactly 1 public video URL."
    if post_type == "carousel" and not (2 <= len(media_urls) <= 10):
        return "Carousel posts require 2-10 image URLs."
    return ""


def _instagram_job_to_public(row: dict) -> dict:
    media_urls = _parse_instagram_media_urls(row.get("media_urls") or "[]")
    return {
        "id": row.get("id"),
        "company_id": row.get("company_id") or "",
        "provider": row.get("provider") or "instagram",
        "post_type": row.get("post_type") or "",
        "ig_user_id": row.get("ig_user_id") or "",
        "page_id": row.get("page_id") or "",
        "media_urls": media_urls,
        "caption": row.get("caption") or "",
        "status": row.get("status") or "",
        "creation_id": row.get("creation_id") or "",
        "media_id": row.get("media_id") or "",
        "permalink": row.get("permalink") or "",
        "error_message": row.get("error_message") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
        "published_at": row.get("published_at") or "",
    }


def _update_instagram_job(company_id: str, job_id: int, **fields):
    allowed = {
        "status",
        "creation_id",
        "media_id",
        "permalink",
        "error_message",
        "updated_at",
        "published_at",
    }
    updates = []
    values = []
    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key} = %s")
            values.append(value)
    if not updates:
        return

    values.extend([company_id, job_id])
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE v2_instagram_publish_jobs
                SET {", ".join(updates)}
                WHERE company_id = %s AND id = %s
                """,
                tuple(values),
            )
        conn.commit()
    except Exception as e:
        print("INSTAGRAM JOB UPDATE ERROR:", type(e).__name__)
    finally:
        conn.close()


def _instagram_fail_job(company_id: str, job_id: int, message: str, *, status_code: int = 400):
    safe_message = _safe_instagram_error(message)
    now = _iso_z(datetime.utcnow())
    _update_instagram_job(
        company_id,
        job_id,
        status="failed",
        error_message=safe_message,
        updated_at=now,
    )
    print(
        "INSTAGRAM PUBLISH FAILED:",
        {"company_id": company_id, "job_id": job_id, "status": "failed", "error": safe_message[:160]},
    )
    return JSONResponse({"success": False, "error": safe_message}, status_code=status_code)


def _instagram_token_for_account(company_id: str, ig_user_id: str):
    conn = get_db_connection()
    if not conn:
        return None, "", "Database error"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, account_name, account_id, status
                FROM v2_social_accounts
                WHERE company_id = %s
                AND platform = %s
                AND account_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (company_id, "Instagram", ig_user_id),
            )
            account = cur.fetchone()
            if not account:
                return None, "", "Instagram account is not connected."

            cur.execute(
                """
                SELECT access_token
                FROM v2_social_tokens
                WHERE company_id = %s
                AND provider = %s
                AND platform = %s
                AND account_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (company_id, "meta", "Instagram", ig_user_id),
            )
            token_row = cur.fetchone()
            token = (token_row.get("access_token") or "").strip() if token_row else ""
            if not token:
                return account, "", "Instagram token missing. Reconnect Meta to refresh access."
            return account, token, ""
    except Exception as e:
        print("INSTAGRAM TOKEN LOOKUP ERROR:", type(e).__name__)
        return None, "", "Instagram token lookup error"
    finally:
        conn.close()


def _instagram_create_container(ig_user_id: str, access_token: str, params: dict):
    url = f"https://graph.facebook.com/{_instagram_graph_version()}/{urllib.parse.quote(ig_user_id, safe='')}/media"
    data, err = _http_post_form_json_graph(url, {**params, "access_token": access_token}, timeout_sec=45)
    if err:
        return "", err
    creation_id = (data.get("id") or "").strip()
    if not creation_id:
        return "", "Instagram media container returned no creation id."
    return creation_id, ""


def _instagram_publish_container(ig_user_id: str, access_token: str, creation_id: str):
    url = f"https://graph.facebook.com/{_instagram_graph_version()}/{urllib.parse.quote(ig_user_id, safe='')}/media_publish"
    data, err = _http_post_form_json_graph(
        url,
        {"creation_id": creation_id, "access_token": access_token},
        timeout_sec=45,
    )
    if err:
        return "", err
    media_id = (data.get("id") or "").strip()
    if not media_id:
        return "", "Instagram media publish returned no media id."
    return media_id, ""


def _instagram_wait_for_container(creation_id: str, access_token: str, max_wait_seconds: int = 60):
    """Poll asynchronous Reel/carousel processing before media_publish."""
    deadline = time.monotonic() + max(5, max_wait_seconds)
    last_status = ""
    while time.monotonic() < deadline:
        query = urllib.parse.urlencode({"fields": "status_code,status", "access_token": access_token})
        url = (
            f"https://graph.facebook.com/{_instagram_graph_version()}/"
            f"{urllib.parse.quote(creation_id, safe='')}?{query}"
        )
        data, err = _http_get_json_graph(url, timeout_sec=20)
        if err:
            return err
        last_status = str(data.get("status_code") or "").upper()
        if last_status == "FINISHED":
            return ""
        if last_status in {"ERROR", "EXPIRED"}:
            return _safe_instagram_error(data.get("status") or f"Instagram container {last_status.lower()}")
        time.sleep(3)
    return f"Instagram media is still processing ({last_status or 'unknown'}). Try publishing again shortly."


def _instagram_permalink(media_id: str, access_token: str) -> str:
    if not media_id:
        return ""
    qs = urllib.parse.urlencode({"fields": "permalink", "access_token": access_token})
    url = f"https://graph.facebook.com/{_instagram_graph_version()}/{urllib.parse.quote(media_id, safe='')}?{qs}"
    data, err = _http_get_json_graph(url, timeout_sec=20)
    if err:
        print("INSTAGRAM PERMALINK FETCH ERROR:", err[:160])
        return ""
    return (data.get("permalink") or "").strip()


def _facebook_page_token(company_id: str, page_id: str):
    conn = get_db_connection()
    if not conn:
        return "", "Database error"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT access_token FROM v2_social_tokens
                WHERE company_id = %s AND provider = 'meta'
                  AND platform = 'Facebook' AND account_id = %s
                ORDER BY id DESC LIMIT 1
                """,
                (company_id, page_id),
            )
            row = cur.fetchone()
        token = (row.get("access_token") or "").strip() if row else ""
        return (token, "") if token else ("", "Facebook token missing. Reconnect Meta.")
    except Exception:
        return "", "Facebook token lookup error"
    finally:
        conn.close()


def _facebook_publish_image(page_id: str, access_token: str, image_url: str, caption: str):
    endpoint = (
        f"https://graph.facebook.com/{_instagram_graph_version()}/"
        f"{urllib.parse.quote(page_id, safe='')}/photos"
    )
    data, err = _http_post_form_json_graph(
        endpoint,
        {"url": image_url, "caption": caption, "published": "true", "access_token": access_token},
        timeout_sec=60,
    )
    if err:
        return {}, err
    object_id = str(data.get("post_id") or data.get("id") or "").strip()
    permalink = ""
    if object_id:
        query = urllib.parse.urlencode({"fields": "permalink_url", "access_token": access_token})
        details, details_err = _http_get_json_graph(
            f"https://graph.facebook.com/{_instagram_graph_version()}/{urllib.parse.quote(object_id, safe='')}?{query}",
            timeout_sec=20,
        )
        if not details_err:
            permalink = str(details.get("permalink_url") or "").strip()
    return {"id": object_id, "permalink": permalink}, ""


@app.post("/api/social/publish-static")
async def publish_static_to_meta(request: Request):
    """Publish one approved static creative to connected Facebook and Instagram accounts."""
    data = await request.json()
    company_id, user, err = resolve_company_id(
        request,
        (data.get("companyId") or "").strip(),
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    image_url = str(data.get("imageUrl") or "").strip()
    caption = str(data.get("caption") or "").strip()
    requested = data.get("platforms") or ["Facebook", "Instagram"]
    platforms = {str(x or "").strip() for x in requested}
    if _validate_instagram_public_urls([image_url]):
        return json_error("A public image URL is required", 400)
    if not caption:
        return json_error("Caption is required", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT platform, account_id, account_name
                FROM v2_social_accounts
                WHERE company_id = %s AND platform IN ('Facebook','Instagram')
                  AND status = 'connected'
                ORDER BY id DESC
                """,
                (company_id,),
            )
            accounts = cur.fetchall()
    finally:
        conn.close()

    results = {}
    for platform in ("Facebook", "Instagram"):
        if platform not in platforms:
            continue
        account = next((row for row in accounts if row.get("platform") == platform), None)
        if not account:
            results[platform] = {"success": False, "error": f"{platform} is not connected"}
            continue
        account_id = str(account.get("account_id") or "").strip()

        if platform == "Facebook":
            token, token_err = _facebook_page_token(company_id, account_id)
            if token_err:
                results[platform] = {"success": False, "error": token_err}
                continue
            published, publish_err = _facebook_publish_image(account_id, token, image_url, caption)
            results[platform] = (
                {"success": False, "error": publish_err}
                if publish_err
                else {"success": True, **published}
            )
            continue

        _account, token, token_err = _instagram_token_for_account(company_id, account_id)
        if token_err:
            results[platform] = {"success": False, "error": token_err}
            continue
        creation_id, create_err = _instagram_create_container(
            account_id, token, {"image_url": image_url, "caption": caption}
        )
        if create_err:
            results[platform] = {"success": False, "error": create_err}
            continue
        media_id, publish_err = _instagram_publish_container(account_id, token, creation_id)
        if publish_err:
            results[platform] = {"success": False, "error": publish_err}
            continue
        results[platform] = {
            "success": True,
            "id": media_id,
            "permalink": _instagram_permalink(media_id, token),
        }

    complete = bool(results) and all(item.get("success") for item in results.values())
    return JSONResponse({"success": complete, "results": results}, status_code=200 if complete else 207)


@app.post("/api/facebook/publish-reel")
async def facebook_publish_reel(request: Request):
    data = await request.json()
    company_id, user, err = resolve_company_id(
        request,
        (data.get("companyId") or "").strip(),
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)
    if data.get("confirmed") is not True:
        return json_error("Explicit confirmation is required before publishing", 400)

    video_url = str(data.get("videoUrl") or "").strip()
    title = str(data.get("title") or "").strip()[:255]
    description = str(data.get("description") or "").strip()[:5000]
    if _validate_instagram_public_urls([video_url]):
        return json_error("A public Reel URL is required", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT account_id FROM v2_social_accounts
                WHERE company_id = %s AND platform = 'Facebook' AND status = 'connected'
                ORDER BY id DESC LIMIT 1
                """,
                (company_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    page_id = str(row.get("account_id") or "").strip() if row else ""
    if not page_id:
        return json_error("Facebook Page is not connected", 400)
    token, token_err = _facebook_page_token(company_id, page_id)
    if token_err:
        return json_error(token_err, 400)

    reels_url = (
        f"https://graph.facebook.com/{_instagram_graph_version()}/"
        f"{urllib.parse.quote(page_id, safe='')}/video_reels"
    )
    started, start_err = _http_post_form_json_graph(
        reels_url, {"access_token": token, "upload_phase": "start"}, timeout_sec=45
    )
    if start_err:
        return json_error(start_err, 400)
    video_id = str(started.get("video_id") or "").strip()
    upload_url = str(started.get("upload_url") or "").strip()
    if not video_id or not upload_url.startswith("https://rupload.facebook.com/"):
        return json_error("Facebook did not return a valid Reel upload session", 502)

    upload_req = urllib.request.Request(
        upload_url,
        data=b"",
        method="POST",
        headers={
            "Authorization": f"OAuth {token}",
            "file_url": video_url,
            "User-Agent": "AI-FLOW/1.0",
        },
    )
    try:
        with urllib.request.urlopen(upload_req, timeout=90) as response:
            upload_data = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    except Exception as exc:
        return json_error(f"Facebook Reel upload failed: {type(exc).__name__}", 502)
    if upload_data.get("success") is not True:
        return json_error("Facebook did not accept the hosted Reel", 502)

    finished, finish_err = _http_post_form_json_graph(
        reels_url,
        {
            "access_token": token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": description,
            "title": title,
        },
        timeout_sec=60,
    )
    if finish_err:
        return json_error(finish_err, 400)
    return JSONResponse(
        {
            "success": finished.get("success") is True,
            "videoId": video_id,
            "message": "Facebook accepted the Reel. Check processing status before reporting it as published.",
        }
    )


@app.get("/api/facebook/reel-status")
def facebook_reel_status(request: Request, companyId: str = "", videoId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)
    video_id = str(videoId or "").strip()
    if not video_id:
        return json_error("videoId is required", 400)

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT account_id FROM v2_social_accounts
                WHERE company_id = %s AND platform = 'Facebook' AND status = 'connected'
                ORDER BY id DESC LIMIT 1
                """,
                (company_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    page_id = str(row.get("account_id") or "").strip() if row else ""
    token, token_err = _facebook_page_token(company_id, page_id)
    if token_err:
        return json_error(token_err, 400)
    query = urllib.parse.urlencode({"fields": "status,permalink_url", "access_token": token})
    details, details_err = _http_get_json_graph(
        f"https://graph.facebook.com/{_instagram_graph_version()}/{urllib.parse.quote(video_id, safe='')}?{query}",
        timeout_sec=20,
    )
    if details_err:
        return json_error(details_err, 400)
    return JSONResponse({"success": True, "videoId": video_id, "details": details})


@app.get("/api/instagram/accounts")
def instagram_accounts(request: Request, companyId: str = ""):
    company_id, err = _resolve_instagram_company(request, companyId)
    if err:
        return err

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, account_name, account_id, status, created_at, updated_at
                FROM v2_social_accounts
                WHERE company_id = %s
                AND platform = %s
                ORDER BY id DESC
                """,
                (company_id, "Instagram"),
            )
            accounts = cur.fetchall()

            cur.execute(
                """
                SELECT account_id
                FROM v2_social_tokens
                WHERE company_id = %s
                AND provider = %s
                AND platform = %s
                AND COALESCE(access_token, '') <> ''
                """,
                (company_id, "meta", "Instagram"),
            )
            token_ids = {str(r.get("account_id") or "") for r in cur.fetchall()}

        public_accounts = []
        for account in accounts:
            account_id = str(account.get("account_id") or "")
            public_accounts.append(
                {
                    "id": account.get("id"),
                    "ig_user_id": account_id,
                    "account_id": account_id,
                    "account_name": account.get("account_name") or "Instagram",
                    "status": account.get("status") or "",
                    "token_available": account_id in token_ids,
                    "created_at": account.get("created_at") or "",
                    "updated_at": account.get("updated_at") or "",
                }
            )

        return JSONResponse({"success": True, "accounts": public_accounts})
    except Exception as e:
        print("INSTAGRAM ACCOUNTS ERROR:", type(e).__name__)
        return JSONResponse({"error": "Instagram accounts error"}, status_code=500)
    finally:
        conn.close()


@app.post("/api/instagram/drafts")
async def instagram_create_draft(request: Request):
    data = await request.json()
    company_id, err = _resolve_instagram_company(request, (data.get("companyId") or "").strip())
    if err:
        return err

    ig_user_id = (data.get("ig_user_id") or data.get("igUserId") or "").strip()
    post_type = (data.get("post_type") or data.get("postType") or "").strip().lower()
    media_urls = _parse_instagram_media_urls(data.get("media_urls") or data.get("mediaUrls") or [])
    caption = (data.get("caption") or "").strip()

    if not ig_user_id:
        return JSONResponse({"error": "ig_user_id is required"}, status_code=400)

    validation_error = _validate_instagram_draft_payload(post_type, media_urls)
    if validation_error:
        return JSONResponse({"error": validation_error}, status_code=400)

    _account, _token, token_err = _instagram_token_for_account(company_id, ig_user_id)
    if token_err:
        return JSONResponse({"error": token_err}, status_code=400)

    now = _iso_z(datetime.utcnow())
    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO v2_instagram_publish_jobs (
                    company_id, provider, post_type, ig_user_id, page_id, media_urls,
                    caption, status, creation_id, media_id, permalink, error_message,
                    created_at, updated_at, published_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    company_id,
                    "instagram",
                    post_type,
                    ig_user_id,
                    "",
                    json.dumps(media_urls),
                    caption,
                    "draft",
                    "",
                    "",
                    "",
                    "",
                    now,
                    now,
                    "",
                ),
            )
            job = cur.fetchone()
        conn.commit()
        print(
            "INSTAGRAM DRAFT CREATED:",
            {"company_id": company_id, "job_id": job.get("id"), "ig_user_id": ig_user_id, "post_type": post_type},
        )
        return JSONResponse({"success": True, "job": _instagram_job_to_public(job)})
    except Exception as e:
        print("INSTAGRAM DRAFT CREATE ERROR:", type(e).__name__)
        return JSONResponse({"error": "Instagram draft create error"}, status_code=500)
    finally:
        conn.close()


@app.get("/api/instagram/jobs")
def instagram_jobs(request: Request, companyId: str = ""):
    company_id, err = _resolve_instagram_company(request, companyId)
    if err:
        return err

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_instagram_publish_jobs
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (company_id,),
            )
            rows = cur.fetchall()
        return JSONResponse({"success": True, "jobs": [_instagram_job_to_public(r) for r in rows]})
    except Exception as e:
        print("INSTAGRAM JOBS ERROR:", type(e).__name__)
        return JSONResponse({"error": "Instagram jobs error"}, status_code=500)
    finally:
        conn.close()


@app.post("/api/instagram/publish")
async def instagram_publish(request: Request):
    data = await request.json()
    company_id, err = _resolve_instagram_company(request, (data.get("companyId") or "").strip())
    if err:
        return err

    try:
        job_id = int(data.get("job_id") or data.get("jobId") or 0)
    except Exception:
        job_id = 0
    if not job_id:
        return JSONResponse({"error": "job_id is required"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_instagram_publish_jobs
                WHERE company_id = %s AND id = %s
                """,
                (company_id, job_id),
            )
            job = cur.fetchone()
    finally:
        conn.close()

    if not job:
        return JSONResponse({"error": "Instagram publish job not found"}, status_code=404)

    public_job = _instagram_job_to_public(job)
    if public_job["status"] == "published":
        return JSONResponse({"success": True, "already_published": True, "job": public_job})

    ig_user_id = public_job["ig_user_id"]
    post_type = public_job["post_type"]
    media_urls = public_job["media_urls"]
    caption = public_job["caption"]

    validation_error = _validate_instagram_draft_payload(post_type, media_urls)
    if validation_error:
        return _instagram_fail_job(company_id, job_id, validation_error, status_code=400)

    _account, access_token, token_err = _instagram_token_for_account(company_id, ig_user_id)
    if token_err:
        return _instagram_fail_job(company_id, job_id, token_err, status_code=400)

    now = _iso_z(datetime.utcnow())
    _update_instagram_job(
        company_id,
        job_id,
        status="uploading",
        error_message="",
        updated_at=now,
    )
    print(
        "INSTAGRAM PUBLISH START:",
        {"company_id": company_id, "job_id": job_id, "ig_user_id": ig_user_id, "post_type": post_type},
    )

    if post_type == "image":
        creation_id, create_err = _instagram_create_container(
            ig_user_id,
            access_token,
            {"image_url": media_urls[0], "caption": caption},
        )
        if create_err:
            return _instagram_fail_job(company_id, job_id, create_err, status_code=400)

    elif post_type == "carousel":
        child_ids = []
        for media_url in media_urls:
            child_id, child_err = _instagram_create_container(
                ig_user_id,
                access_token,
                {"image_url": media_url, "is_carousel_item": "true"},
            )
            if child_err:
                return _instagram_fail_job(company_id, job_id, child_err, status_code=400)
            child_ids.append(child_id)

        creation_id, create_err = _instagram_create_container(
            ig_user_id,
            access_token,
            {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
        )
        if create_err:
            return _instagram_fail_job(company_id, job_id, create_err, status_code=400)

    elif post_type == "reel":
        creation_id, create_err = _instagram_create_container(
            ig_user_id,
            access_token,
            {"media_type": "REELS", "video_url": media_urls[0], "caption": caption},
        )
        if create_err:
            return _instagram_fail_job(company_id, job_id, create_err, status_code=400)

    else:
        return _instagram_fail_job(company_id, job_id, "Unsupported Instagram post type.", status_code=400)

    now = _iso_z(datetime.utcnow())
    _update_instagram_job(
        company_id,
        job_id,
        status="processing",
        creation_id=creation_id,
        updated_at=now,
    )

    if post_type in {"reel", "carousel"}:
        processing_err = _instagram_wait_for_container(creation_id, access_token)
        if processing_err:
            return _instagram_fail_job(company_id, job_id, processing_err, status_code=409)

    media_id, publish_err = _instagram_publish_container(ig_user_id, access_token, creation_id)
    if publish_err:
        return _instagram_fail_job(company_id, job_id, publish_err, status_code=400)

    permalink = _instagram_permalink(media_id, access_token)
    now = _iso_z(datetime.utcnow())
    _update_instagram_job(
        company_id,
        job_id,
        status="published",
        media_id=media_id,
        permalink=permalink,
        error_message="",
        updated_at=now,
        published_at=now,
    )
    print(
        "INSTAGRAM PUBLISH SUCCESS:",
        {"company_id": company_id, "job_id": job_id, "ig_user_id": ig_user_id, "post_type": post_type, "status": "published"},
    )

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"success": True, "media_id": media_id, "permalink": permalink})
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_instagram_publish_jobs
                WHERE company_id = %s AND id = %s
                """,
                (company_id, job_id),
            )
            saved_job = cur.fetchone()
        return JSONResponse(
            {
                "success": True,
                "message": "Instagram post published successfully",
                "media_id": media_id,
                "permalink": permalink,
                "job": _instagram_job_to_public(saved_job or public_job),
            }
        )
    finally:
        conn.close()


# =========================================================
# AI MEDIA STUDIO (MVP)
# =========================================================

def _resolve_ai_media_company(request: Request, provided_company_id: str):
    company_id, user, err = resolve_company_id(
        request,
        provided_company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return "", err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return "", json_error("Forbidden", 403)
    return company_id, None


def _resolve_social_admin_company(request: Request, provided_company_id: str):
    company_id, user, err = resolve_company_id(
        request,
        provided_company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return "", err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return "", json_error("Forbidden", 403)
    return company_id, None


def _parse_json_list(value: str):
    if not value:
        return []
    try:
        obj = json.loads(value)
        if isinstance(obj, list):
            return obj
    except Exception:
        return []
    return []


def _ai_media_job_to_public(row: dict):
    if not isinstance(row, dict):
        return {}
    return {
        "id": row.get("id"),
        "company_id": row.get("company_id") or "",
        "media_type": row.get("media_type") or "",
        "prompt": row.get("prompt") or "",
        "style": row.get("style") or "",
        "format": row.get("format") or "",
        "provider": row.get("provider") or "",
        "provider_job_id": row.get("provider_job_id") or "",
        "status": row.get("status") or "",
        "public_urls": _parse_json_list(row.get("public_urls") or "[]"),
        "preview_urls": _parse_json_list(row.get("preview_urls") or "[]"),
        "caption": row.get("caption") or "",
        "reel_script": row.get("reel_script") or "",
        "error_message": row.get("error_message") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
    }


def _ai_media_base_url(request: Request) -> str:
    base = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
    if base:
        return base
    return str(request.base_url).rstrip("/")


def _ai_media_store_bytes(request: Request, company_id: str, ext: str, data: bytes) -> tuple[str, str]:
    ext = (ext or "").strip().lower()
    if not ext.startswith("."):
        ext = "." + (ext or "bin")

    rel = Path("ai") / company_id / f"{uuid.uuid4().hex}{ext}"
    abs_path = (MEDIA_DIR / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)

    public_url = _ai_media_base_url(request) + "/media/" + urllib.parse.quote(rel.as_posix(), safe="/")
    return public_url, rel.as_posix()


def _openai_api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _openai_err(data: dict, fallback: str) -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg = (err.get("message") or fallback).strip()
            if msg:
                return msg[:500]
        if isinstance(err, str) and err.strip():
            return err.strip()[:500]
    return (fallback or "OpenAI API error").strip()[:500]


def _http_post_json_openai(url: str, payload: dict, timeout_sec: int = 90):
    key = _openai_api_key()
    if not key:
        return {}, "OPENAI_API_KEY is not configured."

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "AI-FLOW/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict) and data.get("error"):
                return data, _openai_err(data, "OpenAI API error")
            return data, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return data, _openai_err(data, f"OpenAI API HTTP {e.code}")
    except Exception as e:
        return {}, f"OpenAI API request error: {type(e).__name__}"


def _multipart_form_data(fields: dict[str, str], boundary: str) -> bytes:
    lines: list[bytes] = []
    for key, value in fields.items():
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))
    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    return b"\r\n".join(lines)


def _http_post_multipart_openai(url: str, fields: dict[str, str], timeout_sec: int = 120):
    key = _openai_api_key()
    if not key:
        return {}, "OPENAI_API_KEY is not configured."

    boundary = "----AI-FLOW-" + uuid.uuid4().hex
    body = _multipart_form_data(fields, boundary)
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AI-FLOW/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict) and data.get("error"):
                return data, _openai_err(data, "OpenAI API error")
            return data, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return data, _openai_err(data, f"OpenAI API HTTP {e.code}")
    except Exception as e:
        return {}, f"OpenAI API request error: {type(e).__name__}"


def _http_get_json_openai(url: str, timeout_sec: int = 30):
    key = _openai_api_key()
    if not key:
        return {}, "OPENAI_API_KEY is not configured."
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "AI-FLOW/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if isinstance(data, dict) and data.get("error"):
                return data, _openai_err(data, "OpenAI API error")
            return data, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return data, _openai_err(data, f"OpenAI API HTTP {e.code}")
    except Exception as e:
        return {}, f"OpenAI API request error: {type(e).__name__}"


def _http_get_bytes_openai(url: str, timeout_sec: int = 180):
    key = _openai_api_key()
    if not key:
        return b"", "OPENAI_API_KEY is not configured."
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "AI-FLOW/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return resp.read(), ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return b"", _openai_err(data, f"OpenAI API HTTP {e.code}")
    except Exception as e:
        return b"", f"OpenAI API request error: {type(e).__name__}"


def _ai_media_format_to_openai_size(fmt: str) -> str:
    fmt = (fmt or "").strip()
    if fmt == "1:1":
        return "1024x1024"
    if fmt in {"4:5", "9:16"}:
        return "1024x1536"
    return "1024x1024"


def _ai_media_style_to_prompt(style: str) -> str:
    s = (style or "").strip().lower()
    if not s:
        return ""
    mapping = {
        "cinematic": "cinematic lighting, dramatic composition, shallow depth of field",
        "luxury": "luxury brand aesthetic, premium look, glossy highlights, minimal clutter",
        "viral tiktok/reels": "viral short-form style, punchy visuals, high contrast, bold text areas",
        "tech/ai": "futuristic tech/AI aesthetic, neon accents, clean UI-like shapes",
        "realistic": "photorealistic, natural textures, realistic lighting",
        "minimal": "minimalist design, clean negative space, simple shapes",
        "bold advertisement": "bold ad creative, product-focused, strong CTA space, high contrast",
    }
    return mapping.get(s, s)


def _generate_ai_caption(company_id: str, media_type: str, prompt: str, style: str) -> str:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        return ""
    try:
        client = Groq(api_key=api_key)
        sys = "You write short, high-converting Instagram captions. Output plain text only."
        user = f"""
Create an Instagram caption for:
Media type: {media_type}
Prompt: {prompt}
Style: {style}

Rules:
- write in English
- 1-3 short paragraphs
- include 3-8 hashtags at the end
- avoid emojis
"""
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=260,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _generate_reel_package(company_id: str, prompt: str, style: str, duration_seconds: int) -> str:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        return ""
    try:
        client = Groq(api_key=api_key)
        sys = "You write short Reel scripts and shot lists. Output plain text only."
        user = f"""
Create a Reel package for Instagram.

Prompt: {prompt}
Style: {style}
Duration seconds: {duration_seconds}

Return:
- Hook (1 line)
- Script (short, with timestamps or beats)
- Scene-by-scene plan (3-8 scenes)
- Suggested on-screen text
- Suggested audio/mood
- 3 image prompts for key frames

Rules:
- write in English
- avoid emojis
"""
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.7,
            max_tokens=520,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _ai_media_insert_job(
    company_id: str,
    media_type: str,
    prompt: str,
    style: str,
    fmt: str,
    provider: str,
    status: str,
):
    now = now_utc_iso()
    conn = get_db_connection()
    if not conn:
        return None, "Database error"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO v2_ai_media_jobs (
                    company_id, media_type, prompt, style, format, provider, status,
                    provider_job_id, public_urls, preview_urls, caption, reel_script, error_message,
                    created_at, updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
                """,
                (
                    company_id,
                    media_type,
                    prompt,
                    style,
                    fmt,
                    provider,
                    status,
                    "",
                    "[]",
                    "[]",
                    "",
                    "",
                    "",
                    now,
                    now,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return row, ""
    except Exception:
        return None, "AI media job create error"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _ai_media_update_job(company_id: str, job_id: int, **fields):
    if not fields:
        return
    fields = {k: v for k, v in fields.items() if v is not None}
    fields["updated_at"] = now_utc_iso()

    sets = []
    values = []
    for k, v in fields.items():
        sets.append(f"{k}=%s")
        values.append(v)
    values.extend([company_id, job_id])

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE v2_ai_media_jobs SET {', '.join(sets)} WHERE company_id=%s AND id=%s",
                tuple(values),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _ai_media_get_job(company_id: str, job_id: int):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM v2_ai_media_jobs WHERE company_id = %s AND id = %s",
                (company_id, job_id),
            )
            return cur.fetchone()
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/ai-media/jobs")
def ai_media_jobs(request: Request, companyId: str = ""):
    company_id, err = _resolve_ai_media_company(request, companyId)
    if err:
        return err

    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_ai_media_jobs
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 30
                """,
                (company_id,),
            )
            rows = cur.fetchall()

        # Best-effort refresh for in-progress OpenAI Reel video jobs (keep it bounded to avoid timeouts).
        refreshed = 0
        for row in rows or []:
            if refreshed >= 2:
                break
            if (row.get("media_type") or "") != "reel":
                continue
            if (row.get("provider") or "") != "openai":
                continue
            status = (row.get("status") or "").strip()
            if status not in {"queued", "generating", "in_progress"}:
                continue
            provider_job_id = (row.get("provider_job_id") or "").strip()
            if not provider_job_id:
                continue

            meta, meta_err = _http_get_json_openai(f"https://api.openai.com/v1/videos/{provider_job_id}", timeout_sec=25)
            if meta_err:
                continue
            v_status = (meta.get("status") or "").strip()
            if v_status in {"queued", "in_progress"}:
                _ai_media_update_job(company_id, int(row.get("id") or 0), status="generating")
                row["status"] = "generating"
                refreshed += 1
                continue
            if v_status == "failed":
                err_obj = meta.get("error") if isinstance(meta, dict) else None
                msg = ""
                if isinstance(err_obj, dict):
                    msg = (err_obj.get("message") or "").strip()
                msg = (msg or "Video generation failed.").strip()[:500]
                _ai_media_update_job(company_id, int(row.get("id") or 0), status="failed", error_message=msg)
                row["status"] = "failed"
                row["error_message"] = msg
                refreshed += 1
                continue
            if v_status == "completed":
                video_bytes, dl_err = _http_get_bytes_openai(
                    f"https://api.openai.com/v1/videos/{provider_job_id}/content",
                    timeout_sec=180,
                )
                if dl_err or not video_bytes:
                    _ai_media_update_job(company_id, int(row.get("id") or 0), status="failed", error_message=(dl_err or "Video download failed.")[:500])
                    row["status"] = "failed"
                    row["error_message"] = (dl_err or "Video download failed.")[:500]
                    refreshed += 1
                    continue

                public_url, _rel = _ai_media_store_bytes(request, company_id, ".mp4", video_bytes)
                caption = row.get("caption") or ""
                if not caption:
                    caption = _generate_ai_caption(company_id, "reel", row.get("prompt") or "", row.get("style") or "") or ""

                _ai_media_update_job(
                    company_id,
                    int(row.get("id") or 0),
                    status="completed",
                    public_urls=json.dumps([public_url]),
                    preview_urls=json.dumps([public_url]),
                    caption=caption,
                    error_message="",
                )
                row["status"] = "completed"
                row["public_urls"] = json.dumps([public_url])
                row["preview_urls"] = json.dumps([public_url])
                row["caption"] = caption
                row["error_message"] = ""
                refreshed += 1
        return JSONResponse({"success": True, "jobs": [_ai_media_job_to_public(r) for r in rows]})
    except Exception:
        return json_error("AI media jobs error", 500)
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.post("/api/ai-media/generate-image")
async def ai_media_generate_image(request: Request):
    data = await request.json()
    company_id, err = _resolve_ai_media_company(request, (data.get("companyId") or "").strip())
    if err:
        return err

    prompt = (data.get("prompt") or "").strip()
    style = (data.get("style") or "").strip()
    fmt = (data.get("format") or "").strip()
    if not prompt:
        return json_error("prompt is required", 400)
    if fmt not in {"1:1", "4:5", "9:16"}:
        return json_error("format must be 1:1, 4:5, or 9:16", 400)

    provider = "openai" if _openai_api_key() else ""
    job, job_err = _ai_media_insert_job(company_id, "image", prompt, style, fmt, provider, "generating")
    if job_err or not job:
        return json_error(job_err or "AI media job create error", 500)
    job_id = int(job.get("id") or 0)

    if not _openai_api_key():
        _ai_media_update_job(company_id, job_id, status="failed", provider="", error_message="AI image generation provider is not configured yet.")
        return JSONResponse({"success": False, "error": "AI image generation provider is not configured yet.", "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

    size = _ai_media_format_to_openai_size(fmt)
    style_hint = _ai_media_style_to_prompt(style)
    full_prompt = prompt if not style_hint else (prompt + "\nStyle: " + style_hint)
    model = (os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip() or "gpt-image-1"
    quality = (os.getenv("OPENAI_IMAGE_QUALITY") or "medium").strip() or "medium"

    data_img, img_err = _http_post_json_openai(
        "https://api.openai.com/v1/images/generations",
        {"model": model, "prompt": full_prompt, "n": 1, "size": size, "quality": quality, "output_format": "png"},
        timeout_sec=120,
    )
    if img_err:
        _ai_media_update_job(company_id, job_id, status="failed", error_message=img_err)
        print("AI_MEDIA_IMAGE_FAILED:", {"company_id": company_id, "job_id": job_id, "provider": provider})
        return JSONResponse({"success": False, "error": img_err, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

    items = data_img.get("data") if isinstance(data_img, dict) else None
    b64 = ""
    if isinstance(items, list) and items:
        b64 = (items[0] or {}).get("b64_json") or ""
    if not b64:
        err_msg = "Image generation returned no image data."
        _ai_media_update_job(company_id, job_id, status="failed", error_message=err_msg)
        return JSONResponse({"success": False, "error": err_msg, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

    try:
        img_bytes = base64.b64decode(b64)
    except Exception:
        err_msg = "Image decode failed."
        _ai_media_update_job(company_id, job_id, status="failed", error_message=err_msg)
        return JSONResponse({"success": False, "error": err_msg, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

    public_url, _rel = _ai_media_store_bytes(request, company_id, ".png", img_bytes)
    caption = _generate_ai_caption(company_id, "image", prompt, style) or ""
    _ai_media_update_job(
        company_id,
        job_id,
        status="completed",
        provider=provider,
        public_urls=json.dumps([public_url]),
        preview_urls=json.dumps([public_url]),
        caption=caption,
        error_message="",
    )
    print("AI_MEDIA_IMAGE_OK:", {"company_id": company_id, "job_id": job_id, "provider": provider, "status": "completed"})
    saved = _ai_media_get_job(company_id, job_id) or job
    return JSONResponse({"success": True, "job": _ai_media_job_to_public(saved)})


@app.post("/api/ai-media/generate-carousel")
async def ai_media_generate_carousel(request: Request):
    data = await request.json()
    company_id, err = _resolve_ai_media_company(request, (data.get("companyId") or "").strip())
    if err:
        return err

    prompt = (data.get("prompt") or "").strip()
    style = (data.get("style") or "").strip()
    fmt = (data.get("format") or "").strip()
    slide_count = data.get("slide_count") or data.get("slideCount") or 5
    try:
        slide_count = int(slide_count)
    except Exception:
        slide_count = 5
    slide_count = max(3, min(10, slide_count))

    if not prompt:
        return json_error("prompt is required", 400)
    if fmt not in {"1:1", "4:5"}:
        return json_error("format must be 1:1 or 4:5", 400)

    provider = "openai" if _openai_api_key() else ""
    job, job_err = _ai_media_insert_job(company_id, "carousel", prompt, style, fmt, provider, "generating")
    if job_err or not job:
        return json_error(job_err or "AI media job create error", 500)
    job_id = int(job.get("id") or 0)

    if not _openai_api_key():
        _ai_media_update_job(company_id, job_id, status="failed", provider="", error_message="AI image generation provider is not configured yet.")
        return JSONResponse({"success": False, "error": "AI image generation provider is not configured yet.", "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

    size = _ai_media_format_to_openai_size(fmt)
    style_hint = _ai_media_style_to_prompt(style)
    model = (os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip() or "gpt-image-1"
    quality = (os.getenv("OPENAI_IMAGE_QUALITY") or "medium").strip() or "medium"

    public_urls = []
    for i in range(slide_count):
        slide_prompt = f"{prompt}\nSlide {i+1} of {slide_count}.\nKeep consistent visual style.\n"
        if style_hint:
            slide_prompt += "Style: " + style_hint

        data_img, img_err = _http_post_json_openai(
            "https://api.openai.com/v1/images/generations",
            {"model": model, "prompt": slide_prompt, "n": 1, "size": size, "quality": quality, "output_format": "png"},
            timeout_sec=140,
        )
        if img_err:
            _ai_media_update_job(company_id, job_id, status="failed", error_message=img_err)
            print("AI_MEDIA_CAROUSEL_FAILED:", {"company_id": company_id, "job_id": job_id, "provider": provider})
            return JSONResponse({"success": False, "error": img_err, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

        items = data_img.get("data") if isinstance(data_img, dict) else None
        b64 = ""
        if isinstance(items, list) and items:
            b64 = (items[0] or {}).get("b64_json") or ""
        if not b64:
            img_err = "Image generation returned no image data."
            _ai_media_update_job(company_id, job_id, status="failed", error_message=img_err)
            return JSONResponse({"success": False, "error": img_err, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})
        try:
            img_bytes = base64.b64decode(b64)
        except Exception:
            img_err = "Image decode failed."
            _ai_media_update_job(company_id, job_id, status="failed", error_message=img_err)
            return JSONResponse({"success": False, "error": img_err, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})

        url, _rel = _ai_media_store_bytes(request, company_id, ".png", img_bytes)
        public_urls.append(url)

    caption = _generate_ai_caption(company_id, "carousel", prompt, style) or ""
    _ai_media_update_job(
        company_id,
        job_id,
        status="completed",
        provider=provider,
        public_urls=json.dumps(public_urls),
        preview_urls=json.dumps(public_urls),
        caption=caption,
        error_message="",
    )
    print("AI_MEDIA_CAROUSEL_OK:", {"company_id": company_id, "job_id": job_id, "provider": provider, "status": "completed"})
    saved = _ai_media_get_job(company_id, job_id) or job
    return JSONResponse({"success": True, "job": _ai_media_job_to_public(saved)})


@app.post("/api/ai-media/generate-reel")
async def ai_media_generate_reel(request: Request):
    data = await request.json()
    company_id, err = _resolve_ai_media_company(request, (data.get("companyId") or "").strip())
    if err:
        return err

    prompt = (data.get("prompt") or "").strip()
    style = (data.get("style") or "").strip()
    fmt = (data.get("format") or "").strip()
    duration_seconds = data.get("duration_seconds") or data.get("durationSeconds") or 8
    try:
        duration_seconds = int(duration_seconds)
    except Exception:
        duration_seconds = 8
    duration_seconds = max(5, min(30, duration_seconds))

    if not prompt:
        return json_error("prompt is required", 400)
    if fmt != "9:16":
        return json_error("format must be 9:16", 400)

    provider = "openai" if _openai_api_key() else ""
    job, job_err = _ai_media_insert_job(company_id, "reel", prompt, style, fmt, provider, "generating")
    if job_err or not job:
        return json_error(job_err or "AI media job create error", 500)
    job_id = int(job.get("id") or 0)

    # If OpenAI is configured, attempt real video generation. Otherwise, generate a Reel package only.
    if not _openai_api_key():
        script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
        msg = "AI Reel video generation provider is not configured yet. Connect a video generation provider to generate MP4 files."
        _ai_media_update_job(
            company_id,
            job_id,
            status="completed",
            provider="",
            public_urls="[]",
            preview_urls="[]",
            reel_script=(script + ("\n\n" + msg if msg else "")),
            error_message="",
        )
        return JSONResponse({"success": True, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job), "warning": msg})

    # OpenAI Sora video generation (best-effort, may remain in_progress and require polling).
    model = (os.getenv("OPENAI_VIDEO_MODEL") or "sora-2").strip() or "sora-2"
    size = (os.getenv("OPENAI_VIDEO_SIZE") or "720x1280").strip() or "720x1280"
    # Map requested duration to supported values (4/8/12).
    if duration_seconds <= 6:
        seconds = "4"
    elif duration_seconds <= 10:
        seconds = "8"
    else:
        seconds = "12"

    video_job, v_err = _http_post_multipart_openai(
        "https://api.openai.com/v1/videos",
        {"model": model, "prompt": prompt, "seconds": seconds, "size": size},
        timeout_sec=120,
    )
    if v_err:
        script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
        _ai_media_update_job(company_id, job_id, status="completed", provider="openai", reel_script=script, error_message=v_err)
        print("AI_MEDIA_REEL_VIDEO_FAILED:", {"company_id": company_id, "job_id": job_id, "provider": provider})
        return JSONResponse({"success": True, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job), "warning": v_err})

    openai_video_id = (video_job.get("id") or "").strip()
    if not openai_video_id:
        script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
        msg = "Video generation did not return a video id."
        _ai_media_update_job(company_id, job_id, status="completed", provider="openai", reel_script=script, error_message=msg)
        return JSONResponse({"success": True, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job), "warning": msg})

    _ai_media_update_job(company_id, job_id, provider="openai", provider_job_id=openai_video_id)

    # Poll briefly for completion (so users sometimes get instant preview); otherwise rely on /api/ai-media/jobs polling.
    status = (video_job.get("status") or "").strip()
    for _ in range(10):
        if status == "completed":
            break
        if status in {"failed", "canceled"}:
            break
        meta, meta_err = _http_get_json_openai(f"https://api.openai.com/v1/videos/{openai_video_id}", timeout_sec=30)
        if meta_err:
            break
        status = (meta.get("status") or "").strip()
        if status in {"queued", "in_progress"}:
            try:
                import time
                time.sleep(2)
            except Exception:
                break

    if status != "completed":
        script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
        _ai_media_update_job(
            company_id,
            job_id,
            status="generating",
            provider="openai",
            provider_job_id=openai_video_id,
            reel_script=script,
            error_message="",
        )
        return JSONResponse(
            {
                "success": True,
                "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job),
                "video_status": status or "generating",
                "openai_video_id": openai_video_id,
                "warning": "Video generation is in progress. Refresh AI Media Studio jobs to fetch the MP4 when ready.",
            }
        )

    video_bytes, dl_err = _http_get_bytes_openai(f"https://api.openai.com/v1/videos/{openai_video_id}/content", timeout_sec=240)
    if dl_err or not video_bytes:
        script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
        _ai_media_update_job(company_id, job_id, status="completed", provider="openai", reel_script=script, error_message=dl_err or "Video download failed.")
        return JSONResponse({"success": True, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job), "warning": dl_err or "Video download failed."})

    public_url, _rel = _ai_media_store_bytes(request, company_id, ".mp4", video_bytes)
    caption = _generate_ai_caption(company_id, "reel", prompt, style) or ""
    script = _generate_reel_package(company_id, prompt, style, duration_seconds) or ""
    _ai_media_update_job(
        company_id,
        job_id,
        status="completed",
        provider="openai",
        provider_job_id=openai_video_id,
        public_urls=json.dumps([public_url]),
        preview_urls=json.dumps([public_url]),
        caption=caption,
        reel_script=script,
        error_message="",
    )
    print("AI_MEDIA_REEL_OK:", {"company_id": company_id, "job_id": job_id, "provider": provider, "status": "completed"})
    return JSONResponse({"success": True, "job": _ai_media_job_to_public(_ai_media_get_job(company_id, job_id) or job)})


# =========================================================
# TIKTOK OAUTH (MVP)
# =========================================================

@app.get("/tiktok-connect-url")
def tiktok_connect_url(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_admin_company(request, companyId)
    if err:
        return err

    client_key, client_secret, redirect_uri = _tiktok_config()
    config_issue = _tiktok_config_issue(client_key, client_secret, redirect_uri)
    if config_issue:
        print(
            "TIKTOK OAUTH CONFIG ERROR:",
            {
                "issue": config_issue,
                "client_key_present": bool(client_key),
                "client_key_mask": _mask_value(client_key),
                "client_secret_present": bool(client_secret),
                "redirect_uri": redirect_uri,
            },
        )
        return JSONResponse(
            {
                "success": False,
                "error": "TikTok OAuth is not configured",
                "detail": config_issue,
            },
            status_code=500,
        )

    # Prefix companyId for older TikTok diagnostics; signed payload remains the trusted source.
    state = _create_oauth_state("tiktok", company_id, include_company_prefix=True)
    state_error = _store_oauth_state_in_db("tiktok", state, company_id)
    if state_error:
        return JSONResponse({"success": False, "error": state_error}, status_code=500)
    _store_oauth_state_in_session(request, "tiktok", state, company_id)

    auth_url = _build_tiktok_authorize_url(
        client_key,
        redirect_uri,
        state,
        scope="user.info.basic,video.upload,video.publish",
    )

    return JSONResponse({"success": True, "auth_url": auth_url, "url": auth_url})


@app.get("/tiktok-oauth-preflight")
def tiktok_oauth_preflight(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_admin_company(request, companyId)
    if err:
        return err

    client_key, client_secret, redirect_uri = _tiktok_config()
    config_issue = _tiktok_config_issue(client_key, client_secret, redirect_uri)

    warnings = []
    if not config_issue:
        warnings.append("Ensure this exact redirect URI is configured in TikTok Developer Portal Login Kit.")
        warnings.append("If app is in Development mode, login with a whitelisted test user.")
        warnings.append("Use Client Key from the same TikTok app as this redirect URI.")

    return JSONResponse(
        {
            "success": not bool(config_issue),
            "configured": not bool(config_issue),
            "detail": config_issue or "",
            "client_key_present": bool(client_key),
            "client_key_mask": _mask_value(client_key),
            "client_key_len": len(client_key),
            "client_secret_present": bool(client_secret),
            "client_secret_mask": _mask_value(client_secret),
            "client_secret_len": len(client_secret),
            "are_equal": bool(client_key and client_secret and (client_key == client_secret)),
            "redirect_uri": redirect_uri,
            "warnings": warnings,
        },
        status_code=200 if not config_issue else 500,
    )


@app.get("/tiktok-oauth-callback")
def tiktok_oauth_callback(request: Request, code: str = "", state: str = ""):
    if not code or not state:
        return JSONResponse({"error": "Missing code/state"}, status_code=400)

    client_key, client_secret, redirect_uri = _tiktok_config()
    config_issue = _tiktok_config_issue(client_key, client_secret, redirect_uri)
    if config_issue:
        print(
            "TIKTOK OAUTH CALLBACK CONFIG ERROR:",
            {
                "issue": config_issue,
                "client_key_present": bool(client_key),
                "client_key_mask": _mask_value(client_key),
                "client_secret_present": bool(client_secret),
                "redirect_uri": redirect_uri,
            },
        )
        return JSONResponse({"error": "TikTok OAuth is not configured"}, status_code=500)

    company_id, state_error = _resolve_oauth_company_from_state(request, "tiktok", state)
    if state_error and state_error != "Invalid state":
        return JSONResponse({"error": state_error}, status_code=500)
    if not company_id:
        return JSONResponse({"error": "Invalid state"}, status_code=400)

    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    try:
        token_data = _http_post_form_json(
            token_url,
            {
                "client_key": client_key,
                "client_secret": client_secret,
                "code": urllib.parse.unquote(code),
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
    except Exception as e:
        print("TIKTOK TOKEN EXCHANGE ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok token exchange error"}, status_code=500)

    access_token = (token_data.get("access_token") or "").strip()
    refresh_token = (token_data.get("refresh_token") or "").strip()
    open_id = (token_data.get("open_id") or "").strip()
    scope = (token_data.get("scope") or "").strip()
    expires_in = token_data.get("expires_in")
    refresh_expires_in = token_data.get("refresh_expires_in")

    if not access_token or not open_id:
        detail = {
            "error": token_data.get("error"),
            "error_description": token_data.get("error_description"),
            "log_id": token_data.get("log_id"),
        }
        return JSONResponse(
            {"error": "TikTok token exchange failed", "detail": detail},
            status_code=500,
        )

    expires_at = ""
    refresh_expires_at = ""
    try:
        if expires_in is not None:
            expires_at = _iso_z(datetime.utcnow() + timedelta(seconds=int(expires_in)))
        if refresh_expires_in is not None:
            refresh_expires_at = _iso_z(datetime.utcnow() + timedelta(seconds=int(refresh_expires_in)))
    except Exception:
        expires_at = ""
        refresh_expires_at = ""

    display_name = "TikTok Account"
    try:
        user_info_url = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,avatar_url"
        req = urllib.request.Request(
            user_info_url,
            method="GET",
            headers={"User-Agent": "AI-FLOW/1.0", "Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            user_data = json.loads(raw)
            data_obj = user_data.get("data") or {}
            user_obj = data_obj.get("user") or {}
            display_name = (user_obj.get("display_name") or "").strip() or display_name
    except Exception as e:
        print("TIKTOK USER INFO ERROR:", type(e).__name__)

    now = _iso_z(datetime.utcnow())

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            # Keep existing social account/token storage.
            cur.execute(
                "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s",
                (company_id, "TikTok"),
            )
            cur.execute(
                """
                INSERT INTO v2_social_accounts (company_id, platform, status, account_name, account_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (company_id, "TikTok", "connected", display_name, open_id, now, now),
            )

            cur.execute(
                """
                INSERT INTO v2_social_tokens (company_id, provider, platform, account_id, access_token, token_expires_at, refresh_token, refresh_expires_at, scope, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, provider, platform, account_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    refresh_token = EXCLUDED.refresh_token,
                    refresh_expires_at = EXCLUDED.refresh_expires_at,
                    scope = EXCLUDED.scope,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    company_id,
                    "tiktok",
                    "TikTok",
                    open_id,
                    access_token,
                    expires_at,
                    refresh_token,
                    refresh_expires_at,
                    scope,
                    now,
                    now,
                ),
            )

            # New dedicated TikTok account store (foundation for future publishing).
            cur.execute(
                """
                INSERT INTO v2_tiktok_accounts (
                    company_id,
                    tiktok_open_id,
                    username,
                    access_token,
                    refresh_token,
                    expires_in,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, tiktok_open_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_in = EXCLUDED.expires_in,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    company_id,
                    open_id,
                    display_name,
                    access_token,
                    refresh_token,
                    str(expires_in) if expires_in is not None else "",
                    "connected",
                    now,
                    now,
                ),
            )

        conn.commit()

    except Exception as e:
        print("TIKTOK CALLBACK DB ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok callback save error"}, status_code=500)

    finally:
        conn.close()

    return RedirectResponse(url="/social-accounts?connected=tiktok", status_code=302)


@app.get("/tiktok-accounts")
def tiktok_accounts(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, company_id, tiktok_open_id, username, status, created_at, updated_at
                FROM v2_tiktok_accounts
                WHERE company_id = %s
                ORDER BY id DESC
                """,
                (company_id,),
            )
            accounts = cur.fetchall()

        return JSONResponse({"success": True, "accounts": accounts})

    except Exception as e:
        print("TIKTOK ACCOUNTS ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok accounts error"}, status_code=500)

    finally:
        conn.close()


@app.get("/api/tiktok/connect")
def tiktok_connect(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_admin_company(request, companyId)
    if err:
        return err

    client_key, client_secret, redirect_uri = _tiktok_config()
    config_issue = _tiktok_config_issue(client_key, client_secret, redirect_uri)
    if config_issue:
        print(
            "TIKTOK OAUTH CONFIG ERROR (LEGACY CONNECT):",
            {
                "issue": config_issue,
                "client_key_present": bool(client_key),
                "client_key_mask": _mask_value(client_key),
                "client_secret_present": bool(client_secret),
                "redirect_uri": redirect_uri,
            },
        )
        return JSONResponse(
            {
                "success": False,
                "error": "TikTok OAuth is not configured",
                "detail": config_issue,
            },
            status_code=500,
        )

    state = _create_oauth_state("tiktok", company_id, include_company_prefix=True)
    state_error = _store_oauth_state_in_db("tiktok", state, company_id)
    if state_error:
        return JSONResponse({"success": False, "error": state_error}, status_code=500)
    _store_oauth_state_in_session(request, "tiktok", state, company_id)

    auth_url = _build_tiktok_authorize_url(client_key, redirect_uri, state, scope="user.info.basic")

    return HTMLResponse(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={auth_url}"></head>
<body style="font-family:Arial,sans-serif;background:#061923;color:#f7fbff;padding:24px;">
Redirecting to TikTok OAuth...
</body></html>"""
    )


@app.get("/api/tiktok/callback")
def tiktok_callback(request: Request, code: str = "", state: str = ""):
    if not code or not state:
        return JSONResponse({"error": "Missing code/state"}, status_code=400)

    client_key, client_secret, redirect_uri = _tiktok_config()
    config_issue = _tiktok_config_issue(client_key, client_secret, redirect_uri)
    if config_issue:
        print(
            "TIKTOK OAUTH CALLBACK CONFIG ERROR (LEGACY):",
            {
                "issue": config_issue,
                "client_key_present": bool(client_key),
                "client_key_mask": _mask_value(client_key),
                "client_secret_present": bool(client_secret),
                "redirect_uri": redirect_uri,
            },
        )
        return JSONResponse({"error": "TikTok OAuth is not configured"}, status_code=500)

    company_id, state_error = _resolve_oauth_company_from_state(request, "tiktok", state)
    if state_error and state_error != "Invalid state":
        return JSONResponse({"error": state_error}, status_code=500)
    if not company_id:
        return JSONResponse({"error": "Invalid state"}, status_code=400)

    # Exchange code -> access token
    token_url = "https://open.tiktokapis.com/v2/oauth/token/"
    try:
        token_data = _http_post_form_json(
            token_url,
            {
                "client_key": client_key,
                "client_secret": client_secret,
                "code": urllib.parse.unquote(code),
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
    except Exception as e:
        print("TIKTOK TOKEN EXCHANGE ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok token exchange error"}, status_code=500)

    access_token = (token_data.get("access_token") or "").strip()
    refresh_token = (token_data.get("refresh_token") or "").strip()
    open_id = (token_data.get("open_id") or "").strip()
    scope = (token_data.get("scope") or "").strip()
    expires_in = token_data.get("expires_in")
    refresh_expires_in = token_data.get("refresh_expires_in")

    if not access_token or not open_id:
        detail = {
            "error": token_data.get("error"),
            "error_description": token_data.get("error_description"),
            "log_id": token_data.get("log_id"),
        }
        return JSONResponse(
            {"error": "TikTok token exchange failed", "detail": detail},
            status_code=500,
        )

    expires_at = ""
    refresh_expires_at = ""
    try:
        if expires_in is not None:
            expires_at = _iso_z(datetime.utcnow() + timedelta(seconds=int(expires_in)))
        if refresh_expires_in is not None:
            refresh_expires_at = _iso_z(datetime.utcnow() + timedelta(seconds=int(refresh_expires_in)))
    except Exception:
        expires_at = ""
        refresh_expires_at = ""

    # Fetch basic user info (display name)
    display_name = "TikTok Account"
    try:
        user_info_url = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,avatar_url"
        req = urllib.request.Request(
            user_info_url,
            method="GET",
            headers={"User-Agent": "AI-FLOW/1.0", "Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            user_data = json.loads(raw)
            data_obj = user_data.get("data") or {}
            user_obj = data_obj.get("user") or {}
            display_name = (user_obj.get("display_name") or "").strip() or display_name
    except Exception as e:
        print("TIKTOK USER INFO ERROR:", type(e).__name__)

    now = _iso_z(datetime.utcnow())

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            # Save account info
            cur.execute(
                "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s",
                (company_id, "TikTok"),
            )
            cur.execute(
                """
                INSERT INTO v2_social_accounts (company_id, platform, status, account_name, account_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (company_id, "TikTok", "connected", display_name, open_id, now, now),
            )

            # Save tokens (server-side only)
            cur.execute(
                """
                INSERT INTO v2_social_tokens (company_id, provider, platform, account_id, access_token, token_expires_at, refresh_token, refresh_expires_at, scope, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, provider, platform, account_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    refresh_token = EXCLUDED.refresh_token,
                    refresh_expires_at = EXCLUDED.refresh_expires_at,
                    scope = EXCLUDED.scope,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    company_id,
                    "tiktok",
                    "TikTok",
                    open_id,
                    access_token,
                    expires_at,
                    refresh_token,
                    refresh_expires_at,
                    scope,
                    now,
                    now,
                ),
            )

        conn.commit()
    except Exception as e:
        print("TIKTOK CALLBACK DB ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok callback save error"}, status_code=500)
    finally:
        conn.close()

    return HTMLResponse(
        """<!doctype html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#061923;color:#f7fbff;padding:24px;">
Connected. You can close this tab.
<script>window.location.href='/social-accounts?tiktok=connected';</script>
</body></html>"""
    )


@app.get("/api/tiktok/account")
def tiktok_account(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT platform, status, account_name, account_id, created_at, updated_at
                FROM v2_social_accounts
                WHERE company_id = %s
                AND platform = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (company_id, "TikTok"),
            )
            account = cur.fetchone()

        return JSONResponse({"success": True, "account": account})
    except Exception as e:
        print("TIKTOK ACCOUNT ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok account error"}, status_code=500)
    finally:
        conn.close()


def _tiktok_company_token(company_id: str):
    conn = get_db_connection()
    if not conn:
        return "", "", "Database error"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT access_token, scope
                FROM v2_social_tokens
                WHERE company_id = %s AND provider = 'tiktok'
                ORDER BY id DESC LIMIT 1
                """,
                (company_id,),
            )
            row = cur.fetchone()
        if not row or not (row.get("access_token") or "").strip():
            return "", "", "TikTok is not connected"
        return (row.get("access_token") or "").strip(), (row.get("scope") or "").strip(), ""
    except Exception:
        return "", "", "TikTok token lookup error"
    finally:
        conn.close()


def _tiktok_post_json(path: str, access_token: str, payload: dict):
    url = "https://open.tiktokapis.com" + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "AI-FLOW/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw or "{}")
        except Exception:
            data = {}
        return data, f"TikTok API HTTP {exc.code}"
    except Exception as exc:
        return {}, f"TikTok API request error: {type(exc).__name__}"
    error = data.get("error") or {}
    code = str(error.get("code") or "ok")
    if code not in {"", "ok"}:
        return data, str(error.get("message") or code)[:500]
    return data, ""


def _resolve_tiktok_write_company(request: Request, provided_company_id: str):
    company_id, user, err = resolve_company_id(
        request, provided_company_id, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return "", err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return "", json_error("Forbidden", 403)
    return company_id, None


@app.get("/api/tiktok/creator-info")
def tiktok_creator_info(request: Request, companyId: str = ""):
    company_id, err = _resolve_tiktok_write_company(request, companyId)
    if err:
        return err
    token, scope, token_err = _tiktok_company_token(company_id)
    if token_err:
        return json_error(token_err, 400)
    if "video.publish" not in scope:
        return json_error("Reconnect TikTok and grant video.publish", 400)
    data, api_err = _tiktok_post_json("/v2/post/publish/creator_info/query/", token, {})
    if api_err:
        return JSONResponse({"error": api_err, "detail": data.get("error") or {}}, status_code=400)
    return JSONResponse({"success": True, "creator": data.get("data") or {}})


@app.post("/api/tiktok/publish-photo")
async def tiktok_publish_photo(request: Request):
    data = await request.json()
    company_id, err = _resolve_tiktok_write_company(
        request, (data.get("companyId") or "").strip()
    )
    if err:
        return err
    if data.get("confirmed") is not True:
        return json_error("Explicit confirmation is required before posting to TikTok", 400)

    photo_url = str(data.get("photoUrl") or "").strip()
    title = str(data.get("title") or "").strip()[:90]
    description = str(data.get("description") or "").strip()[:2200]
    privacy_level = str(data.get("privacyLevel") or "SELF_ONLY").strip()
    if _validate_instagram_public_urls([photo_url]):
        return json_error("A public photo URL is required", 400)

    token, scope, token_err = _tiktok_company_token(company_id)
    if token_err:
        return json_error(token_err, 400)
    if "video.publish" not in scope:
        return json_error("Reconnect TikTok and grant video.publish", 400)

    creator_response, creator_err = _tiktok_post_json(
        "/v2/post/publish/creator_info/query/", token, {}
    )
    if creator_err:
        return JSONResponse({"error": creator_err, "detail": creator_response.get("error") or {}}, status_code=400)
    creator = creator_response.get("data") or {}
    allowed_privacy = creator.get("privacy_level_options") or []
    if privacy_level not in allowed_privacy:
        return JSONResponse(
            {
                "error": "Selected TikTok privacy level is unavailable",
                "allowedPrivacyLevels": allowed_privacy,
            },
            status_code=400,
        )

    payload = {
        "post_info": {
            "title": title,
            "description": description,
            "disable_comment": bool(data.get("disableComment", False)),
            "privacy_level": privacy_level,
            "auto_add_music": bool(data.get("autoAddMusic", False)),
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_cover_index": 0,
            "photo_images": [photo_url],
        },
        "post_mode": "DIRECT_POST",
        "media_type": "PHOTO",
    }
    published, publish_err = _tiktok_post_json("/v2/post/publish/content/init/", token, payload)
    if publish_err:
        return JSONResponse({"error": publish_err, "detail": published.get("error") or {}}, status_code=400)
    publish_id = str((published.get("data") or {}).get("publish_id") or "").strip()
    return JSONResponse(
        {
            "success": bool(publish_id),
            "publishId": publish_id,
            "message": "TikTok is processing the post. Check publish status before reporting success.",
        }
    )


@app.post("/api/tiktok/publish-video")
async def tiktok_publish_video(request: Request):
    data = await request.json()
    company_id, err = _resolve_tiktok_write_company(
        request, (data.get("companyId") or "").strip()
    )
    if err:
        return err
    if data.get("confirmed") is not True:
        return json_error("Explicit confirmation is required before posting to TikTok", 400)

    video_url = str(data.get("videoUrl") or "").strip()
    title = str(data.get("title") or "").strip()[:2200]
    privacy_level = str(data.get("privacyLevel") or "SELF_ONLY").strip()
    if _validate_instagram_public_urls([video_url]):
        return json_error("A public video URL is required", 400)

    token, scope, token_err = _tiktok_company_token(company_id)
    if token_err:
        return json_error(token_err, 400)
    if "video.publish" not in scope:
        return json_error("Reconnect TikTok and grant video.publish", 400)

    creator_response, creator_err = _tiktok_post_json(
        "/v2/post/publish/creator_info/query/", token, {}
    )
    if creator_err:
        return JSONResponse({"error": creator_err, "detail": creator_response.get("error") or {}}, status_code=400)
    creator = creator_response.get("data") or {}
    allowed_privacy = creator.get("privacy_level_options") or []
    if privacy_level not in allowed_privacy:
        return JSONResponse(
            {"error": "Selected TikTok privacy level is unavailable", "allowedPrivacyLevels": allowed_privacy},
            status_code=400,
        )

    payload = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": bool(data.get("disableDuet", False)),
            "disable_comment": bool(data.get("disableComment", False)),
            "disable_stitch": bool(data.get("disableStitch", False)),
            "video_cover_timestamp_ms": int(data.get("videoCoverTimestampMs") or 1000),
        },
        "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
    }
    published, publish_err = _tiktok_post_json("/v2/post/publish/video/init/", token, payload)
    if publish_err:
        return JSONResponse({"error": publish_err, "detail": published.get("error") or {}}, status_code=400)
    publish_id = str((published.get("data") or {}).get("publish_id") or "").strip()
    return JSONResponse(
        {
            "success": bool(publish_id),
            "publishId": publish_id,
            "message": "TikTok is processing the video. Check publish status before reporting success.",
        }
    )


@app.post("/api/tiktok/publish-status")
async def tiktok_publish_status(request: Request):
    data = await request.json()
    company_id, err = _resolve_tiktok_write_company(
        request, (data.get("companyId") or "").strip()
    )
    if err:
        return err
    publish_id = str(data.get("publishId") or "").strip()
    if not publish_id:
        return json_error("publishId is required", 400)
    token, scope, token_err = _tiktok_company_token(company_id)
    if token_err:
        return json_error(token_err, 400)
    result, api_err = _tiktok_post_json(
        "/v2/post/publish/status/fetch/", token, {"publish_id": publish_id}
    )
    if api_err:
        return JSONResponse({"error": api_err, "detail": result.get("error") or {}}, status_code=400)
    return JSONResponse({"success": True, "status": result.get("data") or {}})


@app.post("/api/tiktok/disconnect")
async def tiktok_disconnect(request: Request):
    data = await request.json()
    company_id = (data.get("companyId") or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM v2_social_tokens WHERE company_id = %s AND provider = %s",
                (company_id, "tiktok"),
            )
            cur.execute(
                "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s",
                (company_id, "TikTok"),
            )
            cur.execute(
                "DELETE FROM v2_tiktok_accounts WHERE company_id = %s",
                (company_id,),
            )
        conn.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        print("TIKTOK DISCONNECT ERROR:", type(e).__name__)
        return JSONResponse({"error": "TikTok disconnect error"}, status_code=500)
    finally:
        conn.close()


# =========================================================
# BOOKINGS / CALENDAR
# =========================================================

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
GOOGLE_ACCOUNT_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]


def _google_oauth_client_config(redirect_uri: str):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret or not redirect_uri:
        return None
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def _google_account_flow(state: str = ""):
    redirect_uri = (
        os.getenv("GOOGLE_AUTH_REDIRECT_URI")
        or os.getenv("GOOGLE_REDIRECT_URI")
        or ""
    ).strip()
    config = _google_oauth_client_config(redirect_uri)
    if not config:
        return None
    return Flow.from_client_config(
        config,
        scopes=GOOGLE_ACCOUNT_SCOPES,
        redirect_uri=redirect_uri,
        state=state or None,
    )


def _google_user_info(access_token: str):
    req = urllib.request.Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _google_browser_login_response(request: Request, email: str, role: str, company_id: str, user_id: int, target: str):
    request.session.clear()
    request.session["user_id"] = int(user_id)
    request.session["email"] = email
    request.session["role"] = role
    request.session["company_id"] = company_id

    remember_token = secrets.token_urlsafe(48)
    remember_hash = hashlib.sha256(remember_token.encode("utf-8")).hexdigest()
    remember_expires = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_auth_sessions (user_id, token_hash, expires_at, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (int(user_id), remember_hash, remember_expires, now_utc_iso()),
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("GOOGLE LOGIN SESSION ERROR:", type(e).__name__)
        finally:
            conn.close()

    safe_target = target if target in {"/dashboard", "/onboarding", "/calendar", "/social-accounts"} else "/dashboard"
    html = f"""<!doctype html><html><body><script>
localStorage.setItem('ai_flow_email', {json.dumps(email)});
localStorage.setItem('ai_flow_role', {json.dumps(role)});
localStorage.setItem('ai_flow_company_id', {json.dumps(company_id)});
window.location.replace({json.dumps(safe_target)});
</script></body></html>"""
    response = HTMLResponse(html)
    response.set_cookie(
        key="ai_flow_remember",
        value=remember_token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@app.get("/auth/google")
def google_account_login(request: Request, next: str = "/dashboard"):
    flow = _google_account_flow()
    if not flow:
        return json_error("Google OAuth is not configured", 503)
    current_user = get_session_user(request) or {}
    company_hint = (current_user.get("company_id") or "new_google_user").strip()
    state = _create_oauth_state("google_account", company_hint)
    request.session["google_account_state"] = state
    request.session["google_account_next"] = next if next.startswith("/") else "/dashboard"
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return RedirectResponse(authorization_url, status_code=302)


@app.get("/google/callback")
@app.get("/auth/google/callback")
def google_account_callback(request: Request, code: str = "", state: str = ""):
    expected_state = request.session.get("google_account_state") or ""
    if not code or not state or not hmac.compare_digest(state, expected_state):
        return json_error("Invalid Google OAuth state", 400)
    _company_hint, state_error = _verify_signed_oauth_state(state, "google_account")
    if state_error:
        return json_error("Invalid or expired Google OAuth state", 400)
    flow = _google_account_flow(state)
    if not flow:
        return json_error("Google OAuth is not configured", 503)

    try:
        flow.fetch_token(code=code)
        info = _google_user_info(flow.credentials.token)
        email = (info.get("email") or "").strip().lower()
        if not email or info.get("email_verified") is not True:
            return json_error("Google email is not verified", 403)

        conn = get_db_connection()
        if not conn:
            return json_error("Database unavailable", 503)
        created = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                if not user:
                    created = True
                    company_id = email
                    created_at = now_utc_iso()
                    random_password = hash_password(secrets.token_urlsafe(48))
                    cur.execute(
                        """
                        INSERT INTO companies (company_id, company_name, owner_email, plan, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_id) DO NOTHING
                        """,
                        (company_id, info.get("name") or "New Client Company", email, "Growth Studio", "active", created_at),
                    )
                    cur.execute(
                        """
                        INSERT INTO users (email, password, password_hash, role, company_id, status, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (email, random_password, random_password, ROLE_COMPANY_ADMIN, company_id, USER_STATUS_ACTIVE, created_at, created_at),
                    )
                    user = cur.fetchone()
                    cur.execute(
                        "UPDATE companies SET owner_user_id = %s, updated_at = %s WHERE company_id = %s",
                        (int(user["id"]), created_at, company_id),
                    )

                role = (user.get("role") or ROLE_COMPANY_ADMIN).strip() or ROLE_COMPANY_ADMIN
                if role in {"admin", ROLE_CLIENT} and (user.get("company_id") or "").strip():
                    role = ROLE_PLATFORM_ADMIN if role == "admin" else ROLE_COMPANY_ADMIN
                company_id = (user.get("company_id") or "").strip()
                if email in FIXED_PLATFORM_ADMIN_EMAILS:
                    role = ROLE_PLATFORM_ADMIN
                    company_id = ""
                    cur.execute(
                        "UPDATE users SET role = %s, company_id = %s, status = %s, updated_at = %s WHERE id = %s",
                        (ROLE_PLATFORM_ADMIN, "", USER_STATUS_ACTIVE, now_utc_iso(), int(user["id"])),
                    )
                elif role == ROLE_PLATFORM_ADMIN:
                    role = ROLE_COMPANY_ADMIN if company_id else ROLE_CLIENT
                    cur.execute(
                        "UPDATE users SET role = %s, updated_at = %s WHERE id = %s",
                        (role, now_utc_iso(), int(user["id"])),
                    )
                if role != ROLE_PLATFORM_ADMIN and company_id:
                    cur.execute(
                        """
                        INSERT INTO v2_google_calendar_tokens (company_id, token_json, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (company_id) DO UPDATE SET token_json = EXCLUDED.token_json, updated_at = EXCLUDED.updated_at
                        """,
                        (company_id, flow.credentials.to_json(), now_utc_iso()),
                    )
            conn.commit()
        finally:
            conn.close()

        target = request.session.get("google_account_next") or ("/onboarding" if created else "/dashboard")
        if created and target == "/dashboard":
            target = "/onboarding"
        return _google_browser_login_response(request, email, role, company_id, int(user["id"]), target)
    except Exception as e:
        print("GOOGLE ACCOUNT CALLBACK ERROR:", type(e).__name__, str(e))
        return json_error("Google sign-in failed", 500)


def _google_calendar_flow(state: str = ""):
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    if not client_id or not client_secret or not redirect_uri:
        return None
    config = _google_oauth_client_config(redirect_uri)
    return Flow.from_client_config(
        config,
        scopes=GOOGLE_CALENDAR_SCOPES,
        redirect_uri=redirect_uri,
        state=state or None,
    )


def _google_calendar_service(company_id: str):
    conn = get_db_connection()
    if not conn:
        return None, "Database unavailable", "primary", "Asia/Bangkok"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT token_json, calendar_id, timezone FROM v2_google_calendar_tokens WHERE company_id = %s",
                (company_id,),
            )
            row = cur.fetchone()
        if not row:
            return None, "Google Calendar is not connected", "primary", "Asia/Bangkok"
        info = json.loads(row.get("token_json") or "{}")
        credentials = Credentials.from_authorized_user_info(info, GOOGLE_CALENDAR_SCOPES)
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return service, "", row.get("calendar_id") or "primary", row.get("timezone") or "Asia/Bangkok"
    except Exception as e:
        print("GOOGLE CALENDAR SERVICE ERROR:", str(e))
        return None, "Google Calendar connection error", "primary", "Asia/Bangkok"
    finally:
        conn.close()


@app.get("/connect/google-calendar")
def connect_google_calendar(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)
    return RedirectResponse("/auth/google?next=/calendar", status_code=302)


@app.get("/google-calendar/callback")
def google_calendar_callback(request: Request, code: str = "", state: str = ""):
    if not code or not state or state != request.session.get("google_calendar_state"):
        return json_error("Invalid Google OAuth state", 400)
    company_id, state_error = _verify_signed_oauth_state(state, "google")
    if state_error or not company_id:
        return json_error("Invalid or expired Google OAuth state", 400)
    flow = _google_calendar_flow(state)
    if not flow:
        return json_error("Google OAuth is not configured", 503)
    try:
        flow.fetch_token(code=code)
        token_json = flow.credentials.to_json()
        conn = get_db_connection()
        if not conn:
            return json_error("Database unavailable", 503)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_google_calendar_tokens (company_id, token_json, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (company_id) DO UPDATE SET token_json = EXCLUDED.token_json, updated_at = EXCLUDED.updated_at
                    """,
                    (company_id, token_json, now_utc_iso()),
                )
            conn.commit()
        finally:
            conn.close()
        request.session.pop("google_calendar_state", None)
        return RedirectResponse("/calendar?google=connected", status_code=302)
    except Exception as e:
        print("GOOGLE CALENDAR CALLBACK ERROR:", str(e))
        return json_error("Google Calendar connection failed", 500)


@app.get("/api/booking/availability")
def public_booking_availability(companyId: str = "", days: int = 7):
    company_id = (companyId or "").strip()
    if not company_id:
        return json_error("Missing companyId", 400)
    service, error, calendar_id, timezone_name = _google_calendar_service(company_id)
    if not service:
        return json_error(error, 409)
    days = max(1, min(int(days or 7), 14))
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    end = now + timedelta(days=days)
    try:
        busy_result = service.freebusy().query(
            body={
                "timeMin": now.isoformat(),
                "timeMax": end.isoformat(),
                "timeZone": timezone_name,
                "items": [{"id": calendar_id}],
            }
        ).execute()
        busy = busy_result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        busy_ranges = [
            (datetime.fromisoformat(x["start"].replace("Z", "+00:00")), datetime.fromisoformat(x["end"].replace("Z", "+00:00")))
            for x in busy
        ]
        slots = []
        day = now.date()
        while day <= end.date() and len(slots) < 12:
            for hour in (9, 10, 11, 13, 14, 15, 16):
                start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
                finish = start + timedelta(hours=1)
                if start <= now + timedelta(minutes=30):
                    continue
                if not any(start < b_end and finish > b_start for b_start, b_end in busy_ranges):
                    slots.append({"start": start.isoformat(), "end": finish.isoformat(), "label": start.strftime("%a %d %b, %H:%M")})
                if len(slots) >= 12:
                    break
            day += timedelta(days=1)
        return JSONResponse({"success": True, "timezone": timezone_name, "slots": slots})
    except Exception as e:
        print("GOOGLE AVAILABILITY ERROR:", str(e))
        return json_error("Could not read Google Calendar availability", 502)


@app.get("/api/booking/status")
def public_booking_status(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return json_error("Missing companyId", 400)
    service, error, _calendar_id, timezone_name = _google_calendar_service(company_id)
    return JSONResponse({"companyId": company_id, "googleConnected": bool(service), "timezone": timezone_name, "error": "" if service else error})


@app.post("/api/booking/create")
async def public_booking_create(request: Request):
    data = await request.json()
    company_id = (data.get("companyId") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    service_name = (data.get("service") or "Appointment").strip()
    start_raw = (data.get("start") or "").strip()
    if not company_id or not name or not email or not phone or not start_raw:
        return json_error("Name, email, phone and appointment time are required", 400)
    service, error, calendar_id, timezone_name = _google_calendar_service(company_id)
    if not service:
        return json_error(error, 409)
    try:
        start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        end = start + timedelta(hours=1)
        event = service.events().insert(
            calendarId=calendar_id,
            sendUpdates="all",
            body={
                "summary": f"{service_name} — {name}",
                "description": "Booked through AI FLOW",
                "location": address,
                "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
                "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
                "attendees": [{"email": email}],
            },
        ).execute()
        conn = get_db_connection()
        if not conn:
            return json_error("Database unavailable", 503)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_bookings
                    (company_id, client_name, email, phone, meeting_time, meeting_link, status, created_at,
                     service, address, calendar_event_id, payment_status)
                    VALUES (%s,%s,%s,%s,%s,%s,'booked',%s,%s,%s,%s,'awaiting_payment') RETURNING id
                    """,
                    (company_id, name, email, phone, start.isoformat(), event.get("htmlLink") or "", now_utc_iso(), service_name, address, event.get("id") or ""),
                )
                booking_id = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        return JSONResponse({"success": True, "bookingId": booking_id, "calendarEvent": event.get("htmlLink"), "paymentStatus": "awaiting_payment"})
    except Exception as e:
        print("PUBLIC BOOKING ERROR:", str(e))
        return json_error("Could not create booking", 502)

@app.get("/bookings-data")
def bookings_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    companyId = company_id

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_bookings
                WHERE company_id = %s
                ORDER BY id DESC
                """,
                (companyId,),
            )
            bookings = cur.fetchall()

        return JSONResponse({"success": True, "bookings": bookings})

    except Exception as e:
        print("BOOKINGS DATA ERROR:", str(e))
        return JSONResponse({"error": "Bookings data error"}, status_code=500)

    finally:
        conn.close()


@app.post("/create-booking")
async def create_booking(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    client_name = (data.get("clientName") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    date_value = (data.get("date") or "").strip()
    time_value = (data.get("time") or "").strip()
    meeting_type = (data.get("meetingType") or "").strip()

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    if not client_name or not date_value or not time_value:
        return JSONResponse({"error": "Missing clientName, date, or time"}, status_code=400)

    meeting_time = f"{date_value} {time_value}"
    meeting_link = meeting_type or ""
    status = "booked"
    created_at = now_utc_iso()

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_bookings (
                    company_id,
                    client_name,
                    email,
                    phone,
                    meeting_time,
                    meeting_link,
                    status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    client_name,
                    email,
                    phone,
                    meeting_time,
                    meeting_link,
                    status,
                    created_at,
                ),
            )
            booking_id = cur.fetchone()[0]

        conn.commit()
        return JSONResponse({"success": True, "id": booking_id})

    except Exception as e:
        print("CREATE BOOKING ERROR:", str(e))
        return JSONResponse({"error": "Create booking error"}, status_code=500)

    finally:
        conn.close()


@app.post("/delete-booking")
async def delete_booking(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    booking_id = data.get("id")

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    try:
        booking_id_int = int(booking_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM v2_bookings
                WHERE company_id = %s
                AND id = %s
                """,
                (company_id, booking_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("DELETE BOOKING ERROR:", str(e))
        return JSONResponse({"error": "Delete booking error"}, status_code=500)

    finally:
        conn.close()

@app.get("/social-data")
def social_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request, companyId, allow_public=False, allow_platform_admin_any=True
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_social_accounts
                WHERE company_id = %s
                ORDER BY id DESC
                """,
                (company_id,),
            )

            accounts = cur.fetchall()

        wa_cfg = _whatsapp_config_snapshot()
        wa_connected = any(
            (str(a.get("platform") or "").strip().lower() == "whatsapp")
            and (str(a.get("status") or "").strip().lower() == "connected")
            for a in accounts
        )
        if wa_connected:
            wa_status = "connected"
        elif wa_cfg["oauth_ready"]:
            wa_status = "oauth_available"
        elif wa_cfg["manual_ready"]:
            wa_status = "configured"
        else:
            wa_status = "not_configured"

        return JSONResponse(
            {
                "success": True,
                "accounts": accounts,
                "whatsapp": {
                    "status": wa_status,
                    "oauth_ready": wa_cfg["oauth_ready"],
                    "manual_ready": wa_cfg["manual_ready"],
                    "missing": wa_cfg["missing"],
                    "has_access_token": not _is_placeholder_value(wa_cfg["whatsapp_access_token"]),
                    "has_phone_number_id": not _is_placeholder_value(wa_cfg["whatsapp_phone_number_id"]),
                },
            }
        )

    except Exception as e:
        print("SOCIAL DATA ERROR:", str(e))

        return JSONResponse(
            {"error": "Social data error"},
            status_code=500,
        )

    finally:
        conn.close()


@app.get("/whatsapp-connect-url")
def whatsapp_connect_url(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_admin_company(request, companyId)
    if err:
        return err

    cfg = _whatsapp_config_snapshot()

    if cfg["oauth_ready"]:
        auth_url = "/api/meta/connect?companyId=" + urllib.parse.quote(company_id, safe="")
        return JSONResponse(
            {
                "success": True,
                "mode": "oauth_meta",
                "auth_url": auth_url,
            }
        )

    if cfg["manual_ready"]:
        now = datetime.utcnow().isoformat() + "Z"
        account_id = (cfg["whatsapp_phone_number_id"] or "").strip() or "whatsapp_manual"
        account_name = "WhatsApp Business"
        conn = get_db_connection()
        if not conn:
            return JSONResponse({"success": False, "error": "Database error"}, status_code=500)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM v2_social_accounts WHERE company_id = %s AND platform = %s",
                    (company_id, "WhatsApp"),
                )
                cur.execute(
                    """
                    INSERT INTO v2_social_accounts (company_id, platform, status, account_name, account_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (company_id, "WhatsApp", "connected", account_name, account_id, now, now),
                )
            conn.commit()
        except Exception as e:
            print("WHATSAPP MANUAL CONNECT ERROR:", type(e).__name__)
            return JSONResponse({"success": False, "error": "WhatsApp manual setup save error"}, status_code=500)
        finally:
            conn.close()

        return JSONResponse(
            {
                "success": True,
                "mode": "manual_config",
                "configured": True,
                "message": "WhatsApp manual config detected and saved.",
            }
        )

    missing = cfg["missing"] or ["META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"]
    return JSONResponse(
        {
            "success": False,
            "error": "WhatsApp is not configured.",
            "detail": "WhatsApp requires Meta OAuth credentials or manual Cloud API setup.",
            "missing": missing,
        },
        status_code=400,
    )


# =========================================================
# SOCIAL CONTENT AUTOMATION (MVP)
# =========================================================

_SOCIAL_DRAFT_TYPES_BY_PLATFORM = {
    "Facebook": ["Facebook post", "AI tip", "AI statistic/fact post"],
    "Instagram": ["Instagram caption", "Instagram reel idea/script", "AI tip", "AI statistic/fact post"],
    "TikTok": ["TikTok video idea/script", "AI tip", "AI statistic/fact post"],
}


def _today_utc_date_str():
    return datetime.utcnow().date().isoformat()


def _fallback_social_draft(company_name: str, platform: str, draft_type: str, date_str: str):
    brand = (company_name or "your business").strip() or "your business"
    topic = "AI sales automation"

    if draft_type == "Instagram reel idea/script":
        title = f"{platform} Reel Idea: 3 Ways {topic} Saves Time"
        hook = "Stop replying manually. Here are 3 quick wins with AI automation."
        caption = (
            f"Reel script idea:\n"
            f"1) Hook: \"Still replying to leads one by one?\"\n"
            f"2) Show: instant replies + booking link\n"
            f"3) Proof: faster follow-ups, fewer missed leads\n"
            f"4) CTA: \"Comment 'FLOW' and we’ll send the setup.\"\n"
        )
        hashtags = "#sales #automation #ai #leadgeneration #business"
        visual = "Vertical reel: screen recording of a lead coming in, AI reply, then booking confirmed."
        return {
            "title": title,
            "caption": caption,
            "hook": hook,
            "hashtags": hashtags,
            "visual_idea": visual,
        }

    if draft_type in ("TikTok video idea/script",):
        title = f"TikTok Idea: Instant Lead Reply Demo ({date_str})"
        hook = "Watch how a lead turns into a booking in under 30 seconds."
        caption = (
            "Video script:\n"
            "1) Show incoming lead message\n"
            "2) Show AI reply asking 1 question\n"
            "3) Show booking confirmation\n"
            "CTA: \"Want this for your business? DM 'AI FLOW'\""
        )
        hashtags = "#tiktokmarketing #automation #ai #crm #leadgen"
        visual = "Vertical screen recording + captions, fast cuts, end with booking calendar."
        return {
            "title": title,
            "caption": caption,
            "hook": hook,
            "hashtags": hashtags,
            "visual_idea": visual,
        }

    if draft_type == "AI statistic/fact post":
        title = f"{platform} Fact: Faster Replies Win More Deals"
        hook = "Fast response time is one of the biggest predictors of conversion."
        caption = (
            f"Fact: businesses that respond faster capture more opportunities.\n"
            f"With AI FLOW, {brand} can reply instantly, qualify, and book calls.\n"
            f"Want the setup? Reply with your website."
        )
        hashtags = "#ai #sales #conversion #leadgeneration #businessgrowth"
        visual = "Simple chart-style graphic: Response time vs conversion rate."
        return {
            "title": title,
            "caption": caption,
            "hook": hook,
            "hashtags": hashtags,
            "visual_idea": visual,
        }

    if draft_type == "AI tip":
        title = f"{platform} Tip: Ask One Clear Question"
        hook = "One good question beats a long pitch."
        caption = (
            "Tip: Keep replies short and ask one clear follow-up question.\n"
            "Example: \"What’s the best phone number or email to reach you?\""
        )
        hashtags = "#aitips #sales #customerexperience #automation"
        visual = "Minimal dark card graphic with the tip headline + one example question."
        return {
            "title": title,
            "caption": caption,
            "hook": hook,
            "hashtags": hashtags,
            "visual_idea": visual,
        }

    # Default short post
    title = f"{platform} Post: {topic} for {brand}"
    hook = "Reply faster. Capture more leads. Book more appointments."
    caption = (
        f"{hook}\n"
        f"{brand} can automate follow-ups, qualify leads, and fill the calendar with AI.\n"
        "Want a demo? Send your email and we’ll set it up."
    )
    hashtags = "#sales #automation #ai #smallbusiness #agency"
    visual = "Screenshot-style mock: chat widget + CRM lead captured + booking card."
    return {"title": title, "caption": caption, "hook": hook, "hashtags": hashtags, "visual_idea": visual}


def _recent_social_context(company_id: str, platform: str) -> str:
    """Small history window used to avoid repetitive daily content."""
    conn = get_db_connection()
    if not conn:
        return "No reliable performance or publishing history is available yet."
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT title, hook, status, publish_message
                FROM v2_social_content_drafts
                WHERE company_id = %s AND platform = %s
                ORDER BY id DESC
                LIMIT 12
                """,
                (company_id, platform),
            )
            rows = cur.fetchall()
        if not rows:
            return "No reliable performance or publishing history is available yet."
        return json.dumps(rows, ensure_ascii=False)[:4000]
    except Exception:
        return "Publishing history could not be loaded. Do not invent performance data."
    finally:
        conn.close()


def _generate_social_draft(company_id: str, platform: str, draft_type: str):
    """
    Returns dict with keys: title, caption, hook, hashtags, visual_idea.
    Uses Groq if configured; falls back to deterministic templates.
    """
    company_name = ""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT company_name FROM companies WHERE company_id = %s",
                    (company_id,),
                )
                row = cur.fetchone()
                company_name = (row.get("company_name") or "").strip() if row else ""
        except Exception:
            company_name = ""
        finally:
            conn.close()

    date_str = _today_utc_date_str()
    recent_context = _recent_social_context(company_id, platform)

    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            client = Groq(api_key=api_key.strip())
            prompt = f"""
You are the organic growth operator inside AI FLOW. Create ONE publish-ready social post variant.

Company: {company_name or "Client"}
Platform: {platform}
Content slot: {draft_type}
Date: {date_str}
Recent content history: {recent_context}

Return JSON ONLY with keys:
title, caption, hook, hashtags, visual_idea

Rules:
- Write in English only.
- First reason silently about the audience's current pain, platform-native behavior,
  and which angle is least repetitive. Never claim live trends or performance data
  unless it appears in the supplied history.
- Optimize for organic distribution: immediate specific hook, one useful idea,
  easy-to-scan language, retention or save/share value, and one natural CTA.
- Do not use engagement bait, fake urgency, unsupported statistics, spam, or promises
  that a post will go viral.
- Adapt to {platform}; do not reuse generic cross-platform wording.
- The title is an internal label, not a caption headline.
- Keep hashtags relevant and restrained: 3-6 tags in one string.
- For Reel/video, caption must include a concise 12-20 second scene/script plan.
- visual_idea must be production-ready: subject, composition, on-screen copy,
  safe zones, and the first-frame hook.
"""
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=380,
            )
            raw = (completion.choices[0].message.content or "").strip()
            obj = json.loads(raw)
            return {
                "title": str(obj.get("title") or "").strip(),
                "caption": str(obj.get("caption") or "").strip(),
                "hook": str(obj.get("hook") or "").strip(),
                "hashtags": str(obj.get("hashtags") or "").strip(),
                "visual_idea": str(obj.get("visual_idea") or "").strip(),
            }
        except Exception as e:
            print("SOCIAL DRAFT GROQ ERROR:", str(e))

    return _fallback_social_draft(company_name, platform, draft_type, date_str)


def _ensure_daily_social_drafts(company_id: str):
    """Create the configured daily queue without publishing it."""
    today = _today_utc_date_str()
    now = _iso_z(datetime.utcnow())

    conn = get_db_connection()
    if not conn:
        return False, "Database error"

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT daily_content_units FROM v2_social_automation_settings WHERE company_id = %s",
                (company_id,),
            )
            settings_row = cur.fetchone()
        configured_units = max(1, min(3, int((settings_row or {}).get("daily_content_units") or 1)))
        try:
            launch_queue_limit = max(1, min(3, int(os.getenv("SOCIAL_QUEUE_DAILY_LIMIT", "1"))))
        except Exception:
            launch_queue_limit = 1
        daily_units = min(configured_units, launch_queue_limit)

        # Start with one reviewed daily concept while integrations are being
        # approved. The same concept gets a platform-native variant, and the
        # setting can be raised to three after launch readiness is confirmed.
        platforms = ["Facebook", "Instagram", "TikTok"]
        daily_slots = ["Educational static", "Proof or case study", "Organic short-form Reel"]
        for platform in platforms:
            for draft_type in daily_slots[:daily_units]:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM v2_social_content_drafts
                        WHERE company_id = %s AND content_date = %s
                          AND platform = %s AND draft_type = %s
                        LIMIT 1
                        """,
                        (company_id, today, platform, draft_type),
                    )
                    already = cur.fetchone() is not None
                if already:
                    continue

                draft = _generate_social_draft(company_id, platform, draft_type)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO v2_social_content_drafts (
                            company_id, content_date, platform, draft_type,
                            title, caption, hook, hashtags, visual_idea,
                            status, publish_message, created_at, updated_at
                        )
                        SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM v2_social_content_drafts
                            WHERE company_id = %s AND content_date = %s
                              AND platform = %s AND draft_type = %s
                        )
                        """,
                        (
                            company_id, today, platform, draft_type,
                            draft.get("title") or "", draft.get("caption") or "",
                            draft.get("hook") or "", draft.get("hashtags") or "",
                            draft.get("visual_idea") or "", "draft", "", now, now,
                            company_id, today, platform, draft_type,
                        ),
                    )

        conn.commit()
        return True, ""
    except Exception as e:
        print("ENSURE DAILY SOCIAL DRAFTS ERROR:", str(e))
        return False, "Social draft generation error"
    finally:
        conn.close()


def _resolve_social_content_company(request: Request, provided_company_id: str, *, write: bool = False):
    company_id, user, err = resolve_company_id(
        request,
        provided_company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return "", err
    allowed_roles = (ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN) if write else (
        ROLE_PLATFORM_ADMIN,
        ROLE_COMPANY_ADMIN,
        ROLE_EMPLOYEE,
    )
    if not user or not is_role(user, *allowed_roles):
        return "", json_error("Forbidden", 403)
    return company_id, None


@app.get("/api/social/automation-settings")
def social_automation_settings(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_content_company(request, companyId)
    if err:
        return err
    defaults = {
        "enabled": False,
        "dailyContentUnits": 1,
        "timezone": "UTC",
        "publishMode": "approval",
        "postingTimes": ["09:00", "14:00", "19:00"],
    }
    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM v2_social_automation_settings WHERE company_id = %s",
                (company_id,),
            )
            row = cur.fetchone()
        if not row:
            return JSONResponse({"success": True, "settings": defaults})
        try:
            posting_times = json.loads(row.get("posting_times") or "[]")
        except Exception:
            posting_times = defaults["postingTimes"]
        return JSONResponse(
            {
                "success": True,
                "settings": {
                    "enabled": bool(row.get("enabled")),
                    "dailyContentUnits": int(row.get("daily_content_units") or 1),
                    "timezone": row.get("timezone") or "UTC",
                    "publishMode": row.get("publish_mode") or "approval",
                    "postingTimes": posting_times,
                },
            }
        )
    finally:
        conn.close()


@app.post("/api/social/automation-settings")
async def save_social_automation_settings(request: Request):
    data = await request.json()
    company_id, err = _resolve_social_content_company(
        request, (data.get("companyId") or "").strip(), write=True
    )
    if err:
        return err
    enabled = data.get("enabled") is True
    timezone_name = str(data.get("timezone") or "UTC").strip()[:80] or "UTC"
    publish_mode = str(data.get("publishMode") or "approval").strip()
    # TikTok requires an explicit per-post review/confirmation. Keep approval as
    # the safe default and reject invented fully autonomous modes.
    if publish_mode not in {"approval", "meta_auto_after_brand_approval"}:
        return json_error("Invalid publish mode", 400)
    try:
        daily_units = max(1, min(3, int(data.get("dailyContentUnits") or 1)))
    except Exception:
        return json_error("Daily content units must be between 1 and 3", 400)
    posting_times = data.get("postingTimes") or ["09:00", "14:00", "19:00"]
    if not isinstance(posting_times, list) or len(posting_times) != 3:
        return json_error("Exactly three posting times are required", 400)
    clean_times = []
    for value in posting_times:
        candidate = str(value or "").strip()
        try:
            datetime.strptime(candidate, "%H:%M")
        except Exception:
            return json_error("Posting times must use HH:MM", 400)
        clean_times.append(candidate)

    now = _iso_z(datetime.utcnow())
    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_social_automation_settings (
                    company_id, enabled, daily_content_units, timezone,
                    publish_mode, posting_times, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (company_id) DO UPDATE SET
                    enabled = EXCLUDED.enabled,
                    daily_content_units = EXCLUDED.daily_content_units,
                    timezone = EXCLUDED.timezone,
                    publish_mode = EXCLUDED.publish_mode,
                    posting_times = EXCLUDED.posting_times,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    company_id, enabled, daily_units, timezone_name, publish_mode,
                    json.dumps(clean_times), now, now,
                ),
            )
        conn.commit()
        return JSONResponse({"success": True})
    finally:
        conn.close()


def _social_cron_authorized(request: Request):
    expected = (os.getenv("SOCIAL_CRON_SECRET") or "").strip()
    if not expected:
        return False, json_error("SOCIAL_CRON_SECRET is not configured", 503)
    supplied = (request.headers.get("authorization") or "").strip()
    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return False, json_error("Unauthorized", 401)
    return True, None


@app.post("/api/cron/social-content")
def run_social_content_cron(request: Request):
    authorized, err = _social_cron_authorized(request)
    if not authorized:
        return err
    conn = get_db_connection()
    if not conn:
        return json_error("Database error", 500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT s.company_id
                FROM v2_social_automation_settings s
                JOIN companies c ON c.company_id = s.company_id
                WHERE s.enabled = TRUE AND COALESCE(c.status, 'active') = 'active'
                ORDER BY s.company_id
                """
            )
            company_ids = [str(row.get("company_id") or "") for row in cur.fetchall()]
    finally:
        conn.close()

    generated, failed = [], []
    for company_id in company_ids:
        ok, generate_err = _ensure_daily_social_drafts(company_id)
        (generated if ok else failed).append(company_id if ok else {"companyId": company_id, "error": generate_err})
    return JSONResponse(
        {
            "success": not failed,
            "generatedCompanies": len(generated),
            "failed": failed,
            "note": "This job creates the daily approval queue. Publishing remains policy- and permission-gated per channel.",
        }
    )


@app.get("/social-content-data")
def social_content_data(request: Request, companyId: str = ""):
    company_id, err = _resolve_social_content_company(request, companyId)
    if err:
        return err

    ok, err = _ensure_daily_social_drafts(company_id)
    if not ok:
        return JSONResponse({"error": err or "Social content error"}, status_code=500)

    today = _today_utc_date_str()

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_social_content_drafts
                WHERE company_id = %s AND content_date = %s
                ORDER BY id DESC
                """,
                (company_id, today),
            )
            today_drafts = cur.fetchall()

            cur.execute(
                """
                SELECT *
                FROM v2_social_content_drafts
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 60
                """,
                (company_id,),
            )
            history = cur.fetchall()

        return JSONResponse(
            {"success": True, "today": today, "drafts": today_drafts, "history": history}
        )
    except Exception as e:
        print("SOCIAL CONTENT DATA ERROR:", str(e))
        return JSONResponse({"error": "Social content data error"}, status_code=500)
    finally:
        conn.close()


@app.post("/social-content/regenerate")
async def social_content_regenerate(request: Request):
    data = await request.json()
    company_id, err = _resolve_social_content_company(
        request, (data.get("companyId") or "").strip(), write=True
    )
    if err:
        return err
    draft_id = data.get("id")
    try:
        draft_id_int = int(draft_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT platform, draft_type
                FROM v2_social_content_drafts
                WHERE company_id = %s AND id = %s
                """,
                (company_id, draft_id_int),
            )
            row = cur.fetchone()
            if not row:
                return JSONResponse({"error": "Draft not found"}, status_code=404)

        platform = row.get("platform") or "Instagram"
        draft_type = row.get("draft_type") or "Instagram caption"
        draft = _generate_social_draft(company_id, platform, draft_type)
        now = datetime.utcnow().isoformat() + "Z"

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE v2_social_content_drafts
                SET title=%s, caption=%s, hook=%s, hashtags=%s, visual_idea=%s,
                    status=%s, publish_message=%s, updated_at=%s
                WHERE company_id=%s AND id=%s
                """,
                (
                    draft.get("title") or "",
                    draft.get("caption") or "",
                    draft.get("hook") or "",
                    draft.get("hashtags") or "",
                    draft.get("visual_idea") or "",
                    "draft",
                    "",
                    now,
                    company_id,
                    draft_id_int,
                ),
            )

            if cur.rowcount == 0:
                return JSONResponse({"error": "Draft not found"}, status_code=404)

        conn.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        print("SOCIAL CONTENT REGENERATE ERROR:", str(e))
        return JSONResponse({"error": "Regenerate error"}, status_code=500)
    finally:
        conn.close()


@app.post("/social-content/update")
async def social_content_update(request: Request):
    data = await request.json()
    company_id, err = _resolve_social_content_company(
        request, (data.get("companyId") or "").strip(), write=True
    )
    if err:
        return err
    draft_id = data.get("id")
    try:
        draft_id_int = int(draft_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    fields_map = {
        "title": "title",
        "caption": "caption",
        "hook": "hook",
        "hashtags": "hashtags",
        "visualIdea": "visual_idea",
    }

    updates = []
    values = []
    for k, col in fields_map.items():
        if k in data and data.get(k) is not None:
            updates.append(f"{col} = %s")
            values.append(str(data.get(k)).strip())

    if not updates:
        return JSONResponse({"error": "No fields to update"}, status_code=400)

    now = datetime.utcnow().isoformat() + "Z"
    updates.append("updated_at = %s")
    values.append(now)
    values.extend([company_id, draft_id_int])

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE v2_social_content_drafts
                SET {", ".join(updates)}
                WHERE company_id = %s AND id = %s
                """,
                tuple(values),
            )
            if cur.rowcount == 0:
                return JSONResponse({"error": "Draft not found"}, status_code=404)

        conn.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        print("SOCIAL CONTENT UPDATE ERROR:", str(e))
        return JSONResponse({"error": "Update error"}, status_code=500)
    finally:
        conn.close()


@app.post("/social-content/status")
async def social_content_status(request: Request):
    data = await request.json()
    company_id, err = _resolve_social_content_company(
        request, (data.get("companyId") or "").strip(), write=True
    )
    if err:
        return err
    draft_id = data.get("id")
    status = (data.get("status") or "").strip()
    try:
        draft_id_int = int(draft_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    allowed = {"draft", "approved", "posted", "failed"}
    if status not in allowed:
        return JSONResponse({"error": "Invalid status"}, status_code=400)

    now = datetime.utcnow().isoformat() + "Z"

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE v2_social_content_drafts
                SET status = %s, updated_at = %s
                WHERE company_id = %s AND id = %s
                """,
                (status, now, company_id, draft_id_int),
            )
            if cur.rowcount == 0:
                return JSONResponse({"error": "Draft not found"}, status_code=404)

        conn.commit()
        return JSONResponse({"success": True})
    except Exception as e:
        print("SOCIAL CONTENT STATUS ERROR:", str(e))
        return JSONResponse({"error": "Status update error"}, status_code=500)
    finally:
        conn.close()


@app.post("/social-content/publish")
async def social_content_publish(request: Request):
    data = await request.json()
    company_id, err = _resolve_social_content_company(
        request, (data.get("companyId") or "").strip(), write=True
    )
    if err:
        return err
    draft_id = data.get("id")
    try:
        draft_id_int = int(draft_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, platform, status, caption, hashtags
                FROM v2_social_content_drafts
                WHERE company_id = %s AND id = %s
                """,
                (company_id, draft_id_int),
            )
            draft = cur.fetchone()
            if not draft:
                return JSONResponse({"error": "Draft not found"}, status_code=404)

            if (draft.get("status") or "") != "approved":
                return JSONResponse({"error": "Approve the draft before publishing"}, status_code=400)

            platform = (draft.get("platform") or "").strip() or "Instagram"

        # Facebook: attempt a simple text post to the most recently connected Page.
        if platform == "Facebook":
            conn2 = get_db_connection()
            if not conn2:
                return JSONResponse({"error": "Database error"}, status_code=500)
            try:
                with conn2.cursor(cursor_factory=RealDictCursor) as cur2:
                    cur2.execute(
                        """
                        SELECT account_id
                        FROM v2_social_accounts
                        WHERE company_id = %s AND platform = 'Facebook'
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (company_id,),
                    )
                    row = cur2.fetchone()
                    page_id = (row.get("account_id") or "").strip() if row else ""
                    if not page_id:
                        return JSONResponse(
                            {"error": "Facebook Page is not connected. Connect Meta first."},
                            status_code=400,
                        )

                    cur2.execute(
                        """
                        SELECT access_token
                        FROM v2_social_tokens
                        WHERE company_id = %s AND provider = %s AND platform = %s AND account_id = %s
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (company_id, "meta", "Facebook", page_id),
                    )
                    tok = cur2.fetchone()
                    page_token = (tok.get("access_token") or "").strip() if tok else ""
                    if not page_token:
                        return JSONResponse(
                            {"error": "Facebook token missing. Reconnect Meta to refresh tokens."},
                            status_code=400,
                        )
            finally:
                conn2.close()

            message = (draft.get("caption") or "").strip()
            tags = (draft.get("hashtags") or "").strip()
            if tags:
                message = (message + "\n\n" + tags).strip()

            publish_url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
            try:
                resp = _http_post_form_json(
                    publish_url,
                    {"message": message, "access_token": page_token},
                    timeout_sec=25,
                )
            except Exception as e:
                print("FACEBOOK PUBLISH HTTP ERROR:", type(e).__name__)
                return JSONResponse({"error": "Facebook publish error"}, status_code=500)

            if resp.get("error"):
                # Keep draft approved; store error message for debugging.
                err_obj = resp.get("error") or {}
                msg = (err_obj.get("message") or "Facebook publish failed").strip()
                low = msg.lower()
                short_msg = msg
                if "pages_manage_posts" in low or "permissions error" in low or "(#200)" in low:
                    short_msg = (
                        "Missing Meta permissions to publish to Facebook Pages. "
                        "Enable pages_manage_posts (and pages_read_engagement) in your Meta app, then reconnect Meta."
                    )
                elif "access token" in low and "expired" in low:
                    short_msg = "Facebook token expired. Reconnect Meta to refresh tokens."

                now = _iso_z(datetime.utcnow())
                try:
                    conn3 = get_db_connection()
                    if conn3:
                        with conn3.cursor() as cur3:
                            cur3.execute(
                                """
                                UPDATE v2_social_content_drafts
                                SET publish_message = %s, updated_at = %s
                                WHERE company_id = %s AND id = %s
                                """,
                                (short_msg[:400], now, company_id, draft_id_int),
                            )
                        conn3.commit()
                finally:
                    if "conn3" in locals() and conn3:
                        conn3.close()
                return JSONResponse(
                    {
                        "error": "Facebook publish failed",
                        "detail": short_msg,
                    },
                    status_code=400,
                )

            post_id = (resp.get("id") or "").strip()
            if not post_id:
                return JSONResponse({"error": "Facebook publish returned no post id"}, status_code=500)

            now = _iso_z(datetime.utcnow())
            conn4 = get_db_connection()
            if not conn4:
                return JSONResponse({"error": "Database error"}, status_code=500)
            try:
                with conn4.cursor() as cur4:
                    cur4.execute(
                        """
                        UPDATE v2_social_content_drafts
                        SET status = %s, publish_message = %s, updated_at = %s
                        WHERE company_id = %s AND id = %s
                        """,
                        ("posted", f"Facebook post id: {post_id}", now, company_id, draft_id_int),
                    )
                conn4.commit()
            finally:
                conn4.close()

            return JSONResponse({"success": True, "platform": "Facebook", "postId": post_id})

        # Instagram: would require instagram_content_publish + media container flow.
        if platform == "Instagram":
            return JSONResponse(
                {
                    "error": "Instagram publishing is not enabled in this MVP build yet.",
                    "detail": "Instagram publishing requires Meta Instagram Graph API publishing flow and instagram_content_publish permission.",
                },
                status_code=400,
            )

        # TikTok: requires Content Posting API scopes and a real video upload/publish flow.
        if platform == "TikTok":
            # Check token + scopes for clearer messaging.
            conn2 = get_db_connection()
            scope = ""
            try:
                if conn2:
                    with conn2.cursor(cursor_factory=RealDictCursor) as cur2:
                        cur2.execute(
                            """
                            SELECT scope
                            FROM v2_social_tokens
                            WHERE company_id = %s AND provider = %s
                            ORDER BY id DESC
                            LIMIT 1
                            """,
                            (company_id, "tiktok"),
                        )
                        row = cur2.fetchone()
                        scope = (row.get("scope") or "").strip() if row else ""
            finally:
                if conn2:
                    conn2.close()

            if "video.publish" not in scope and "video.upload" not in scope:
                return JSONResponse(
                    {
                        "error": "TikTok publishing permission is missing.",
                        "detail": "Enable Content Posting API scopes (video.upload/video.publish) in TikTok Developer Portal and complete review/audit.",
                    },
                    status_code=400,
                )

            return JSONResponse(
                {
                    "error": "TikTok publishing is not enabled in this MVP build yet.",
                    "detail": "Implementing real TikTok publishing requires video files and the Content Posting API media transfer flow.",
                },
                status_code=400,
            )

        return JSONResponse({"error": "Unsupported platform"}, status_code=400)

    except Exception as e:
        print("SOCIAL CONTENT PUBLISH ERROR:", str(e))
        return JSONResponse({"error": "Publish error"}, status_code=500)
    finally:
        conn.close()


# =========================================================
# ANALYTICS
# =========================================================

@app.get("/analytics-data")
def analytics_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    companyId = company_id

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Leads
            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s",
                (companyId,),
            )
            total_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "new"),
            )
            new_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "in_progress"),
            )
            in_progress_leads = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_leads WHERE company_id = %s AND status = %s",
                (companyId, "converted"),
            )
            converted_leads = cur.fetchone()["count"]

            # Content posts
            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_content_posts WHERE company_id = %s",
                (companyId,),
            )
            total_posts = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_content_posts WHERE company_id = %s AND status = %s",
                (companyId, "draft"),
            )
            draft_posts = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_content_posts WHERE company_id = %s AND status = %s",
                (companyId, "approved"),
            )
            approved_posts = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_content_posts WHERE company_id = %s AND status = %s",
                (companyId, "published"),
            )
            published_posts = cur.fetchone()["count"]

            # Bookings
            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_bookings WHERE company_id = %s",
                (companyId,),
            )
            total_bookings = cur.fetchone()["count"]

            # AI replies
            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_ai_replies WHERE company_id = %s",
                (companyId,),
            )
            total_ai_replies = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_ai_replies WHERE company_id = %s AND status = %s",
                (companyId, "draft"),
            )
            draft_replies = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_ai_replies WHERE company_id = %s AND status = %s",
                (companyId, "sent"),
            )
            sent_replies = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_ai_replies WHERE company_id = %s AND status = %s",
                (companyId, "archived"),
            )
            archived_replies = cur.fetchone()["count"]

            # Social accounts
            cur.execute(
                "SELECT COUNT(*) AS count FROM v2_social_accounts WHERE company_id = %s AND status = %s",
                (companyId, "connected"),
            )
            connected_social_accounts = cur.fetchone()["count"]

        conversion_rate = 0
        if total_leads and int(total_leads) > 0:
            conversion_rate = int(round((converted_leads / total_leads) * 100))

        return JSONResponse(
            {
                "success": True,
                "metrics": {
                    "total_leads": total_leads,
                    "new_leads": new_leads,
                    "in_progress_leads": in_progress_leads,
                    "converted_leads": converted_leads,
                    "total_posts": total_posts,
                    "draft_posts": draft_posts,
                    "approved_posts": approved_posts,
                    "published_posts": published_posts,
                    "total_bookings": total_bookings,
                    "total_ai_replies": total_ai_replies,
                    "draft_replies": draft_replies,
                    "sent_replies": sent_replies,
                    "archived_replies": archived_replies,
                    "connected_social_accounts": connected_social_accounts,
                    "conversion_rate": conversion_rate,
                },
            }
        )

    except Exception as e:
        print("ANALYTICS DATA ERROR:", str(e))
        return JSONResponse({"error": "Analytics data error"}, status_code=500)

    finally:
        conn.close()


# =========================================================
# SETTINGS
# =========================================================

@app.get("/settings-data")
def settings_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    companyId = company_id

    defaults = {
        "industry": "Beauty / Salon",
        "website": "",
        "phone": "",
        "assistantName": "AI FLOW Assistant",
        "aiTone": "Friendly",
        "aiGoal": "Capture leads",
        "businessDescription": "",
        "welcomeMessage": "Hi! How can I help you today?",
        "leadQuestion": "What is the best phone number or email to contact you?",
        "emailNotifications": "Enabled",
        "leadAlerts": "Enabled",
        "weeklyReports": "Enabled",
        "updatedAt": "",
    }

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT company_id, company_name, owner_email, plan, status, created_at, payment_status
                FROM companies
                WHERE company_id = %s
                """,
                (companyId,),
            )
            company = cur.fetchone() or {
                "company_id": companyId,
                "company_name": "",
                "owner_email": "",
                "plan": "Growth Studio",
                "status": "active",
                "created_at": "",
                "payment_status": "unpaid",
            }

            cur.execute(
                """
                SELECT *
                FROM v2_company_settings
                WHERE company_id = %s
                """,
                (companyId,),
            )
            settings_row = cur.fetchone()

        settings = dict(defaults)

        # Prefer company table name if present; settings.html may override with its own input.
        if settings_row:
            settings["industry"] = settings_row.get("industry") or settings["industry"]
            settings["website"] = settings_row.get("website") or ""
            settings["phone"] = settings_row.get("phone") or ""
            settings["assistantName"] = settings_row.get("assistant_name") or settings["assistantName"]
            settings["aiTone"] = settings_row.get("ai_tone") or settings["aiTone"]
            settings["aiGoal"] = settings_row.get("ai_goal") or settings["aiGoal"]
            settings["businessDescription"] = settings_row.get("business_description") or ""
            settings["welcomeMessage"] = settings_row.get("welcome_message") or settings["welcomeMessage"]
            settings["leadQuestion"] = settings_row.get("lead_question") or settings["leadQuestion"]
            settings["emailNotifications"] = (
                settings_row.get("email_notifications") or settings["emailNotifications"]
            )
            settings["leadAlerts"] = settings_row.get("lead_alerts") or settings["leadAlerts"]
            settings["weeklyReports"] = settings_row.get("weekly_reports") or settings["weeklyReports"]
            settings["updatedAt"] = settings_row.get("updated_at") or ""

        company_name = (company.get("company_name") or "").strip()
        settings_exists = bool(settings_row)
        is_complete = bool(company_name) and company_name != "New Client Company"

        return JSONResponse(
            {
                "success": True,
                "company": company,
                "settings": settings,
                "settingsExists": settings_exists,
                "isComplete": is_complete,
            }
        )

    except Exception as e:
        print("SETTINGS DATA ERROR:", str(e))
        return JSONResponse({"error": "Settings data error"}, status_code=500)

    finally:
        conn.close()


@app.post("/save-settings")
async def save_settings(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    company_name = (data.get("companyName") or "").strip()
    industry = (data.get("industry") or "").strip()
    website = (data.get("website") or "").strip()
    phone = (data.get("phone") or "").strip()
    assistant_name = (data.get("assistantName") or "AI FLOW Assistant").strip() or "AI FLOW Assistant"
    ai_tone = (data.get("aiTone") or "Friendly").strip() or "Friendly"
    ai_goal = (data.get("aiGoal") or "Capture leads").strip() or "Capture leads"
    business_description = (data.get("businessDescription") or "").strip()
    welcome_message = (data.get("welcomeMessage") or "").strip()
    lead_question = (data.get("leadQuestion") or "").strip()
    email_notifications = (data.get("emailNotifications") or "Enabled").strip() or "Enabled"
    lead_alerts = (data.get("leadAlerts") or "Enabled").strip() or "Enabled"
    weekly_reports = (data.get("weeklyReports") or "Enabled").strip() or "Enabled"
    updated_at = now_utc_iso()

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            if company_name:
                cur.execute(
                    """
                    UPDATE companies
                    SET company_name = %s
                    WHERE company_id = %s
                    """,
                    (company_name, company_id),
                )

            # Upsert (manual): update first, then insert if no row
            cur.execute(
                """
                UPDATE v2_company_settings
                SET
                    industry = %s,
                    website = %s,
                    phone = %s,
                    assistant_name = %s,
                    ai_tone = %s,
                    ai_goal = %s,
                    business_description = %s,
                    welcome_message = %s,
                    lead_question = %s,
                    email_notifications = %s,
                    lead_alerts = %s,
                    weekly_reports = %s,
                    updated_at = %s
                WHERE company_id = %s
                """,
                (
                    industry,
                    website,
                    phone,
                    assistant_name,
                    ai_tone,
                    ai_goal,
                    business_description,
                    welcome_message,
                    lead_question,
                    email_notifications,
                    lead_alerts,
                    weekly_reports,
                    updated_at,
                    company_id,
                ),
            )

            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO v2_company_settings (
                        company_id,
                        industry,
                        website,
                        phone,
                        assistant_name,
                        ai_tone,
                        ai_goal,
                        business_description,
                        welcome_message,
                        lead_question,
                        email_notifications,
                        lead_alerts,
                        weekly_reports,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        company_id,
                        industry,
                        website,
                        phone,
                        assistant_name,
                        ai_tone,
                        ai_goal,
                        business_description,
                        welcome_message,
                        lead_question,
                        email_notifications,
                        lead_alerts,
                        weekly_reports,
                        updated_at,
                    ),
                )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("SAVE SETTINGS ERROR:", str(e))
        return JSONResponse({"error": "Save settings error"}, status_code=500)

    finally:
        conn.close()


@app.get("/widget-settings")
def widget_settings(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

    defaults = {
        "assistantName": "AI FLOW Assistant",
        "welcomeMessage": "Hi! How can I help you today?",
        "leadQuestion": "What is the best phone number or email to contact you?",
        "aiTone": "Friendly",
        "aiGoal": "Capture leads",
        "businessDescription": "",
    }

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"success": True, "settings": defaults})

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT assistant_name, welcome_message, lead_question, ai_tone, ai_goal, business_description
                FROM v2_company_settings
                WHERE company_id = %s
                """,
                (companyId,),
            )
            row = cur.fetchone()

        if not row:
            return JSONResponse({"success": True, "settings": defaults})

        merged = dict(defaults)
        merged["assistantName"] = row.get("assistant_name") or merged["assistantName"]
        merged["welcomeMessage"] = row.get("welcome_message") or merged["welcomeMessage"]
        merged["leadQuestion"] = row.get("lead_question") or merged["leadQuestion"]
        merged["aiTone"] = row.get("ai_tone") or merged["aiTone"]
        merged["aiGoal"] = row.get("ai_goal") or merged["aiGoal"]
        merged["businessDescription"] = row.get("business_description") or merged["businessDescription"]

        return JSONResponse({"success": True, "settings": merged})

    except Exception as e:
        print("WIDGET SETTINGS ERROR:", str(e))
        return JSONResponse({"success": True, "settings": defaults})

    finally:
        conn.close()


# =========================================================
# BILLING
# =========================================================

@app.get("/billing-data")
def billing_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    companyId = company_id

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT company_id, plan
                FROM companies
                WHERE company_id = %s
                """,
                (companyId,),
            )
            row = cur.fetchone()

        plan = (row or {}).get("plan") or "Growth Studio"
        return JSONResponse({"success": True, "plan": plan})

    except Exception as e:
        print("BILLING DATA ERROR:", str(e))
        return JSONResponse({"error": "Billing data error"}, status_code=500)

    finally:
        conn.close()


@app.post("/update-plan")
async def update_plan(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    plan = (data.get("plan") or "").strip()

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN):
        return json_error("Forbidden", 403)

    if not plan:
        return JSONResponse({"error": "Missing plan"}, status_code=400)

    allowed = {"AI Website Bot", "Growth Studio", "Agency Pro"}
    if plan not in allowed:
        return JSONResponse({"error": "Invalid plan"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE companies
                SET plan = %s
                WHERE company_id = %s
                """,
                (plan, company_id),
            )

            # If company row doesn't exist yet, create it (minimal MVP upsert).
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO companies (company_id, plan, status, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (company_id, plan, "active", datetime.utcnow().isoformat() + "Z"),
                )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("UPDATE PLAN ERROR:", str(e))
        msg = str(e)
        if "column" in msg and "plan" in msg and "does not exist" in msg:
            return JSONResponse(
                {"error": "Database schema missing companies.plan. Redeploy to run migrations."},
                status_code=500,
            )
        if "relation" in msg and "companies" in msg and "does not exist" in msg:
            return JSONResponse(
                {"error": "Database schema missing companies table. Redeploy to run migrations."},
                status_code=500,
            )
        # Surface a short DB detail so the UI can show something actionable.
        detail = msg[:200]
        return JSONResponse({"error": "Update plan error", "detail": detail}, status_code=500)

    finally:
        conn.close()


# =========================================================
# STRIPE PAYMENTS (MVP)
# =========================================================

def _stripe_config():
    secret_key = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    webhook_secret = (os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()
    price_starter = (os.getenv("STRIPE_PRICE_STARTER") or "").strip()
    price_pro = (os.getenv("STRIPE_PRICE_PRO") or "").strip()
    public_url = (os.getenv("APP_PUBLIC_URL") or "").strip().rstrip("/")
    return secret_key, webhook_secret, price_starter, price_pro, public_url


def _stripe_safe_error_info(err: Exception):
    # StripeError fields are safe; never include request body, api key, etc.
    try:
        code = getattr(err, "code", None)
        param = getattr(err, "param", None)
        user_message = getattr(err, "user_message", None) or getattr(err, "user_message", None)
        return {
            "type": type(err).__name__,
            "code": str(code) if code else "",
            "param": str(param) if param else "",
            "user_message": str(user_message) if user_message else "",
        }
    except Exception:
        return {"type": type(err).__name__, "code": "", "param": "", "user_message": ""}


@app.post("/api/stripe/create-checkout-session")
async def stripe_create_checkout_session(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    project_name = (data.get("projectName") or "ai_flow_saas").strip() or "ai_flow_saas"
    plan = (data.get("plan") or "").strip().lower()

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

    if plan not in ("starter", "pro"):
        return JSONResponse({"error": "Invalid plan. Use starter or pro."}, status_code=400)

    secret_key, webhook_secret, price_starter, price_pro, public_url = _stripe_config()
    if not secret_key or not webhook_secret or not public_url:
        return JSONResponse(
            {
                "error": "Stripe is not configured",
                "detail": "Missing STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PRICE_STARTER / STRIPE_PRICE_PRO / APP_PUBLIC_URL",
            },
            status_code=500,
        )

    # Validate env vars before calling Stripe.
    if not (secret_key.startswith("sk_test_") or secret_key.startswith("sk_live_")):
        return JSONResponse({"error": "Stripe is not configured", "detail": "Invalid STRIPE_SECRET_KEY"}, status_code=400)
    if not public_url.startswith("https://"):
        return JSONResponse({"error": "Stripe is not configured", "detail": "APP_PUBLIC_URL must start with https://"}, status_code=400)

    price_id = price_starter if plan == "starter" else price_pro
    if not price_id:
        return JSONResponse(
            {"error": "Stripe is not configured", "detail": f"Missing Stripe price id for {plan}"},
            status_code=500,
        )
    if not price_id.startswith("price_"):
        return JSONResponse({"error": "Stripe is not configured", "detail": f"Invalid Stripe price id for {plan}"}, status_code=400)

    stripe.api_key = secret_key

    # Use owner email from companies table if available (helps prefill Checkout).
    customer_email = ""
    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT owner_email FROM companies WHERE company_id = %s",
                (company_id,),
            )
            row = cur.fetchone()
            if row:
                customer_email = (row.get("owner_email") or "").strip()
    except Exception as e:
        print("STRIPE PREFILL EMAIL ERROR:", type(e).__name__)
        customer_email = ""
    finally:
        conn.close()

    success_url = f"{public_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{public_url}/payment/cancel"

    now = _iso_z(datetime.utcnow())

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email or None,
            metadata={"company_id": company_id, "project_name": project_name, "plan": plan},
        )
    except stripe.error.StripeError as e:
        info = _stripe_safe_error_info(e)
        print("STRIPE CREATE SESSION ERROR:", json.dumps(info, ensure_ascii=True))
        msg = info.get("user_message") or "Stripe checkout error. Please verify your Price IDs and Stripe keys."
        return JSONResponse({"error": msg, "code": info.get("code") or "", "param": info.get("param") or ""}, status_code=400)
    except Exception as e:
        print("STRIPE CREATE SESSION ERROR:", type(e).__name__)
        return JSONResponse({"error": "Stripe session create error"}, status_code=500)

    # Record session in DB (status stays "created"; webhook will mark "paid").
    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_payments (company_id, project_name, stripe_session_id, customer_email, amount, currency, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (stripe_session_id)
                DO NOTHING
                """,
                (
                    company_id,
                    project_name + ":" + plan,
                    session.get("id") or "",
                    customer_email or "",
                    0,
                    "",
                    "created",
                    now,
                ),
            )
        conn.commit()
    except Exception as e:
        print("STRIPE SAVE SESSION ERROR:", type(e).__name__)
        # Continue anyway; session is created, webhook can still insert later.
    finally:
        conn.close()

    checkout_url = ""
    try:
        checkout_url = getattr(session, "url", "") or ""
    except Exception:
        checkout_url = ""

    if not checkout_url:
        try:
            checkout_url = session["url"]
        except Exception:
            checkout_url = ""

    if not checkout_url:
        return JSONResponse(
            {"error": "Stripe session created but no checkout URL was returned. Check your Stripe API version/settings."},
            status_code=500,
        )

    return JSONResponse({"success": True, "url": checkout_url})


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    secret_key, webhook_secret, price_starter, price_pro, public_url = _stripe_config()
    if not secret_key or not webhook_secret:
        return JSONResponse({"error": "Stripe is not configured"}, status_code=500)
    if not (secret_key.startswith("sk_test_") or secret_key.startswith("sk_live_")):
        return JSONResponse({"error": "Stripe is not configured"}, status_code=500)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature") or ""

    stripe.api_key = secret_key

    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=webhook_secret)
    except stripe.error.StripeError as e:
        info = _stripe_safe_error_info(e)
        print("STRIPE WEBHOOK SIGNATURE ERROR:", json.dumps(info, ensure_ascii=True))
        return JSONResponse({"error": "Invalid signature"}, status_code=400)
    except Exception as e:
        # Never log payload/signature/secrets
        print("STRIPE WEBHOOK SIGNATURE ERROR:", type(e).__name__)
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    event_type = (event.get("type") or "").strip()
    obj = (event.get("data") or {}).get("object") or {}

    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session_id = (obj.get("id") or "").strip()
        payment_status = (obj.get("payment_status") or "").strip()  # usually "paid" for one-time; subscription varies
        currency = (obj.get("currency") or "").strip()
        amount_total = obj.get("amount_total")
        customer_email = (obj.get("customer_details") or {}).get("email") or (obj.get("customer_email") or "")

        metadata = obj.get("metadata") or {}
        company_id = (metadata.get("company_id") or "").strip()
        project_name = (metadata.get("project_name") or "").strip()
        plan = (metadata.get("plan") or "").strip()

        status = "paid" if payment_status == "paid" else "completed"
        now = _iso_z(datetime.utcnow())

        conn = get_db_connection()
        if not conn:
            return JSONResponse({"error": "Database error"}, status_code=500)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_payments (company_id, project_name, stripe_session_id, customer_email, amount, currency, status, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (stripe_session_id)
                    DO UPDATE SET
                        customer_email = EXCLUDED.customer_email,
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        status = EXCLUDED.status
                    """,
                    (
                        company_id,
                        project_name + ((":" + plan) if plan else ""),
                        session_id,
                        str(customer_email or "")[:200],
                        int(amount_total or 0),
                        str(currency or "")[:12],
                        status,
                        now,
                    ),
                )

                # Mark company as paid only when Stripe indicates paid.
                if company_id and status == "paid":
                    cur.execute(
                        """
                        UPDATE companies
                        SET payment_status = %s
                        WHERE company_id = %s
                        """,
                        ("paid", company_id),
                    )

            conn.commit()
        except Exception as e:
            print("STRIPE WEBHOOK DB ERROR:", type(e).__name__)
            return JSONResponse({"error": "Webhook DB error"}, status_code=500)
        finally:
            conn.close()

    return JSONResponse({"received": True})


@app.post("/connect-social-demo")
async def connect_social_demo(request: Request):
    data = await request.json()

    company_id = data.get("companyId", "")
    platform = data.get("platform", "")

    if not company_id or not platform:
        return JSONResponse(
            {"error": "Missing companyId or platform"},
            status_code=400,
        )

    now = datetime.utcnow().isoformat() + "Z"

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_social_accounts (
                    company_id,
                    platform,
                    status,
                    account_name,
                    account_id,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    company_id,
                    platform,
                    "connected",
                    platform + " Demo Account",
                    "demo_" + platform.lower(),
                    now,
                    now,
                ),
            )

        conn.commit()

        return JSONResponse({"success": True})

    except Exception as e:
        print("CONNECT SOCIAL DEMO ERROR:", str(e))

        return JSONResponse(
            {"error": "Connect social demo error"},
            status_code=500,
        )

    finally:
        conn.close()


# =========================================================
# CREATE DEMO DATA
# =========================================================

@app.post("/create-demo-data")
async def create_demo_data(request: Request):
    data = await request.json()

    company_id = data.get("companyId", "")

    if not company_id:
        return JSONResponse(
            {"error": "Missing companyId"},
            status_code=400,
        )

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500,
        )

    now = datetime.utcnow().isoformat() + "Z"

    try:
        with conn.cursor() as cur:
            demo_lead_emails = [
                "michael@example.com",
                "sarah@example.com",
                "david@example.com",
            ]

            cur.execute(
                """
                SELECT email
                FROM v2_leads
                WHERE company_id = %s
                AND email = ANY(%s)
                """,
                (company_id, demo_lead_emails),
            )
            existing_emails = {row[0] for row in cur.fetchall() if row and row[0]}

            demo_leads = [
                (
                    company_id,
                    "Michael Johnson",
                    "michael@example.com",
                    "+155500001",
                    "Instagram",
                    "new",
                    "Interested in AI automation",
                    now,
                ),
                (
                    company_id,
                    "Sarah Williams",
                    "sarah@example.com",
                    "+155500002",
                    "Website Chat",
                    "in_progress",
                    "Wants pricing",
                    now,
                ),
                (
                    company_id,
                    "David Miller",
                    "david@example.com",
                    "+155500003",
                    "Facebook",
                    "converted",
                    "Booked demo call",
                    now,
                ),
            ]

            for lead in demo_leads:
                if lead[2] in existing_emails:
                    continue
                cur.execute(
                    """
                    INSERT INTO v2_leads (
                        company_id,
                        name,
                        email,
                        phone,
                        source,
                        status,
                        message,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    lead,
                )

            demo_post_titles = [
                "AI automation post",
                "Lead generation ad",
                "Business automation insight",
            ]

            cur.execute(
                """
                SELECT title
                FROM v2_content_posts
                WHERE company_id = %s
                AND title = ANY(%s)
                """,
                (company_id, demo_post_titles),
            )
            existing_titles = {row[0] for row in cur.fetchall() if row and row[0]}

            demo_posts = [
                (
                    company_id,
                    "Instagram",
                    "caption",
                    "AI automation post",
                    "How AI can help your business reply faster and book more clients.",
                    "draft",
                    "system",
                    now,
                ),
                (
                    company_id,
                    "Facebook",
                    "ad",
                    "Lead generation ad",
                    "Stop losing leads. Let AI FLOW answer instantly and book appointments.",
                    "draft",
                    "system",
                    now,
                ),
                (
                    company_id,
                    "LinkedIn",
                    "post",
                    "Business automation insight",
                    "Small businesses can scale faster with AI sales agents and content systems.",
                    "approved",
                    "system",
                    now,
                ),
            ]

            for post in demo_posts:
                if post[3] in existing_titles:
                    continue
                cur.execute(
                    """
                    INSERT INTO v2_content_posts (
                        company_id,
                        platform,
                        post_type,
                        title,
                        content,
                        status,
                        created_by,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    post,
                )

        conn.commit()

        return JSONResponse({"success": True})

    except Exception as e:
        print("CREATE DEMO DATA ERROR:", str(e))

        return JSONResponse(
            {"error": "Create demo data error"},
            status_code=500,
        )

    finally:
        conn.close()


# =========================================================
# CONTENT FACTORY
# =========================================================

@app.post("/create-content-post")
async def create_content_post(request: Request):
    data = await request.json()

    company_id = data.get("companyId", "")
    platform = data.get("platform", "Instagram")
    post_type = data.get("postType", "caption")
    topic = data.get("topic", "AI automation for small business")

    if not company_id:
        return JSONResponse(
            {"error": "Missing companyId"},
            status_code=400,
        )

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return JSONResponse(
            {"error": "Missing GROQ_API_KEY"},
            status_code=500,
        )

    try:
        client = Groq(api_key=api_key.strip())

        prompt = f"""
Create a short social media post.

Platform: {platform}
Post type: {post_type}
Topic: {topic}

Rules:
- write in English
- short and clear
- sales-focused
- include one call to action
"""

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.5,
            max_tokens=250,
        )

        content = completion.choices[0].message.content
        now = datetime.utcnow().isoformat() + "Z"

        conn = get_db_connection()

        if not conn:
            return JSONResponse(
                {"error": "Database error"},
                status_code=500,
            )

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v2_content_posts (
                        company_id,
                        platform,
                        post_type,
                        title,
                        content,
                        status,
                        created_by,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        company_id,
                        platform,
                        post_type,
                        topic,
                        content,
                        "draft",
                        "ai",
                        now,
                    ),
                )

                post_id = cur.fetchone()[0]

            conn.commit()

        finally:
            conn.close()

        return JSONResponse(
            {
                "success": True,
                "post": {
                    "id": post_id,
                    "platform": platform,
                    "post_type": post_type,
                    "title": topic,
                    "content": content,
                    "status": "draft",
                    "created_at": now,
                },
            }
        )

    except Exception as e:
        print("CREATE CONTENT POST ERROR:", str(e))

        return JSONResponse(
            {"error": "AI content generation error"},
            status_code=500,
        )


# =========================================================
# CHAT API
# =========================================================

@app.get("/replies-data")
def replies_data(request: Request, companyId: str = ""):
    company_id, user, err = resolve_company_id(
        request,
        companyId,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    companyId = company_id

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_ai_replies
                WHERE company_id = %s
                ORDER BY id DESC
                """,
                (companyId,),
            )
            replies = cur.fetchall()

        return JSONResponse({"success": True, "replies": replies})

    except Exception as e:
        print("REPLIES DATA ERROR:", str(e))
        return JSONResponse({"error": "Replies data error"}, status_code=500)

    finally:
        conn.close()


@app.post("/create-ai-reply")
async def create_ai_reply(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    customer_name = (data.get("customerName") or "").strip()
    customer_message = (data.get("customerMessage") or "").strip()
    source = (data.get("source") or "Website").strip() or "Website"

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    if not customer_message:
        return JSONResponse({"error": "Missing customerMessage"}, status_code=400)

    fallback = (
        "Thanks for reaching out. We can help with that. What is the best phone number or email to contact you?"
    )

    ai_reply = fallback
    api_key = os.getenv("GROQ_API_KEY")

    if api_key:
        try:
            client = Groq(api_key=api_key.strip())
            prompt = f"""
You are AI FLOW sales assistant. Write a short, helpful reply.

Context:
- Source: {source}
- Customer name: {customer_name or "Customer"}

Customer message:
{customer_message}

Rules:
- write in English
- 2-4 short sentences
- be helpful and sales-oriented
- ask one follow-up question (contact info or next step)
"""

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=180,
            )
            ai_reply = (completion.choices[0].message.content or "").strip() or fallback
        except Exception as e:
            print("CREATE AI REPLY GROQ ERROR:", str(e))
            ai_reply = fallback

    status = "draft"
    created_at = now_utc_iso()

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO v2_ai_replies (
                    company_id,
                    customer_name,
                    customer_message,
                    ai_reply,
                    status,
                    source,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    company_id,
                    customer_name,
                    customer_message,
                    ai_reply,
                    status,
                    source,
                    created_at,
                ),
            )
            reply_id = cur.fetchone()[0]

        conn.commit()
        return JSONResponse(
            {
                "success": True,
                "reply": {
                    "id": reply_id,
                    "company_id": company_id,
                    "customer_name": customer_name,
                    "customer_message": customer_message,
                    "ai_reply": ai_reply,
                    "status": status,
                    "source": source,
                    "created_at": created_at,
                },
            }
        )

    except Exception as e:
        print("CREATE AI REPLY ERROR:", str(e))
        return JSONResponse({"error": "Create ai reply error"}, status_code=500)

    finally:
        conn.close()


@app.post("/update-reply-status")
async def update_reply_status(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    reply_id = data.get("id")
    status = (data.get("status") or "").strip()

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    try:
        reply_id_int = int(reply_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    allowed = {"draft", "sent", "archived"}
    if status not in allowed:
        return JSONResponse({"error": "Invalid status"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE v2_ai_replies
                SET status = %s
                WHERE company_id = %s
                AND id = %s
                """,
                (status, company_id, reply_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("UPDATE REPLY STATUS ERROR:", str(e))
        return JSONResponse({"error": "Update reply status error"}, status_code=500)

    finally:
        conn.close()


@app.post("/delete-reply")
async def delete_reply(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    reply_id = data.get("id")

    company_id, user, err = resolve_company_id(
        request,
        company_id,
        allow_public=False,
        allow_platform_admin_any=True,
    )
    if err:
        return err
    if not user or not is_role(user, ROLE_PLATFORM_ADMIN, ROLE_COMPANY_ADMIN, ROLE_EMPLOYEE):
        return json_error("Forbidden", 403)

    try:
        reply_id_int = int(reply_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM v2_ai_replies
                WHERE company_id = %s
                AND id = %s
                """,
                (company_id, reply_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("DELETE REPLY ERROR:", str(e))
        return JSONResponse({"error": "Delete reply error"}, status_code=500)

    finally:
        conn.close()


@app.post("/update-ai-reply")
async def update_ai_reply(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    reply_id = data.get("id")
    status = data.get("status")
    ai_reply = data.get("aiReply")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    try:
        reply_id_int = int(reply_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    set_clauses = []
    params = []

    if status is not None:
        status_value = (str(status) or "").strip()
        if not status_value:
            return JSONResponse({"error": "Invalid status"}, status_code=400)
        set_clauses.append("status = %s")
        params.append(status_value)

    if ai_reply is not None:
        set_clauses.append("ai_reply = %s")
        params.append(str(ai_reply))

    if not set_clauses:
        return JSONResponse({"error": "Nothing to update"}, status_code=400)

    params.extend([company_id, reply_id_int])

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE v2_ai_replies
                SET {", ".join(set_clauses)}
                WHERE company_id = %s
                AND id = %s
                """,
                tuple(params),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("UPDATE AI REPLY ERROR:", str(e))
        return JSONResponse({"error": "Update ai reply error"}, status_code=500)

    finally:
        conn.close()


@app.post("/delete-ai-reply")
async def delete_ai_reply(request: Request):
    data = await request.json()

    company_id = (data.get("companyId") or "").strip()
    reply_id = data.get("id")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

    try:
        reply_id_int = int(reply_id)
    except Exception:
        return JSONResponse({"error": "Invalid id"}, status_code=400)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM v2_ai_replies
                WHERE company_id = %s
                AND id = %s
                """,
                (company_id, reply_id_int),
            )

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("DELETE AI REPLY ERROR:", str(e))
        return JSONResponse({"error": "Delete ai reply error"}, status_code=500)

    finally:
        conn.close()


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()

    message = data.get("message", "")
    company_id = (data.get("companyId") or "").strip()
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return JSONResponse(
            {
                "reply": "AI is not connected yet.",
            }
        )

    try:
        client = Groq(api_key=api_key.strip())

        system_prompt = "You are AI FLOW sales assistant. Reply short and helpful."

        if company_id:
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute(
                            """
                            SELECT company_name
                            FROM companies
                            WHERE company_id = %s
                            """,
                            (company_id,),
                        )
                        c = cur.fetchone() or {}

                        cur.execute(
                            """
                            SELECT assistant_name, ai_tone, ai_goal, business_description, lead_question
                            FROM v2_company_settings
                            WHERE company_id = %s
                            """,
                            (company_id,),
                        )
                        s = cur.fetchone() or {}

                    assistant_name = (s.get("assistant_name") or "AI FLOW Assistant").strip()
                    company_name = (c.get("company_name") or "").strip() or "this business"
                    ai_tone = (s.get("ai_tone") or "Friendly").strip()
                    ai_goal = (s.get("ai_goal") or "Capture leads").strip()
                    business_description = (s.get("business_description") or "").strip()
                    lead_question = (s.get("lead_question") or "").strip() or (
                        "What is the best phone number or email to contact you?"
                    )

                    # Keep prompt short and safe.
                    if len(business_description) > 600:
                        business_description = business_description[:600].rstrip() + "..."

                    system_prompt = (
                        f"You are {assistant_name}, AI sales assistant for {company_name}.\n"
                        f"Tone: {ai_tone}.\n"
                        f"Goal: {ai_goal}.\n"
                        f"Business info: {business_description or 'N/A'}.\n"
                        f"If user seems interested, ask for contact info using: {lead_question}\n"
                        "Keep replies short and helpful."
                    )
                except Exception as e:
                    print("CHAT SETTINGS ERROR:", str(e))
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            temperature=0.3,
            max_tokens=200,
        )

        return JSONResponse(
            {
                "reply": completion.choices[0].message.content,
            }
        )

    except Exception as e:
        print("CHAT ERROR:", str(e))

        return JSONResponse(
            {
                "reply": "AI connection error.",
            }
        )
