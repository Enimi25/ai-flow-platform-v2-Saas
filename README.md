# AI FLOW (MVP)

FastAPI backend (`app.py`) serving static HTML pages for the AI FLOW SaaS MVP.

## Render Environment Variables

Required (social integrations):
- `META_APP_ID`
- `META_APP_SECRET`
- `META_REDIRECT_URI`
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_REDIRECT_URI`

Optional (AI generation):
- `GROQ_API_KEY`

Notes:
- Redirect URIs must be **exactly** the same as registered in the provider dashboards.
- Redirect URIs must be HTTPS and must not include `#` fragments (TikTok web redirect URI must not include query params).

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

## TikTok OAuth Setup (MVP)

AI FLOW supports connecting a TikTok account (basic connect + account display).

### Required Environment Variables (Render)

- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_REDIRECT_URI`

`TIKTOK_REDIRECT_URI` must point to the deployed callback endpoint:

`https://<your-render-domain>/api/tiktok/callback`

Notes:
- Tokens are stored server-side in PostgreSQL (`v2_social_tokens`), not exposed to the browser.
- For publishing to TikTok via API you typically need Content Posting API access and scopes like `video.upload` / `video.publish` (requires TikTok review/audit). The MVP connect flow requests only `user.info.basic`.

## Social Content Automation (Daily Drafts)

The dashboard auto-generates daily social content drafts for:
- Facebook
- Instagram
- TikTok

How it works (MVP):
- Drafts are stored in PostgreSQL (`v2_social_content_drafts`).
- When the dashboard loads, it calls `/social-content-data?companyId=...` which ensures at least one draft exists for the current UTC day (the MVP generates one per platform).
- Drafts start as `draft`, can be `approved`, and publishing is blocked unless the necessary platform permissions/scopes are configured.

## Stripe Payments (Checkout)

Required environment variables:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_STARTER`
- `STRIPE_PRICE_PRO`
- `APP_PUBLIC_URL` (example: `https://your-app.onrender.com`)

How to set up:
1. In Stripe, create 2 recurring Prices (monthly):
   - Starter ($39/mo) -> `STRIPE_PRICE_STARTER`
   - Pro ($99/mo) -> `STRIPE_PRICE_PRO`
2. Add a webhook endpoint in Stripe pointing to:
   `https://<your-render-domain>/api/stripe/webhook`
   Subscribe at least to: `checkout.session.completed`.
3. In Render, set `APP_PUBLIC_URL` to your deployed app URL (no trailing slash).

How to test:
- Use Stripe test mode keys.
- Start checkout from `/billing` (Pay with Stripe).
- Confirm the payment, then check company payment status via Billing "Refresh Payment Status".

Notes:
- The app does not trust the success URL to grant access. It only marks accounts as paid via Stripe webhooks.

## Accounts, Roles, and RBAC (MVP)

AI FLOW now uses server-side signed cookie sessions and role-based access control.

### Required Environment Variables (Render)

- `SESSION_SECRET` (random long string, required for stable signed sessions)
- `PLATFORM_ADMIN_EMAIL` (bootstrap platform admin login)
- `PLATFORM_ADMIN_PASSWORD` (bootstrap platform admin password)

Notes:
- On startup, if `PLATFORM_ADMIN_EMAIL` + `PLATFORM_ADMIN_PASSWORD` are set and the user does not exist, the app creates a `platform_admin` user.
- Passwords are stored as PBKDF2 hashes. Legacy SHA256 passwords are upgraded to PBKDF2 on first successful login.

### Roles

- `platform_admin`: full access (admin area, all companies/users)
- `company_admin`: manages only their company (billing, settings, social connections, team)
- `employee`: company-scoped access to tools (no billing by default)
- `client`: reserved for client-facing features (not used heavily in the MVP yet)

### Team Invites

- Company admins can open `/team` to generate an invite link for employees/clients.
- Invited users accept the link at `/accept-invite?token=...`, set a password, then login via `/login`.
