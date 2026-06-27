# Component Reference

Canonical classes for building consistent UI in the Kaihou GM Dashboard.

## Shell & Layout

| Class | Purpose | Usage |
|-------|---------|-------|
| `.app-shell` | Root two-column layout (sidebar + main) | Applied to root container; handled by `<AppShell>` component |
| `.sidebar` | Fixed left sidebar | Applied by `<Sidebar>` component |
| `.main-content` | Main scrollable content area | Applied by `<AppShell>` component |
| `.main-workbench` | Max-width wrapper for main content | Wrap all tool panels |

## Tool Panels

| Class | Purpose | Usage |
|-------|---------|-------|
| `.tool-panel` (or `.toolPanel`) | Full tool container surface | Root container for each tool panel |
| `.panel-header` (or `.panelHeader`) | Title row with tool name + actions | Header section inside a tool; use flex with space-between for title left, buttons right |
| `.panel-body` (or `.panelBody`) | Scrollable content area | Not used directly (just padding on `.tool-panel`), but reserved for future sub-layout |

**Example:**
```jsx
<div className="tool-panel">
  <div className="panelHeader">
    <div>
      <h2>Tickets</h2>
      <p>Manage backlog</p>
    </div>
    <button className="btn-primary">New Ticket</button>
  </div>
  {/* content */}
</div>
```

## Cards & Surfaces

| Class | Purpose | Usage |
|-------|---------|-------|
| `.card` | Surface card for content display (search results, cockpit items) | Wrap individual result items |
| `.ticket-card` | Kanban-specific draggable ticket card | Use in Kanban board; has drag affordances |

## Badges

| Class | Purpose | Example |
|-------|---------|---------|
| `.badge--ok` | Status badge — success/healthy state | Sync status: "fresh" |
| `.badge--warn` | Status badge — warning state | Sync status: "stale" |
| `.badge--bad` | Status badge — error/failure state | Sync status: "error" |

**Example:**
```jsx
<span className="badge badge--ok"><ShieldCheck size={14} /> config: fresh</span>
```

## Buttons

| Class | Purpose | Usage |
|-------|---------|-------|
| `.btn` (implicit default) | Ghost/outline button for secondary actions | Cancel, dismiss, alternate actions |
| `.btn-primary` | Accent-colored button for primary CTA | "Save", "Create Ticket", "Generate Draft" |
| `.btn-danger` | Red button for destructive actions | "Delete", "Remove" |

**Example:**
```jsx
<button className="btn">Cancel</button>
<button className="btn-primary">Save</button>
<button className="btn-danger">Delete</button>
```

## Modals

| Class | Purpose | Usage |
|-------|---------|-------|
| `.modal-backdrop` | Full-screen overlay behind modal | Wrapper that fills viewport |
| `.modal` | Dialog box container | Modal content box; set width and max-height |
| `.modal-header` | Modal title section | Header inside modal; use flex space-between |
| `.modal-body` | Modal content | Main content; use `.formGrid` for forms |
| `.modal-footer` | Modal action buttons | Footer inside modal; use flex justify-space-between |
| `.modal-actions` | Button group in header/footer | Flex row for buttons |

**Example:**
```jsx
<div className="modal-backdrop">
  <div className="modal">
    <div className="modal-header">
      <h2>Create Ticket</h2>
      <div className="modal-actions">
        <button onClick={onClose}>Close</button>
      </div>
    </div>
    <div className="modal-body">
      {/* form fields */}
    </div>
    <div className="modal-footer">
      <button className="btn">Cancel</button>
      <button className="btn-primary">Create</button>
    </div>
  </div>
</div>
```

## Forms & Inputs

| Class | Purpose | Usage |
|-------|---------|-------|
| `.field` | Label + input wrapper | Wrap label and input/select/textarea |
| `.formGrid` | 2-column form grid | Wrap multiple `.field` labels |
| `.spanAll` | Span full width in grid | Add to `.field` to span both columns |
| `.field span` | Label text (auto-formatted) | Use inside `.field` as the label |

**Example:**
```jsx
<label className="field">
  <span>Scene Title</span>
  <input value={title} onChange={...} />
</label>

<div className="formGrid">
  <label className="field">
    <span>Type</span>
    <select value={type} onChange={...} />
  </label>
  <label className="field">
    <span>Status</span>
    <select value={status} onChange={...} />
  </label>
  <label className="field spanAll">
    <span>Description</span>
    <textarea value={desc} onChange={...} />
  </label>
</div>
```

## Status & Notifications

| Class | Purpose | Usage |
|-------|---------|-------|
| `.notice` | Status/error message bar | Container at top of workbench |
| `.notice.ok` | Success/status message styling | For informational messages |
| `.notice.bad` | Error message styling | For error states |

**Example:**
```jsx
{status && (
  <section className="notice ok">
    <span>{status}</span>
    <button onClick={dismiss}><X size={14} /></button>
  </section>
)}
```

## Special Layouts

| Class | Purpose | Usage |
|-------|---------|-------|
| `.sessionThreeCol` | 3-column layout (context / form / output) | Session Note panel layout |
| `.draftGrid` | 2-column grid (input / output side-by-side) | Draft editing / preview |
| `.sessionGrid` | 2-column grid for session data | Session context + form |
| `.results` | 2-column grid for search results | Grid of result cards |
| `.kanban-board` | 4-column Kanban board | Ticket board layout |

## Design Tokens

All colors, spacing, and typography are defined as CSS custom properties in `tokens.css` and should be used via `var()`:

- `--color-bg`, `--color-surface`, `--color-card`, `--color-elevated` — surfaces
- `--color-text`, `--color-text-secondary`, `--color-text-muted`, `--color-text-label` — text
- `--color-accent`, `--color-accent-dim` — accent colors
- `--color-border`, `--color-border-strong` — borders
- `--space-1` through `--space-6` — spacing (4px, 8px, 12px, 16px, 20px, 24px)
- `--font-ui`, `--font-mono` — typefaces
- `--text-xs`, `--text-sm`, `--text-base`, `--text-lg`, `--text-xl` — font sizes
- `--radius-sm`, `--radius-md`, `--radius-lg` — border radius
- `--shadow-card` — box shadow for cards

**Example:**
```css
.my-element {
  background: var(--color-surface);
  color: var(--color-text);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
```

## Responsive Breakpoints

- **768px (medium):** Sidebar collapses to icon-only rail
- **640px (small):** Grids stack to 1 column, modals stack to full-width
- **1200px (large):** Session three-column becomes two-column

## When Building a New Tool

1. Wrap in `.tool-panel`
2. Start with `.panelHeader` for title + actions
3. Use `.formGrid` for form layouts
4. Use `.card` for list/result items
5. Use `.modal-backdrop` + `.modal` for overlays
6. Use token variables for colors and spacing (no hardcoded hex)
7. Test at 640px, 768px, and 1200px breakpoints
