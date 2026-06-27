import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const app = fs.readFileSync(path.join("frontend", "src", "main.tsx"), "utf8");
const sidebar = fs.readFileSync(path.join("frontend", "src", "components", "Sidebar.jsx"), "utf8");
const sessionDeck = fs.readFileSync(path.join("frontend", "src", "sessions", "SessionDeck.jsx"), "utf8");
const sessionForm = fs.readFileSync(path.join("frontend", "src", "sessions", "SessionForm.jsx"), "utf8");
const sessionNoteEditor = fs.readFileSync(path.join("frontend", "src", "sessions", "SessionNoteEditor.jsx"), "utf8");
const sceneForm = fs.readFileSync(path.join("frontend", "src", "scenes", "SceneForm.jsx"), "utf8");
const kanban = fs.readFileSync(path.join("frontend", "src", "tickets", "KanbanBoard.jsx"), "utf8");
const css = fs.readFileSync(path.join("frontend", "src", "styles.css"), "utf8");

for (const action of ["Session Deck", "Scene Deck", "Search Vault", "Tickets", "Foundry Link"]) {
  assert.match(sidebar, new RegExp(action));
}

assert.match(sidebar, /CalendarDays/);
assert.doesNotMatch(sidebar, /session-note/);
assert.match(app, /useState\("session-deck"\)/);
assert.match(app, /SessionDeck/);
assert.match(app, /activeTool === "session-deck"/);
assert.match(sessionDeck, /New Session/);
assert.match(sessionDeck, /Browse sessions by status/);
assert.match(sessionForm, /Save Session/);
assert.match(sessionForm, /Planned/);
assert.match(sessionForm, /Active/);
assert.match(sessionForm, /Played/);
assert.match(app, /latest_session\.session/);
assert.match(app, /data\.freshness/);
assert.match(sessionForm, /SessionNoteEditor/);
assert.match(sessionNoteEditor, /Generate Note/);
assert.match(sessionNoteEditor, /Save Note/);
assert.match(sessionNoteEditor, /\/api\/sessions\/\$\{sessionId\}\/note/);
assert.match(sessionNoteEditor, /\/api\/sessions\/\$\{sessionId\}\/note\/generate/);
assert.match(sessionNoteEditor, /Generated markdown/);
assert.match(sceneForm, /Canonical target path/);
assert.match(sceneForm, /Preview Save/);
assert.match(sceneForm, /Confirm Save/);
assert.match(sceneForm, /Create Draft/);
assert.match(kanban, /\/api\/tickets/);
assert.match(app, /Open Markdown/);
assert.match(app, /Markdown Editor/);
assert.match(app, /Read-only context/);
assert.doesNotMatch(app, /Save Markdown/);
assert.match(css, /\.kanban-board/);
assert.match(css, /\.workbench/);
assert.match(css, /\.notice/);
assert.match(css, /\.markdownModal/);
assert.match(css, /\.saveFlow/);
assert.match(css, /\.session-deck-shell/);
assert.match(css, /\.session-card-meta/);
assert.match(css, /\.session-note-editor/);
assert.match(css, /\.session-note-output/);
assert.doesNotMatch(css, /letter-spacing:\s*-/);

console.log("frontend static cockpit checks passed");
