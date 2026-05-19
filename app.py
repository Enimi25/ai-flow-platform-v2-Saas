from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import hashlib
from pathlib import Path
from datetime import datetime

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

        return JSONResponse({"success": True, "company": company, "settings": settings})

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

        conn.commit()
        return JSONResponse({"success": True})

    except Exception as e:
        print("UPDATE PLAN ERROR:", str(e))
        return JSONResponse({"error": "Update plan error"}, status_code=500)

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
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return JSONResponse(
            {
                "reply": "AI is not connected yet.",
            }
        )

    try:
        client = Groq(api_key=api_key.strip())

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are AI FLOW sales assistant. Reply short and helpful.",
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
