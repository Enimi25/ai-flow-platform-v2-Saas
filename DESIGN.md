---
name: AI FLOW Workspace
description: A calm, task-first operating surface for managing customer messaging channels and appointments.
colors:
  charcoal: "#18201c"
  charcoal-hover: "#243029"
  workspace: "#f4f6f3"
  surface: "#ffffff"
  surface-soft: "#edf2ee"
  text-muted: "#647069"
  border: "#d6dcd8"
  emerald: "#1f7356"
  emerald-bright: "#5bc49a"
  emerald-soft: "#edf5f0"
  warning-surface: "#fff0e4"
  warning-text: "#7c3f16"
typography:
  display:
    fontFamily: "var(--font-geist), sans-serif"
    fontSize: "clamp(2.8rem, 5vw, 4.7rem)"
    fontWeight: 700
    lineHeight: 0.95
    letterSpacing: "-0.04em"
  title:
    fontFamily: "var(--font-geist), sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
  body:
    fontFamily: "var(--font-geist), sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "var(--font-geist), sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.2
rounded:
  sm: "9px"
  control: "12px"
  panel: "16px"
spacing:
  xs: "8px"
  sm: "10px"
  md: "16px"
  lg: "22px"
  xl: "28px"
components:
  button-primary:
    backgroundColor: "{colors.emerald}"
    textColor: "#f5fff9"
    rounded: "{rounded.control}"
    padding: "0 15px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.control}"
    padding: "0 15px"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.charcoal}"
    rounded: "{rounded.panel}"
    padding: "22px"
  status-chip:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    padding: "7px 9px"
---

# Design System: AI FLOW Workspace

## Overview

**Creative North Star: "The Calm Operations Desk"**

AI FLOW feels like a focused operations desk: a stable dark frame holds a quiet, cool workspace where account state, appointments, and required actions are easy to scan. The system is practical and restrained rather than decorative, using hierarchy, spacing, and explicit language to make operational truth visible.

The interface is dense enough for daily work without feeling cramped. Large, tightly set page titles orient the user; white panels organize task content; the emerald accent appears only where it signals a useful action, keyboard focus, or healthy state. Unconfigured and preview states are named honestly instead of being disguised as live data.

**Key Characteristics:**

- Dark charcoal navigation frame with a cool neutral workspace.
- Restrained emerald action and status language.
- Rounded, compact controls and calm white panels.
- Explicit preview, disabled, protected, and unconfigured states.
- Task-first responsive composition with persistent mobile navigation.

## Colors

The palette pairs ink-like charcoal with green-tinted neutrals and one restrained emerald voice.

### Primary

- **Operational Emerald:** The sole action accent for primary controls, links that initiate connection, positive state, compact icons, and keyboard focus.
- **Focus Mint:** A brighter emerald reserved for focus outlines, selection, and the account avatar against the dark navigation frame.

### Neutral

- **Navigation Charcoal:** The sidebar, mobile navigation, dark action buttons, and high-contrast date rail.
- **Cool Workspace:** The continuous application canvas behind panels.
- **Clear Surface:** The white panel and secondary-control surface.
- **Soft Utility:** Low-emphasis chips, icon wells, privacy notes, and selected content blocks.
- **Muted Copy:** Supporting descriptions, timestamps, and secondary labels.
- **Quiet Divider:** Separates rows, headers, and structural regions without adding visual weight.

### Named Rules

**The One Signal Rule.** Emerald is the only interactive accent; reserve it for action, focus, availability, or confirmed health.

**The Honest State Rule.** Warning amber communicates incomplete setup, while neutral copy states “Not connected,” “Preview data,” or disabled status explicitly; color never carries status alone.

## Typography

**Display Font:** Geist (with sans-serif fallback)  
**Body Font:** Geist (with sans-serif fallback)

**Character:** A single modern grotesk keeps the application direct and consistent. Tight, oversized display type gives each workspace a clear entry point, while compact labels and tabular numerals support fast scanning.

### Hierarchy

- **Display** (700, responsive 2.8–4.7rem, 0.95 line-height): Page titles only, with tight negative tracking.
- **Title** (700, 20px, 1.2 line-height): Agenda dates and primary panel headings.
- **Body** (400, 13px, 1.5 line-height): Operational descriptions, requirements, and supporting content.
- **Label** (600, 11px, 1.2 line-height): Status chips, workspace metadata, and compact utility copy.
- **Numeric** (tabular numerals): Times, dates, durations, availability windows, and summary counts.

### Named Rules

**The Scan First Rule.** Lead with short headings and state labels; explanatory copy follows in quieter type and remains concise.

## Layout

The desktop shell uses a fixed 248px navigation rail and a fluid workspace. Content is centered within a 1260px maximum and uses 42px horizontal padding, with a 72px top bar anchoring workspace identity and unavailable notifications.

