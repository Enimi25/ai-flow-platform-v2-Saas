# AI FLOW Platform

New Next.js foundation for the AI FLOW marketing site and SaaS platform.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Demo requests

The form validates requests but does not store personal data locally. Set `DEMO_WEBHOOK_URL` in `.env.local` to connect a protected server-side destination. Never use a `NEXT_PUBLIC_` variable for this URL.

## Checks

```bash
npm run lint
npm run build
```

## Implemented workspace foundation

- Secure signed HttpOnly sessions, including platform administrators without a company assignment.
- Overview, conversations, leads, calendar, social accounts, and settings routes.
- Honest preview, empty, unavailable, and setup-required states with responsive navigation.
- Server-only bridges for legacy login, AI chat, demo webhooks, and provider authorization starts.

## Production connections still required

- Connect a protected PostgreSQL database.
- Replace the transitional signed session with an opaque database-backed session after the identity database is connected.
- Add company-level authorization to every protected data mutation.
- Migrate Stripe billing with verified webhooks.
- Replace the placeholder production domain in metadata, sitemap, and robots configuration.
- Complete OAuth callback handlers, token refresh, and encrypted token persistence for Meta and Google.

## Legacy login migration

Set `LEGACY_API_BASE_URL` and a random `SESSION_SECRET` of at least 32 characters. Successful legacy credentials are exchanged server-side for an HttpOnly AI FLOW session cookie. Email, role, and company ID in browser local storage are not treated as authentication.

Social OAuth buttons use the provider authorization URLs from `.env.example`. Complete token exchange, refresh, encryption, and account persistence before enabling these values in production.
