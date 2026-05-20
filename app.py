from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import json
import secrets
import urllib.parse
import urllib.request

import psycopg2
from psycopg2.extras import RealDictCursor


app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT DEFAULT 'client',
                    company_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

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

            # Short-lived OAuth state store for Meta connect flow.
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS v2_meta_oauth_states (
                    state TEXT PRIMARY KEY,
                    company_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                );
                """
            )

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


# =========================================================
# STATIC PAGES
# =========================================================

def page_response(filename: str, media_type: str | None = None):
    return FileResponse(BASE_DIR / filename, media_type=media_type)


@app.get("/")
def home():
    return page_response("index.html")


@app.get("/login")
def login_page():
    return page_response("login.html")


@app.get("/dashboard")
def dashboard_page():
    return page_response("dashboard.html")


@app.get("/leads-page")
def leads_page():
    return page_response("leads.html")


@app.get("/content-factory")
def content_factory_page():
    return page_response("content.html")

@app.get("/settings")
def settings_page():
    return page_response("settings.html")

@app.get("/social-accounts")
def social_accounts_page():
    return page_response("social.html")


@app.get("/ai-replies")
def ai_replies_page():
    return page_response("replies.html")

@app.get("/billing")
def billing_page():
    return page_response("billing.html")

@app.get("/analytics")
def analytics_page():
    return page_response("analytics.html")


@app.get("/calendar")
def calendar_page():
    return page_response("calendar.html")


@app.get("/admin")
def admin_page():
    return page_response("admin.html")

@app.get("/onboarding")
def onboarding_page():
    return page_response("onboarding.html")

@app.get("/admin-data")
def admin_data():
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


@app.get("/privacy.html", response_class=HTMLResponse)
def privacy_page():
    path = BASE_DIR / "privacy.html"
    if not path.exists():
        return HTMLResponse("<h1>Privacy Policy not found</h1>", status_code=404)

    return path.read_text(encoding="utf-8")


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

    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    company_id = email
    created_at = datetime.utcnow().isoformat() + "Z"

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
                    role,
                    company_id,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    email,
                    hashed_password,
                    "client",
                    company_id,
                    created_at,
                ),
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

    hashed_password = hashlib.sha256(password.encode()).hexdigest()

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
                AND password = %s
                """,
                (
                    email,
                    hashed_password,
                ),
            )

            user = cur.fetchone()

            if not user:
                return JSONResponse(
                    {"error": "Invalid credentials"},
                    status_code=401,
                )

            return JSONResponse(
                {
                    "success": True,
                    "email": user["email"],
                    "role": user["role"],
                    "companyId": user["company_id"],
                }
            )

    except Exception as e:
        print("LOGIN ERROR:", str(e))

        return JSONResponse(
            {"error": "Login failed"},
            status_code=500,
        )

    finally:
        conn.close()


# =========================================================
# DASHBOARD DATA
# =========================================================

@app.get("/dashboard-data")
def dashboard_data(companyId: str = ""):
    if not companyId:
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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

    now = datetime.utcnow().isoformat() + "Z"

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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


