Вот полный app.py целиком под замену:

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
