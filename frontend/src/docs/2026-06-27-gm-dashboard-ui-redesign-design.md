# GM Dashboard UI/UX Redesign

**Date:** 2026-06-27  
**Scope:** App shell, sidebar navigation, CSS token system, component reference

---

## Problem Statement

The Kaihou GM Dashboard is functionally complete but lacks visual cohesion and a clear app identity:

1. **No design tokens** — every color is a hardcoded hex value, making rethemes impossible
2. **QuickScene is a styling island** — uses a completely different color palette (`#2a2a2a` grays) vs the rest of the app (green-tinted darks)
3. **Poor app identity** — the topbar shows the active session name as a title, making it feel like a document viewer instead of a command center
4. **Conflicting card systems** — `.card` and `.ticket-card` serve the same purpose but have different DOM structures and styles
5. **Unused cockpit strip** — always-visible at the bottom, user doesn't know what it is or how to populate it
6. **No component library** — each tool panel is built from scratch with its own patterns

---

## Design Goals

1. Establish a **clear app shell** with sidebar navigation and persistent app identity ("Kaihou GM Dashboard")
2. Create a **CSS token system** to formalize the existing color palette and make it maintainable
3. Consolidate **component patterns** into reusable, documented classes
4. Remove **visual inconsistencies** (QuickScene palette, cockpit strip) to make the interface feel like one cohesive tool

---

## Solution

### 1. App Shell & Sidebar Layout

**New DOM structure:**
```
<div class="app-shell">
  <aside class="sidebar">
    [App identity + tool nav + session context]
  </aside>
  <main class="main-content">
    [Active tool panel]
  </main>
</div>
```

**Sidebar (fixed 220px width, left side):**
- **Top:** Kaihou wordmark + "GM Dashboard" subtitle in muted text
- **Middle (flex: 1):** Tool navigation — 5 items as vertical nav links with icon + label
  - Active item: left border accent + background highlight using `var(--color-accent-dim)`
- **Bottom:** Session context block — "Active Session" label + current session name in secondary text
- **Responsive:** Below 768px, collapses to 48px icon-only rail

**Main content area (flex: 1):**
- Takes all remaining width
- Each tool panel renders here, full-height
- Removes the old topbar and cockpit strip entirely

---

### 2. CSS Token System

All design values are defined as CSS custom properties in `tokens.css`, imported at the top of `styles.css`.

**Color tokens** (formalized existing palette):
```css
--color-bg:           #161817;   /* page background */
--color-surface:      #1b1f1d;   /* panels, sidebar */
--color-card:         #242a27;   /* cards, inputs */
--color-elevated:     #2d3530;   /* hover, active states */
--color-border:       #37403b;   /* borders */
--color-border-strong: #4b5d53;  /* strong borders */
--color-accent:       #5a8a6a;   /* green accent */
--color-accent-dim:   #42564c;   /* dimmed accent */
--color-text:         #e7e8e3;   /* primary text */
--color-text-secondary: #c8cec7; /* secondary text */
--color-text-muted:   #8aa898;   /* muted text */
--color-text-label:   #aeb9b1;   /* label text */
```

**Spacing scale:**
```css
--space-1: 4px;  --space-2: 8px;  --space-3: 12px;
--space-4: 16px; --space-5: 20px; --space-6: 24px;
```

**Typography:**
```css
--font-ui:   'Inter', sans-serif;
--font-mono: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
--text-xs: 11px; --text-sm: 13px; --text-base: 14px;
--text-lg: 16px; --text-xl: 18px;
```

**Shape:**
```css
--radius-sm: 4px; --radius-md: 6px; --radius-lg: 10px;
--shadow-card: 0 1px 3px rgba(0,0,0,0.4);
```

---

### 3. Normalized Component Classes

All tool panels use a consistent naming system (BEM-inspired where appropriate):

| Class | Purpose |
|-------|---------|
| `.tool-panel` | Full-width tool container |
| `.panel-header` | Title row with tool name + action buttons |
| `.panel-body` | Scrollable content area |
| `.card` | Surface card for content display |
| `.btn` | Ghost button (secondary actions) |
| `.btn-primary` | Accent-colored button (primary CTA) |
| `.btn-danger` | Red button (delete actions) |
| `.badge--ok` | Status pill — success state |
| `.badge--warn` | Status pill — warning state |
| `.badge--bad` | Status pill — error state |
| `.modal-backdrop` | Full-screen overlay |
| `.modal` | Dialog box container |
| `.modal-header` | Modal title section |
| `.modal-body` | Modal content |
| `.modal-footer` | Modal action buttons |

**Migration notes:**
- QuickScene's inline styles replaced with token-based classes
- `.badge.ok`, `.badge.warn`, `.badge.bad` renamed to BEM modifier style (`.badge--ok`, etc.)
- All hardcoded hex values in `styles.css` replaced with `var(--color-*)` references

---

### 4. Files Changed

**New files:**
- `frontend/src/tokens.css` — all CSS custom properties
- `frontend/src/components/AppShell.jsx` — two-column shell layout
- `frontend/src/components/Sidebar.jsx` — sidebar with nav + session context
- `frontend/src/COMPONENTS.md` — component reference cheat sheet

**Modified files:**
- `frontend/src/main.jsx` — remove topbar/cockpit strip, integrate shell components
- `frontend/src/styles.css` — import tokens, replace hex values, add component classes
- `frontend/src/QuickScene.jsx` — replace inline styles with token-based classes, extract reusable components

**Unchanged:**
- All tool logic (Session Note, Quick Scene, Search, Tickets, Foundry)
- Backend / FastAPI
- Package dependencies

---

### 5. Component Extraction (Step 6)

From `QuickScene.jsx`, extract to `frontend/src/components/`:
- `CollapsibleSection.jsx` — reusable collapsible form section
- `AutocompleteField.jsx` — reusable autocomplete input field

These can be reused in future tool panels.

---

## Verification

After implementation:

1. **Visual check:** Open `http://localhost:5173` after `npm run dev`
   - Sidebar visible on left (220px fixed width)
   - "Kaihou / GM Dashboard" header in sidebar
   - 5 tool nav items in sidebar
   - Active session name at sidebar bottom
   - Cockpit strip gone from page
   - All 5 tools still switchable and functional

2. **Code check:**
   - No hardcoded hex values remain in `styles.css` or `QuickScene.jsx`
   - All colors reference `var(--color-*)` tokens
   - All badges use `.badge--*` modifier syntax
   - All tool panels use `.tool-panel`, `.panel-header`, `.panel-body` consistently

3. **Functional check:**
   - Session Note panel loads and functions correctly
   - Quick Scene form submits and creates drafts
   - Search Vault returns results
   - Tickets Kanban board renders and drag-drop works
   - Foundry Link status endpoint loads
   - No console errors

---

## Future Phases

Not included in this redesign:
- Component showcase/live demo route
- Custom theme switching UI
- Dark/light mode toggle (token system supports it, UI doesn't expose it)
- Detailed tool panel layout improvements (out of scope, tool logic is locked)
