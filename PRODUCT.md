# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are small-business owners and team administrators who need to connect and manage the customer messaging channels used by their business.

## Product Purpose

AI FLOW provides AI sales agents that answer customer messages, capture qualified leads, and create next actions such as appointments across website and social channels. Success means the business can see which channels are connected, understand what requires attention, and manage each connection without losing access to the dashboard.

## Positioning

AI FLOW connects the customer conversation to a business action in one company workspace instead of treating each messaging channel as a separate inbox.

## Operating Context

Owners connect Facebook Pages, Instagram professional accounts, and WhatsApp Business accounts. They need to understand Meta prerequisites, connection health, permissions, and which business account is currently active.

## Capabilities and Constraints

- Confirmed channels: website, Facebook Messenger, Instagram, and WhatsApp Business.
- Social production connections depend on Meta verification, account permissions, and credentials that are not present in this repository.
- The current legacy deployment stores email, role, and company ID in local storage but does not expose a durable server session to protected routes.
- The new platform uses Next.js and must treat a secure HttpOnly cookie as the session source of truth.
- Actual OAuth token exchange, token refresh, and encrypted token persistence remain open until the existing backend repository and Meta application credentials are available.

## Brand Commitments

- Product name: AI FLOW.
- Voice: direct, practical, calm, and understandable to non-technical business owners.
- Existing visual direction: cool neutral surfaces with one restrained emerald accent and rounded 12-16px controls.

## Evidence on Hand

- Existing marketing content and generated product hero in this repository.
- Live legacy login and protected-route behavior inspected on the deployed Render application.
- No approved customer logos, testimonials, performance benchmarks, or real connected social account data are available and none should be fabricated.

## Product Principles

- Show connection state before configuration detail.
- Explain the recovery action whenever a channel needs attention.
- Keep authorization server-controlled and durable across navigation and reloads.
- Separate safe UI demonstration data from real customer account data.
- Never expose provider tokens or customer messages to the browser unnecessarily.

## Accessibility & Inclusion

The interface must support keyboard navigation, visible focus, meaningful status text in addition to color, and responsive operation on mobile web.