def _tiktok_config():
    client_key = (os.getenv("TIKTOK_CLIENT_KEY") or "").strip()
    client_secret = (os.getenv("TIKTOK_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("TIKTOK_REDIRECT_URI") or "").strip()
    return client_key, client_secret, redirect_uri


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
def meta_connect(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

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

    state = secrets.token_urlsafe(32)
    now = _iso_z(datetime.utcnow())
    cutoff = _iso_z(datetime.utcnow() - timedelta(minutes=30))

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            # Cleanup old states to avoid DB growth
            cur.execute("DELETE FROM v2_meta_oauth_states WHERE created_at < %s", (cutoff,))
            cur.execute(
                """
                INSERT INTO v2_meta_oauth_states (state, company_id, created_at)
                VALUES (%s, %s, %s)
                """,
                (state, company_id, now),
            )
        conn.commit()
    finally:
        conn.close()

    # Minimal scopes for Pages list + IG business account discovery.
    scope = ",".join(
        [
            "public_profile",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_metadata",
            "instagram_basic",
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
def meta_callback(code: str = "", state: str = ""):
    if not code or not state:
        return JSONResponse({"error": "Missing code/state"}, status_code=400)

    app_id, app_secret, redirect_uri = _meta_config()
    if not app_id or not app_secret or not redirect_uri:
        return JSONResponse({"error": "Meta OAuth is not configured"}, status_code=500)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    company_id = ""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id, created_at FROM v2_meta_oauth_states WHERE state = %s",
                (state,),
            )
            row = cur.fetchone()
            if row:
                if _oauth_state_is_fresh(row.get("created_at") or ""):
                    company_id = row.get("company_id") or ""
            cur.execute("DELETE FROM v2_meta_oauth_states WHERE state = %s", (state,))
        conn.commit()
    finally:
        conn.close()

    if not company_id:
        return JSONResponse({"error": "Invalid state"}, status_code=400)

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
        return JSONResponse({"error": "Meta token exchange error"}, status_code=500)

    if not user_token:
        return JSONResponse({"error": "Meta token exchange failed"}, status_code=500)

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
        return JSONResponse({"error": "Database error"}, status_code=500)

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
        return JSONResponse({"error": "Meta callback save error"}, status_code=500)
    finally:
        conn.close()

    # Redirect back to Social Accounts page
    return HTMLResponse(
        """<!doctype html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#061923;color:#f7fbff;padding:24px;">
Connected. You can close this tab.
<script>window.location.href='/social-accounts?meta=connected';</script>
</body></html>"""
    )


@app.get("/api/meta/accounts")
def meta_accounts(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

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
# TIKTOK OAUTH (MVP)
# =========================================================

@app.get("/api/tiktok/connect")
def tiktok_connect(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

    client_key, client_secret, redirect_uri = _tiktok_config()
    if not client_key or not client_secret or not redirect_uri:
        return JSONResponse(
            {
                "error": "TikTok OAuth is not configured",
                "detail": "Missing TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_REDIRECT_URI",
            },
            status_code=500,
        )
    uri_err = _validate_redirect_uri(redirect_uri, "tiktok")
    if uri_err:
        return JSONResponse({"error": "TikTok OAuth redirect URI is invalid", "detail": uri_err}, status_code=500)

    state = secrets.token_urlsafe(32)
    now = _iso_z(datetime.utcnow())
    cutoff = _iso_z(datetime.utcnow() - timedelta(minutes=30))

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM v2_tiktok_oauth_states WHERE created_at < %s", (cutoff,))
            cur.execute(
                """
                INSERT INTO v2_tiktok_oauth_states (state, company_id, created_at)
                VALUES (%s, %s, %s)
                """,
                (state, company_id, now),
            )
        conn.commit()
    finally:
        conn.close()

    # Keep scopes minimal for MVP (connect + show account). Publishing scopes require TikTok review/audit.
    scope = "user.info.basic"

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

    return HTMLResponse(
        f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={auth_url}"></head>
<body style="font-family:Arial,sans-serif;background:#061923;color:#f7fbff;padding:24px;">
Redirecting to TikTok OAuth...
</body></html>"""
    )


@app.get("/api/tiktok/callback")
def tiktok_callback(code: str = "", state: str = ""):
    if not code or not state:
        return JSONResponse({"error": "Missing code/state"}, status_code=400)

    client_key, client_secret, redirect_uri = _tiktok_config()
    if not client_key or not client_secret or not redirect_uri:
        return JSONResponse({"error": "TikTok OAuth is not configured"}, status_code=500)

    conn = get_db_connection()
    if not conn:
        return JSONResponse({"error": "Database error"}, status_code=500)

    company_id = ""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT company_id, created_at FROM v2_tiktok_oauth_states WHERE state = %s",
                (state,),
            )
            row = cur.fetchone()
            if row:
                if _oauth_state_is_fresh(row.get("created_at") or ""):
                    company_id = (row.get("company_id") or "").strip()
            cur.execute("DELETE FROM v2_tiktok_oauth_states WHERE state = %s", (state,))
        conn.commit()
    finally:
        conn.close()

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
def tiktok_account(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

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

@app.get("/bookings-data")
def bookings_data(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not client_name or not date_value or not time_value:
        return JSONResponse({"error": "Missing clientName, date, or time"}, status_code=400)

    meeting_time = f"{date_value} {time_value}"
    meeting_link = meeting_type or ""
    status = "booked"
    created_at = datetime.utcnow().isoformat() + "Z"

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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
def social_data(companyId: str = ""):
    if not companyId:
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

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM v2_social_accounts
                WHERE company_id = %s
                ORDER BY id DESC
                """,
                (companyId,),
            )

            accounts = cur.fetchall()

        return JSONResponse(
            {
                "success": True,
                "accounts": accounts,
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

    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            client = Groq(api_key=api_key.strip())
            prompt = f"""
Generate ONE social content draft for AI FLOW client.

Company: {company_name or "Client"}
Platform: {platform}
Draft type: {draft_type}
Date: {date_str}

Return JSON ONLY with keys:
title, caption, hook, hashtags, visual_idea

Rules:
- write in English
- keep it short and clear
- hashtags should be one string with # tags
- caption can include short script if type is reel/video
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
    """Create at least 1 draft per day; we generate 1 per platform for a better MVP experience."""
    today = _today_utc_date_str()
    now = _iso_z(datetime.utcnow())

    conn = get_db_connection()
    if not conn:
        return False, "Database error"

    try:
        # Create missing daily drafts (atomic-ish via INSERT ... SELECT ... WHERE NOT EXISTS).
        platforms = ["Facebook", "Instagram", "TikTok"]
        for platform in platforms:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM v2_social_content_drafts
                    WHERE company_id = %s AND content_date = %s AND platform = %s
                    LIMIT 1
                    """,
                    (company_id, today, platform),
                )
                already = cur.fetchone() is not None

            if already:
                continue

            types = _SOCIAL_DRAFT_TYPES_BY_PLATFORM.get(platform) or ["AI tip"]
            # Deterministic pick per day/platform.
            idx = (int(today.replace("-", "")) + len(platform)) % len(types)
            draft_type = types[idx]
            draft = _generate_social_draft(company_id, platform, draft_type)

            with conn.cursor() as cur:
                # Prevent duplicates if multiple requests race.
                cur.execute(
                    """
                    INSERT INTO v2_social_content_drafts (
                        company_id, content_date, platform, draft_type,
                        title, caption, hook, hashtags, visual_idea,
                        status, publish_message, created_at, updated_at
                    )
                    SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM v2_social_content_drafts
                        WHERE company_id = %s AND content_date = %s AND platform = %s
                    )
                    """,
                    (
                        company_id,
                        today,
                        platform,
                        draft_type,
                        draft.get("title") or "",
                        draft.get("caption") or "",
                        draft.get("hook") or "",
                        draft.get("hashtags") or "",
                        draft.get("visual_idea") or "",
                        "draft",
                        "",
                        now,
                        now,
                        company_id,
                        today,
                        platform,
                    ),
                )

        conn.commit()
        return True, ""
    except Exception as e:
        print("ENSURE DAILY SOCIAL DRAFTS ERROR:", str(e))
        return False, "Social draft generation error"
    finally:
        conn.close()


@app.get("/social-content-data")
def social_content_data(companyId: str = ""):
    company_id = (companyId or "").strip()
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)

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
    company_id = (data.get("companyId") or "").strip()
    draft_id = data.get("id")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)
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
    company_id = (data.get("companyId") or "").strip()
    draft_id = data.get("id")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)
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
    company_id = (data.get("companyId") or "").strip()
    draft_id = data.get("id")
    status = (data.get("status") or "").strip()

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)
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
    company_id = (data.get("companyId") or "").strip()
    draft_id = data.get("id")

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
    if not _company_exists(company_id):
        return JSONResponse({"error": "Unknown companyId"}, status_code=404)
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
def analytics_data(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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
def settings_data(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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
                SELECT company_id, company_name, owner_email, plan, status, created_at
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
    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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
    updated_at = datetime.utcnow().isoformat() + "Z"

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
def billing_data(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
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
def replies_data(companyId: str = ""):
    if not companyId:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)
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
    created_at = datetime.utcnow().isoformat() + "Z"

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

    if not company_id:
        return JSONResponse({"error": "Missing companyId"}, status_code=400)

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
