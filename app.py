from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import hashlib
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor


app = FastAPI()


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

@app.get("/")
def home():
    return FileResponse("index.html")


@app.get("/login")
def login_page():
    return FileResponse("login.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("dashboard.html")


@app.get("/leads-page")
def leads_page():
    return FileResponse("leads.html")


@app.get("/content-factory")
def content_factory_page():
    return FileResponse("content.html")

@app.get("/settings")
def settings_page():
    return FileResponse("settings.html")

@app.get("/social-accounts")
def social_accounts_page():
    return FileResponse("social.html")


@app.get("/ai-replies")
def ai_replies_page():
    return FileResponse("replies.html")

@app.get("/billing")
def billing_page():
    return FileResponse("billing.html")

@app.get("/analytics")
def analytics_page():
    return FileResponse("analytics.html")


@app.get("/calendar")
def calendar_page():
    return FileResponse("calendar.html")


@app.get("/admin")
def admin_page():
    return FileResponse("admin.html")


@app.get("/widget.js")
def widget():
    return FileResponse("widget.js", media_type="application/javascript")


@app.get("/privacy.html", response_class=HTMLResponse)
def privacy_page():
    if not os.path.exists("privacy.html"):
        return HTMLResponse("<h1>Privacy Policy not found</h1>", status_code=404)

    with open("privacy.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/terms.html", response_class=HTMLResponse)
def terms_page():
    if not os.path.exists("terms.html"):
        return HTMLResponse("<h1>Terms not found</h1>", status_code=404)

    with open("terms.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/data-deletion.html", response_class=HTMLResponse)
def data_deletion_page():
    if not os.path.exists("data-deletion.html"):
        return HTMLResponse("<h1>Data Deletion page not found</h1>", status_code=404)

    with open("data-deletion.html", "r", encoding="utf-8") as f:
        return f.read()


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

        return JSONResponse(
            {
                "success": True,
                "stats": {
                    "total_leads": total_leads,
                    "ai_conversations": total_leads,
                    "social_posts": total_posts,
                    "bookings": total_bookings,
                    "conversion_rate": "0%",
                },
                "leads": leads,
                "posts": posts,
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


# =========================================================
# SOCIAL ACCOUNTS
# =========================================================

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
