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
            )

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
            )

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
            )

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
            )

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
