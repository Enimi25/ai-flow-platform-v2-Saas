from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import json
import re
import hashlib
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor


app = FastAPI()

LEADS_FILE = "leads.json"


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
async def login_page():
    return FileResponse("login.html")


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("dashboard.html")


@app.get("/admin")
async def admin_page():
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
