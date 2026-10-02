# Canvas form spike (meal-ingredient trial authoring)

Throwaway spike, not the skill's deliverable. Two-column page: ingredient
form left, label-photo preview right. Uploads the photo bytes to
`.agent_tmp/`, posts one event into the authoring conversation asking the
agent to read the panel into a token-scoped
`spike-macros-<token>.json` sidecar, polls and fills per-100g macros,
validates via `validate_ingredient.py --stdin`, gates Submit on zero errors.

Direct `/v1/*` vision was tried and rejected: every call spawns a sidebar
conversation (nested via `parent_conversation_id` or not), and the agent
has no access to the provider key for a direct Gemini call. So photo reads
cost one agent turn each — the prompt is self-contained (panel-literal
macros, basis, no-label branch, never estimate), keeping the turn cheap.

## Source of truth

This directory (`spike/canvas-form/extension.js` + `canvas-extension.json`).
The live page is served from the installed copy — after editing here,
reinstall and reload the page:

```sh
node --check spike/canvas-form/extension.js
KEY="$(tr -d '\n' < ~/.openhands/agent-canvas/api-key.txt)"
curl -sS -m 15 -X POST http://127.0.0.1:18000/api/canvas-extensions/install \
  -H "Content-Type: application/json" -H "X-Session-API-Key: $KEY" \
  -d '{"source": "/projects/meal-prep/spike/canvas-form", "force": true}'
```

## Label-read contract (page → agent → sidecar)

The page's event tells the agent to write
`.agent_tmp/spike-macros-<token>.json` including `"token": "<token>"`.
Panel reads store literal `macros` + `basis` (never scaled — the page
scales to per-100g); photos with no Nutrition Facts store
`{"no_label": true, "seen": ...}`; failures store `{"error": ...}`.
The page polls that file and handles all three outcomes.

## Token protocol (anti-stale)

Each photo pick mints `token = Date.now().toString(36)+rand`; the upload is
stored as `.agent_tmp/spike-<token>-<name>` and the agent writes
`.agent_tmp/spike-macros-<token>.json` including `"token": "<token>"`. The
page polls that file and accepts it only when `token` matches, so a
same-filename re-upload can never cross-talk with an older read.

## Known limits

- Chrome cannot preview HEIC; the page shows a note and the upload still
  works (the agent reads HEIC directly). Client-side HEIC→JPEG re-encode is
  queued.
- No-label photos (fresh meat/produce): display what the photo did show,
  wait for manual fill or another image — never estimate.
