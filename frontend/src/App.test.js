import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const app = fs.readFileSync(path.join("frontend", "src", "main.jsx"), "utf8");
const css = fs.readFileSync(path.join("frontend", "src", "styles.css"), "utf8");

for (const label of ["Now", "Next", "Scene Deck", "Capture", "Follow-up"]) {
  assert.match(app, new RegExp(label));
}

for (const action of ["Quick Session Note", "Quick Scene", "Search Vault", "Tickets", "Foundry Link"]) {
  assert.match(app, new RegExp(action));
}

assert.match(app, /latest_session\.session/);
assert.match(app, /data\.freshness/);
assert.match(app, /Generate Draft/);
assert.match(app, /Editable Markdown Draft/);
assert.match(app, /Create Scene Draft/);
assert.match(app, /Loaded \$\{json\.length\} operational tickets/);
assert.match(app, /Open Markdown/);
assert.match(app, /Markdown Editor/);
assert.match(app, /Save Markdown/);
assert.match(css, /\.board/);
assert.match(css, /\.workbench/);
assert.match(css, /\.notice/);
assert.match(css, /\.markdownModal/);
assert.doesNotMatch(css, /letter-spacing:\s*-/);

console.log("frontend static cockpit checks passed");