Task surfaces use asymmetric two-column grids: a broader working region and a narrower contextual panel, separated by a 22px gap. Calendar content leads with a horizontally scrollable dark date rail and a vertical agenda stream. Social-account content leads with selectable channels and a sticky detail panel. At roughly 1040px the navigation collapses to a 76px icon rail; task grids stack between 980px and 1080px. At 680px and below, the shell becomes a single column with a fixed 66px bottom navigation, 20px content gutters, and simplified actions.

Spacing follows a compact 8–28px working rhythm. Panel padding is generally 22–26px; list rows use 16–24px; major section separation is 28–48px. Responsive changes preserve task order: selection or agenda first, context and configuration second.

## Elevation & Depth

The system is flat by default and uses tonal layering for most hierarchy. White work panels receive one diffuse, low-contrast ambient shadow; navigation, rails, banners, selected rows, and state blocks rely on background contrast instead. Sticky elements are structural, not visually lifted.

### Shadow Vocabulary

- **Ambient Panel** (`0 18px 48px rgba(24,32,28,.07)`): Agenda, channel list, detail, connection, and availability panels only.
- **Ambient Panel Soft** (`0 18px 48px rgba(24,32,28,.06)`): Supporting side panels where slightly less emphasis is needed.

### Named Rules

**The Flat Frame Rule.** Never shadow the sidebar, top bar, date rail, banners, or bottom navigation; their depth comes from tonal contrast and borders.

## Shapes

The form language is softly geometric. Major panels and rails use 16px corners; controls, icon wells, and navigation items use 11–13px corners; compact chips use 9px corners. Circular geometry is limited to tiny connection-state indicators. Borders are quiet one-pixel dividers in cool gray-green, and full-bleed mobile rails intentionally drop their outer radius.

## Components

### Buttons

- **Shape:** Compact rounded rectangle (11–12px radius), generally 40–48px tall.
- **Primary:** Operational Emerald with near-white text; used for connection and sign-in actions.
- **Hover / Focus:** Darken primary actions on hover. All keyboard-focusable elements receive a 3px Focus Mint outline with a 3px offset; focus inside the dark date rail moves the outline inward.
- **Secondary:** White with a quiet divider border and charcoal text.
- **Disabled:** Retains its component shape and label at 50% opacity with a not-allowed cursor; explanatory title text states the dependency.

### Chips

- **Style:** Compact 9px-radius pills or badges on a low-contrast neutral surface.
- **State:** Use literal text such as “Preview data” and “Not connected.” Selected dates invert to a light surface on the charcoal rail.

### Cards / Containers

- **Corner Style:** Gently rounded panels (16px radius).
- **Background:** Clear Surface over the Cool Workspace; selected rows and event blocks use soft tinted neutrals.
- **Shadow Strategy:** Ambient Panel shadow only on primary work containers.
- **Border:** Internal dividers, rather than boxed borders, organize lists and timelines.
- **Internal Padding:** 22–26px for panel frames; 14–18px for inset state blocks.

### Navigation

- The desktop sidebar is charcoal with muted labels, 46px rows, 12px corners, and 21px icons. Hover uses a slightly lighter charcoal; the active item inverts to a light neutral surface with charcoal text.
- At intermediate widths, the sidebar becomes icon-only. On mobile it becomes a fixed bottom bar; Overview and Settings are hidden so core work destinations remain reachable without crowding.

### Date Rail and Agenda Stream

- The date rail is a dark, horizontal control with nine visible date cells on wide screens and horizontal scrolling on narrower screens. The selected date is a high-contrast light cell with `aria-pressed` state.
- The agenda is a vertical time stream. Each event uses a softly tinted block and preserves explicit source, duration, and example-data labeling. Open time is rendered as an available slot, not a fabricated appointment.

### Channel Board

- Channel rows combine a 44px emerald icon well, a plain-language description, and an explicit connection-state badge. Selection uses a soft emerald tint.
- The detail panel explains prerequisites, requested permissions, server-side token privacy, and the next connection action in that order.

## Do's and Don'ts

### Do:

- **Do** keep the charcoal navigation frame stable while task content changes inside the cool neutral workspace.
- **Do** use emerald sparingly for primary action, focus, confirmed health, and availability.
- **Do** name preview, disconnected, protected, disabled, and incomplete-setup states in visible text.
- **Do** preserve agenda-first and selection-first order when columns stack on smaller screens.
- **Do** use 12–16px radii for controls and panels, with compact 9px badges where appropriate.

### Don't:

- **Don't** use multiple competing accent colors or decorative gradients.
- **Don't** present preview appointments or unconfigured providers as live customer data.
- **Don't** hide required recovery actions behind color, icons, tooltips, or provider jargon.
- **Don't** add shadows to every surface; depth is mostly tonal and structural.
- **Don't** replace visible keyboard focus with subtle border changes.
