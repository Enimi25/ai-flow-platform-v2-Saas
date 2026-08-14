# AI FLOW social content production audit

Date: 2026-08-14  
Scope: Facebook Pages, Instagram Business, TikTok Direct Post, WhatsApp, daily content automation, tenant isolation.

## Outcome

The application now contains production-oriented publishing flows and launch assets, but no social post may be reported as published until the provider returns a completed status and a real post identifier or permalink.

## Implemented

- Three daily content units per company: educational static, proof/case study, and short-form Reel.
- Platform-native AI variants for Facebook, Instagram, and TikTok.
- Organic growth prompt with hook, retention, save/share value, restrained hashtags, natural CTA, and repetition avoidance.
- Production launch static: 1080×1350 PNG.
- Production launch Reel: 1080×1920, H.264, 30 fps, AAC, 12.5 seconds.
- Authenticated one-click static publishing to Facebook Page and Instagram Business.
- Instagram image, carousel, and Reel containers with processing-status polling.
- Facebook hosted-Reel upload session, finish/publish request, and processing-status endpoint.
- TikTok creator-info, photo Direct Post, video Direct Post, explicit consent, privacy validation, and status polling.
- Daily automation settings per company: enabled flag, timezone, three posting times, and publishing mode.
- Secret-protected cron endpoint that builds the daily approval queue.
- Publish-log database foundation.
- Tenant authorization for Meta, TikTok, WhatsApp connection and social-content operations.

## Verified locally

- Python compilation: pass.
- Patch whitespace validation: pass.
- Static asset response: `200 image/png`.
- Reel response: `200 video/mp4`.
- Social account endpoint without an authenticated session: `401`.
- Cron endpoint without `SOCIAL_CRON_SECRET`: `503`.
- Repository secret-pattern scan found no committed provider credentials.

## External actions still required

1. Deploy the latest GitHub `main` commit on Render. The current Render service was observed remaining on an older manually deployed commit.
2. In the Meta app, obtain the required access and reconnect Meta with:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
3. In the TikTok app:
   - add Content Posting API;
   - obtain `video.publish` approval;
   - verify the AI FLOW media URL/domain;
   - complete the TikTok audit to permit public visibility. Unaudited apps are restricted to private posts.
4. Configure a strong `SOCIAL_CRON_SECRET` on Render and the external scheduler/worker that calls the cron endpoint.
5. Rotate all credentials visible in earlier screenshots, including database, Groq, Meta, Stripe test, TikTok, application/session secrets, and the platform-admin password.

## WhatsApp clarification

- WhatsApp Business Platform is suitable for AI customer conversations, qualification, CRM capture, booking, payment links, and human handoff.
- WhatsApp Channels are a public broadcast surface, but the official Cloud API does not currently expose a supported Channel-posting endpoint. Channel content must stay approval/manual-publish until Meta provides an official API.

## Go-live rule

A provider request being accepted is not a completed publication. AI FLOW must poll or receive webhooks until the provider reports completion, then store the external post ID and permalink. Failures must remain visible and retryable; they must never be displayed as published.
