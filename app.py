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


def get_company(company_id):
    conn = get_db_connection()

    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM companies WHERE company_id = %s",
                (company_id,),
            )
            row = cur.fetchone()

            if not row:
                return None

            return dict(row)

    except Exception as e:
        print("GET COMPANY ERROR:", str(e))
        return None

    finally:
        conn.close()


def upsert_company(company):
    conn = get_db_connection()

    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO companies (
                    company_id,
                    google_connected,
                    google_email,
                    google_name,
                    access_token,
                    refresh_token,
                    calendar_id,
                    sheet_id,
                    connected_at,
                    token_refreshed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id) DO UPDATE SET
                    google_connected = EXCLUDED.google_connected,
                    google_email = EXCLUDED.google_email,
                    google_name = EXCLUDED.google_name,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    calendar_id = EXCLUDED.calendar_id,
                    sheet_id = EXCLUDED.sheet_id,
                    connected_at = EXCLUDED.connected_at,
                    token_refreshed_at = EXCLUDED.token_refreshed_at;
                """,
                (
                    company.get("company_id", ""),
                    company.get("google_connected", False),
                    company.get("google_email", ""),
                    company.get("google_name", ""),
                    company.get("access_token", ""),
                    company.get("refresh_token", ""),
                    company.get("calendar_id", "primary"),
                    company.get("sheet_id", ""),
                    company.get("connected_at", ""),
                    company.get("token_refreshed_at", ""),
                ),
            )

        conn.commit()
        return True

    except Exception as e:
        print("UPSERT COMPANY ERROR:", str(e))
        return False

    finally:
        conn.close()


def update_company_access_token(company_id, access_token):
    conn = get_db_connection()

    if not conn:
        return False

    try:
        token_refreshed_at = datetime.utcnow().isoformat() + "Z"

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE companies
                SET access_token = %s,
                    token_refreshed_at = %s
                WHERE company_id = %s
                """,
                (
                    access_token,
                    token_refreshed_at,
                    company_id,
                ),
            )

        conn.commit()
        return True

    except Exception as e:
        print("UPDATE ACCESS TOKEN ERROR:", str(e))
        return False

    finally:
        conn.close()


