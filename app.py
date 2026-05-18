from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    HTMLResponse,
    PlainTextResponse,
)
from fastapi.middleware.cors import CORSMiddleware

from groq import Groq

import os
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import hashlib

from datetime import datetime, timedelta

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
                    google_connected BOOLEAN DEFAULT FALSE,
                    google_email TEXT DEFAULT '',
                    google_name TEXT DEFAULT '',
                    access_token TEXT DEFAULT '',
                    refresh_token TEXT DEFAULT '',
                    calendar_id TEXT DEFAULT 'primary',
                    sheet_id TEXT DEFAULT '',
                    connected_at TEXT DEFAULT '',
                    token_refreshed_at TEXT DEFAULT ''
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
    return FileResponse(
        "widget.js",
        media_type="application/javascript"
    )


@app.get("/privacy.html", response_class=HTMLResponse)
def privacy_page():

    if not os.path.exists("privacy.html"):
        return HTMLResponse(
            "<h1>Privacy Policy not found</h1>",
            status_code=404
        )

    with open("privacy.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/terms.html", response_class=HTMLResponse)
def terms_page():

    if not os.path.exists("terms.html"):
        return HTMLResponse(
            "<h1>Terms not found</h1>",
            status_code=404
        )

    with open("terms.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/data-deletion.html", response_class=HTMLResponse)
def data_deletion_page():

    if not os.path.exists("data-deletion.html"):
        return HTMLResponse(
            "<h1>Data Deletion page not found</h1>",
            status_code=404
        )

    with open("data-deletion.html", "r", encoding="utf-8") as f:
        return f.read()


# =========================================================
# AUTH SYSTEM
# =========================================================

@app.post("/register")
async def register(request: Request):

    data = await request.json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email or not password:
        return JSONResponse(
            {"error": "Missing email or password"},
            status_code=400
        )

    hashed_password = hashlib.sha256(
        password.encode()
    ).hexdigest()

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500
        )

    try:
        with conn.cursor() as cur:

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
                    email,
                    datetime.utcnow().isoformat() + "Z",
                )
            )

        conn.commit()

        return JSONResponse({
            "success": True,
            "email": email
        })

    except Exception as e:
        print("REGISTER ERROR:", str(e))

        return JSONResponse(
            {"error": "User already exists"},
            status_code=400
        )

    finally:
        conn.close()


@app.post("/login-api")
async def login_api(request: Request):

    data = await request.json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    hashed_password = hashlib.sha256(
        password.encode()
    ).hexdigest()

    conn = get_db_connection()

    if not conn:
        return JSONResponse(
            {"error": "Database error"},
            status_code=500
        )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(
                """
                SELECT * FROM users
                WHERE email = %s
                AND password = %s
                """,
                (
                    email,
                    hashed_password,
                )
            )

            user = cur.fetchone()

            if not user:
                return JSONResponse(
                    {"error": "Invalid credentials"},
                    status_code=401
                )

            return JSONResponse({
                "success": True,
                "email": user["email"],
                "role": user["role"],
                "companyId": user["company_id"]
            })

    except Exception as e:
        print("LOGIN ERROR:", str(e))

        return JSONResponse(
            {"error": "Login failed"},
            status_code=500
        )

    finally:
        conn.close()


# =========================================================
# LEADS
# =========================================================

@app.get("/leads")
def get_leads():

    if not os.path.exists(LEADS_FILE):
        return JSONResponse({"leads": []})

    try:
        with open(LEADS_FILE, "r", encoding="utf-8") as f:
            leads = json.load(f)

        return JSONResponse({"leads": leads})

    except Exception:
        return JSONResponse({"leads": []})


# =========================================================
# HELPERS
# =========================================================

def extract_email(text: str):

    match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )

    return match.group(0) if match else ""


def extract_phone(text: str):

    match = re.search(
        r"(\+?\d[\d\s\-\(\)]{7,}\d)",
        text,
    )

    return match.group(0).strip() if match else ""


def detect_language_hint(text: str):

    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"

    if re.search(r"[\u0590-\u05FF]", text):
        return "he"

    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"

    return "auto"


def save_lead_local(lead):

    leads = []

    if os.path.exists(LEADS_FILE):
        try:
            with open(LEADS_FILE, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except Exception:
            leads = []

    leads.append(lead)

    with open(LEADS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            leads,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# AI REPLY
# =========================================================

def build_ai_reply(
    message,
    company_id,
    site_name,
    business_type,
    offer,
    price,
    payment_link,
):

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return "AI is not connected yet. Please try again later."

    client = Groq(api_key=api_key.strip())

    system_prompt = f"""
You are an AI sales assistant.

Company:
{site_name}

Offer:
{offer}

Price:
{price}

Payment:
{payment_link}

Rules:
- reply short
- be friendly
- answer in same language
- help convert lead
"""

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

    return completion.choices[0].message.content


# =========================================================
# CHAT API
# =========================================================

@app.post("/chat")
async def chat(request: Request):

    data = await request.json()

    message = data.get("message", "")
    company_id = data.get("companyId", "default_company")
    site_name = data.get("siteName", "AI FLOW")
    business_type = data.get("businessType", "AI SaaS")
    offer = data.get("offer", "AI Sales Assistant")
    price = data.get("price", "$99/month")

    payment_link = data.get(
        "paymentLink",
        "https://buy.stripe.com/test"
    )

    email = extract_email(message)
    phone = extract_phone(message)

    try:

        reply = build_ai_reply(
            message=message,
            company_id=company_id,
            site_name=site_name,
            business_type=business_type,
            offer=offer,
            price=price,
            payment_link=payment_link,
        )

        return JSONResponse(
            {
                "reply": reply,
                "email": email,
                "phone": phone,
                "companyId": company_id,
            }
        )

    except Exception as e:

        print("CHAT ERROR:", str(e))

        return JSONResponse(
            {
                "reply": "AI connection error.",
            }
        )
