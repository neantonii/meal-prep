# Canvas form spike (meal-ingredient trial authoring)

Throwaway spike, not the skill's deliverable. Two-column page: ingredient
form left, label-photo preview right. Uploads the photo bytes to
`.agent_tmp/`, asks the agent to read the panel into a token-scoped
`spike-macros-<token>.json` sidecar, polls and fills per-100g macros,
validates via `validate_ingredient.py --stdin`, gates Submit on zero errors.

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

## Token protocol (anti-stale)

Each photo pick mints `token = Date.now().toString(36)+rand`; the upload is
stored as `.agent_tmp/spike-<token>-<name>` and the agent writes
`.agent_tmp/spike-macros-<token>.json` including `"token": "<token>"`. The
page polls that file and accepts it only when `token` matches, so a
same-filename re-upload can never cross-talk with an older read.

## Known limits

- Chrome cannot preview HEIC; the page shows a note and the upload still
  works. Client-side HEIC→JPEG re-encode is queued.
- Photo→sidecar currently goes through a chat turn (`run: true`); rewiring to
  direct `/v1/chat/completions` vision is queued.
- No-label photos (fresh meat/produce): display the error, wait for manual
  fill or another image — never estimate.