def get_all_companies_safe():
    conn = get_db_connection()

    if not conn:
        return {}

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    company_id,
                    google_connected,
                    google_email,
                    google_name,
                    calendar_id,
                    sheet_id,
                    connected_at
                FROM companies
                ORDER BY connected_at DESC
                """
            )

            rows = cur.fetchall()
            result = {}

            for row in rows:
                result[row["company_id"]] = {
                    "companyId": row["company_id"],
                    "google_connected": row["google_connected"],
                    "google_email": row["google_email"],
                    "google_name": row["google_name"],
                    "calendar_id": row["calendar_id"],
                    "sheet_id": row["sheet_id"],
                    "connected_at": row["connected_at"],
                }

            return result

    except Exception as e:
        print("GET ALL COMPANIES ERROR:", str(e))
        return {}

    finally:
        conn.close()


# =========================================================
# STATIC PAGES
# =========================================================

@app.get("/")
def home():
    return FileResponse("index.html")


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
        json.dump(leads, f, ensure_ascii=False, indent=2)


# =========================================================
# GOOGLE SHEETS
# =========================================================

def save_lead_to_google_sheets(lead):
    webhook_url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

    if not webhook_url:
        print("GOOGLE_SHEETS_WEBHOOK_URL is missing")
        return False

    try:
        payload = json.dumps(lead).encode("utf-8")

        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AI-Sales-Assistant/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            print("GOOGLE SHEETS RESPONSE:", body)
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("GOOGLE SHEETS HTTP ERROR:", e.code, error_body)
        return False

    except Exception as e:
        print("GOOGLE SHEETS ERROR:", str(e))
        return False


# =========================================================
# GOOGLE CALENDAR
# =========================================================

def refresh_google_access_token(company_id):
    company = get_company(company_id)

    if not company:
        print("No company found for calendar:", company_id)
        return ""

    refresh_token = company.get("refresh_token", "")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not refresh_token:
        print("No refresh token for company:", company_id)
        return ""

    if not client_id or not client_secret:
        print("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")
        return ""

    try:
        payload = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            token_data = json.loads(response.read().decode("utf-8"))
            access_token = token_data.get("access_token", "")

            if access_token:
                update_company_access_token(company_id, access_token)

            return access_token

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("GOOGLE TOKEN HTTP ERROR:", e.code, error_body)
        return ""

    except Exception as e:
        print("GOOGLE TOKEN ERROR:", str(e))
        return ""


def parse_calendar_datetime(message):
    now = datetime.now()
    msg = message.lower()

    hour = 12
    minute = 0

    time_match = re.search(r"(\d{1,2})[:.](\d{2})", msg)

    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        hour_match = re.search(r"(?:в|at)\s+(\d{1,2})", msg)

        if hour_match:
            hour = int(hour_match.group(1))
            minute = 0

    if "послезавтра" in msg:
        event_date = now + timedelta(days=2)
    elif "завтра" in msg or "tomorrow" in msg:
        event_date = now + timedelta(days=1)
    else:
        event_date = now + timedelta(days=1)

    start = event_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    end = start + timedelta(minutes=30)

    return start, end


def create_google_calendar_event(company_id, lead):
    company = get_company(company_id)

    if not company or not company.get("google_connected"):
        print("Calendar not connected for company:", company_id)
        return False

    access_token = refresh_google_access_token(company_id)

    if not access_token:
        print("No access token for calendar event")
        return False

    try:
        message = lead.get("message", "")
        phone = lead.get("phone", "")
        email = lead.get("email", "")
        site_name = lead.get("siteName", "AI Sales Assistant")

        start_dt, end_dt = parse_calendar_datetime(message)

        title_contact = phone or email or "new lead"
        summary = "AI Sales Lead — " + title_contact

        description = (
            "New lead from AI Sales Assistant\n\n"
            + "Company ID: "
            + lead.get("companyId", "")
            + "\n"
            + "Site: "
            + site_name
            + "\n"
            + "Source: "
            + lead.get("source", "")
            + "\n"
            + "Language: "
            + lead.get("language", "")
            + "\n"
            + "Phone: "
            + phone
            + "\n"
            + "Email: "
            + email
            + "\n"
            + "Message: "
            + message
            + "\n"
        )

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Jerusalem",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Jerusalem",
            },
        }

        calendar_id = company.get("calendar_id", "primary")

        url = (
            "https://www.googleapis.com/calendar/v3/calendars/"
            + urllib.parse.quote(calendar_id, safe="")
            + "/events"
        )

        payload = json.dumps(event).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": "Bearer " + access_token,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read().decode("utf-8")
            print("GOOGLE CALENDAR RESPONSE:", body)
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("GOOGLE CALENDAR HTTP ERROR:", e.code, error_body)
        return False

    except Exception as e:
        print("GOOGLE CALENDAR ERROR:", str(e))
        return False


# =========================================================
# LEADS
# =========================================================

def save_lead(message, email, phone, source, language, site_name, company_id):
    lead = {
        "time": datetime.utcnow().isoformat() + "Z",
        "companyId": company_id,
        "siteName": site_name,
        "source": source,
        "language": language,
        "message": message,
        "email": email,
        "phone": phone,
        "status": "new",
    }

    save_lead_local(lead)

    saved_to_sheets = save_lead_to_google_sheets(lead)
    saved_to_calendar = create_google_calendar_event(company_id, lead)

    return {
        "lead": lead,
        "saved_to_sheets": saved_to_sheets,
        "saved_to_calendar": saved_to_calendar,
    }


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
You are an AI sales assistant for a business.

ABSOLUTE LANGUAGE RULE:
- Understand all major human languages.
- Always answer in the same language as the user's intent.
- If the user writes in Russian Cyrillic, answer in Russian Cyrillic.
- If the user writes Russian using Latin letters / transliteration, answer in normal Russian Cyrillic.
- Examples:
  "privet" means "привет"
  "skolko stoit" means "сколько стоит"
  "a vy est v instagram" means "а вы есть в Instagram"
  "hochu zapisatsya" means "хочу записаться"
  "kak oplatit" means "как оплатить"
- If the user writes in English, answer in English.
- If the user writes in Hebrew, answer in Hebrew.
- If the user writes in Spanish, answer in Spanish.
- If the user writes in Arabic, answer in Arabic.
- If the user writes in French, answer in French.
- If the user writes in German, answer in German.
- Never answer Russian transliteration with Latin transliteration.
- Never say "I only speak English".
- Never refuse because of language.
- Never mention translation.

Business context:
- Company ID: {company_id}
- Site name: {site_name}
- Business type: {business_type}
- Offer: {offer}
- Price starts from: {price}
- Payment link: {payment_link}

Your job:
- Act like a confident sales assistant.
- Be friendly, short, natural, and sales-focused.
- Help visitors understand the offer.
- Guide the visitor toward one clear action:
  1. ask price
  2. book appointment
  3. pay now
  4. leave email or phone
- Ask only one question at a time.
- Do not write long explanations.
- Do not say you are an AI model.
- Do not sound robotic.

Sales rules:
- If user asks about price, say that price starts from {price}.
- If user wants to book, ask for email or phone.
- If user sends email or phone, confirm that the request was received and say that the team will contact them soon.
- If user wants to pay, send this payment link: {payment_link}.
- If user asks about Instagram, Facebook, Messenger, WhatsApp, or social media, answer that AI FLOW helps connect website, Facebook, Instagram, and WhatsApp messages into one AI sales assistant.
- If user says they want to book tomorrow or at a certain time, ask for phone/email if they did not provide it.
- If user already provided phone/email, confirm that the request was received and that the team will contact them soon.
- If user is unsure, explain the value briefly and ask what they want to do next.
- If user says hello, greet them and ask how you can help with price, booking, or payment.
- If user asks what this is, explain that AI FLOW helps businesses convert website and social messages into leads, bookings, and payments.

Answer format:
- 1 to 3 short sentences.
- No markdown.
- No bullets unless really needed.
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
        temperature=0.25,
        max_tokens=220,
    )

    return completion.choices[0].message.content


# =========================================================
# META / FACEBOOK MESSENGER
# =========================================================

def send_meta_message(recipient_id, message_text):
    page_access_token = os.getenv("META_PAGE_ACCESS_TOKEN")

    if not page_access_token:
        print("META_PAGE_ACCESS_TOKEN is missing")
        return False

    try:
        url = "https://graph.facebook.com/v19.0/me/messages"

        payload = json.dumps(
            {
                "recipient": {
                    "id": recipient_id,
                },
                "message": {
                    "text": message_text,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url + "?access_token=" + urllib.parse.quote(page_access_token),
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            print("META SEND MESSAGE RESPONSE:", body)
            return True

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("META SEND MESSAGE HTTP ERROR:", e.code, error_body)
        return False

    except Exception as e:
        print("META SEND MESSAGE ERROR:", str(e))
        return False


@app.get("/meta/webhook")
async def verify_meta_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.getenv("META_VERIFY_TOKEN", "ai_flow_verify_2026")

    if mode == "subscribe" and token == verify_token:
        print("META WEBHOOK VERIFIED")
        return PlainTextResponse(challenge or "")

    print("META WEBHOOK VERIFY FAILED")
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/meta/webhook")
async def receive_meta_webhook(request: Request):
    try:
        data = await request.json()
        print("META WEBHOOK EVENT:", json.dumps(data, ensure_ascii=False))

        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender = messaging_event.get("sender", {})
                sender_id = sender.get("id", "")

                message_obj = messaging_event.get("message", {})
                user_message = message_obj.get("text", "")

                if sender_id and user_message:
                    company_id = "ai_sales_assistant_main"
                    site_name = "AI FLOW"
                    business_type = "AI sales automation service"
                    offer = (
                        "AI assistant for Facebook, Instagram, WhatsApp, "
                        "websites, Google Sheets, and Google Calendar"
                    )
                    price = "$99/month + success fee"
                    payment_link = "https://buy.stripe.com/test_your_payment_link"
                    source = "meta messenger"

                    email = extract_email(user_message)
                    phone = extract_phone(user_message)
                    language = detect_language_hint(user_message)

                    if email or phone:
                        save_lead(
                            message=user_message,
                            email=email,
                            phone=phone,
                            source=source,
                            language=language,
                            site_name=site_name,
                            company_id=company_id,
                        )

                    try:
                        reply_text = build_ai_reply(
                            message=user_message,
                            company_id=company_id,
                            site_name=site_name,
                            business_type=business_type,
                            offer=offer,
                            price=price,
                            payment_link=payment_link,
                        )

                    except Exception as ai_error:
                        print("META AI REPLY ERROR:", str(ai_error))
                        reply_text = (
                            "Hello! Welcome to AI FLOW. "
                            "We help businesses automate replies, collect leads, and book appointments. "
                            "Would you like pricing or a demo?"
                        )

                    send_meta_message(sender_id, reply_text)

    except Exception as e:
        print("META WEBHOOK ERROR:", str(e))

    return JSONResponse({"ok": True})


# =========================================================
# GOOGLE OAUTH
# =========================================================

@app.get("/connect/google")
def connect_google(companyId: str = "default_company"):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    if not client_id or not redirect_uri:
        return HTMLResponse(
            """
            <h1>Google OAuth is not configured</h1>
            <p>Missing GOOGLE_CLIENT_ID or GOOGLE_REDIRECT_URI in Render Environment.</p>
            """
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid",
    ]

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": companyId,
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    return RedirectResponse(auth_url)


@app.get("/google/callback")
def google_callback(code: str = "", state: str = "default_company"):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    if not code:
        return HTMLResponse(
            """
            <h1>Google connection failed</h1>
            <p>No authorization code received.</p>
            """
        )

    if not client_id or not client_secret or not redirect_uri:
        return HTMLResponse(
            """
            <h1>Google OAuth is not configured</h1>
            <p>Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or GOOGLE_REDIRECT_URI.</p>
            """
        )

    try:
        token_payload = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")

        token_req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        with urllib.request.urlopen(token_req, timeout=25) as token_response:
            token_data = json.loads(token_response.read().decode("utf-8"))

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")

        user_email = ""
        user_name = ""

        if access_token:
            user_req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={
                    "Authorization": "Bearer " + access_token,
                },
                method="GET",
            )

            with urllib.request.urlopen(user_req, timeout=25) as user_response:
                user_data = json.loads(user_response.read().decode("utf-8"))

            user_email = user_data.get("email", "")
            user_name = user_data.get("name", "")

        company_id = state or "default_company"

        old_company = get_company(company_id)
        old_refresh_token = ""
        old_sheet_id = ""

        if old_company:
            old_refresh_token = old_company.get("refresh_token", "")
            old_sheet_id = old_company.get("sheet_id", "")

        if not refresh_token:
            refresh_token = old_refresh_token

        company = {
            "company_id": company_id,
            "google_connected": True,
            "google_email": user_email,
            "google_name": user_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "connected_at": datetime.utcnow().isoformat() + "Z",
            "calendar_id": "primary",
            "sheet_id": old_sheet_id,
            "token_refreshed_at": "",
        }

        upsert_company(company)

        return HTMLResponse(
            f"""
            <h1>✅ Google connected successfully</h1>
            <p><strong>Company ID:</strong> {company_id}</p>
            <p><strong>Google account:</strong> {user_email}</p>
            <p>You can close this page.</p>
            """
        )

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("GOOGLE OAUTH HTTP ERROR:", e.code, error_body)

        return HTMLResponse(
            f"""
            <h1>Google OAuth error</h1>
            <pre>{error_body}</pre>
            """
        )

    except Exception as e:
        print("GOOGLE OAUTH ERROR:", str(e))

        return HTMLResponse(
            f"""
            <h1>Google OAuth error</h1>
            <pre>{str(e)}</pre>
            """
        )


@app.get("/company/status")
def company_status(companyId: str = "default_company"):
    company = get_company(companyId)

    if not company:
        return JSONResponse(
            {
                "companyId": companyId,
                "google_connected": False,
            }
        )

    return JSONResponse(
        {
            "companyId": companyId,
            "google_connected": company.get("google_connected", False),
            "google_email": company.get("google_email", ""),
            "google_name": company.get("google_name", ""),
            "calendar_id": company.get("calendar_id", "primary"),
            "sheet_id": company.get("sheet_id", ""),
            "connected_at": company.get("connected_at", ""),
        }
    )


@app.get("/companies")
def get_companies():
    companies = get_all_companies_safe()

    return JSONResponse(
        {
            "companies": companies,
        }
    )


# =========================================================
# WEBSITE CHAT
# =========================================================

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()

    message = data.get("message", "")
    company_id = data.get("companyId", "default_company")
    site_name = data.get("siteName", "this business")
    business_type = data.get("businessType", "online business")
    offer = data.get("offer", "AI Sales Assistant")
    price = data.get("price", "$99/month")
    payment_link = data.get(
        "paymentLink",
        "https://buy.stripe.com/test_your_payment_link",
    )
    source = data.get("source", "website widget")

    email = extract_email(message)
    phone = extract_phone(message)
    language = detect_language_hint(message)

    lead_saved = False
    saved_to_sheets = False
    saved_to_calendar = False

    if email or phone:
        result = save_lead(
            message=message,
            email=email,
            phone=phone,
            source=source,
            language=language,
            site_name=site_name,
            company_id=company_id,
        )

        lead_saved = True
        saved_to_sheets = result["saved_to_sheets"]
        saved_to_calendar = result["saved_to_calendar"]

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
                "lead_saved": lead_saved,
                "saved_to_sheets": saved_to_sheets,
                "saved_to_calendar": saved_to_calendar,
                "companyId": company_id,
            }
        )

    except Exception as e:
        print("GROQ SDK ERROR:", str(e))

        return JSONResponse(
            {
                "reply": "AI connection error. Please try again.",
                "lead_saved": lead_saved,
                "saved_to_sheets": saved_to_sheets,
                "saved_to_calendar": saved_to_calendar,
                "companyId": company_id,
            }
        )
