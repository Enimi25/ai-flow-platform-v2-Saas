# AI FLOW (MVP)

FastAPI backend (`app.py`) serving static HTML pages for the AI FLOW SaaS MVP.

## Meta (Facebook / Instagram) OAuth Setup

AI FLOW supports connecting Facebook Pages and Instagram Business accounts via Meta OAuth.

### Required Environment Variables (Render)

- `META_APP_ID`
- `META_APP_SECRET`
- `META_REDIRECT_URI`

`META_REDIRECT_URI` must point to the deployed callback endpoint:

`https://<your-render-domain>/api/meta/callback`

### How It Works (MVP)

1. In the app UI, go to **Social Accounts** and click **Connect Facebook** or **Connect Instagram**.
2. You will be redirected to Meta to authorize.
3. After callback, AI FLOW stores connected Facebook Pages and Instagram accounts in PostgreSQL.

Notes:
- Access tokens are stored server-side in PostgreSQL (not exposed to the browser).
- Disconnect removes Meta tokens and connected Meta accounts for that company.

