# Label Vision (user recognizer)

Read a Nutrition Facts panel photo through the user's own recognition
service. **Never use built-in model vision for labels** — the user pays for
their own recognizer and requires all label reads to go through it.

## When to Use

Any label photo the user drops in chat during ingredient authoring. The
photo arrives as an embedded base64 `image` block in the conversation event
history — extract it to disk first, then call the recognizer.

## Endpoint

`http://gemini-proxy:8000/vision` — multipart form POST:

- `prompt`: plain-text instruction (keep it one line; the proxy warns on
  unknown extra form fields, so put the whole instruction in this one field).
- `file`: the image bytes (`-F "file=@<path>"`).

Reply shape: `{"text": "<JSON object as string>"}`. The inner text is the
transcription — parse it as JSON.

## Workflow

### 1. Extract the photo

Chat attachments are embedded base64 in the event history, not files on
disk. Pull the latest user message and decode. Never hardcode the
conversation id — discover it dynamically (directory names are dashless;
reinsert dashes at 8-4-4-4-12):

```sh
CID="$(ls -t "$OH_CONVERSATIONS_PATH" | head -1 | sed -E 's/(.{8})(.{4})(.{4})(.{4})(.{12})/\1-\2-\3-\4-\5/')"
KEY="$(tr -d '\n' < ~/.openhands/agent-canvas/api-key.txt)"
curl -sS -m 30 -H "X-Session-API-Key: $KEY" \
  "http://127.0.0.1:18000/api/conversations/$CID/events/search?limit=5&sort_order=TIMESTAMP_DESC&source=user" \
  | python -c "
import json,sys,base64
d=json.load(sys.stdin)
for e in d.get('items',d.get('events',[])):
    for x in e.get('llm_message',{}).get('content',[]):
        if x.get('type')=='image':
            for u in x.get('image_urls',[]):
                fmt=u.split(';')[0].split('/')[-1]
                raw=base64.b64decode(u.split(',',1)[1])
                open('<dest>.'+fmt,'wb').write(raw)
                raise SystemExit
"
```

Dead ends (do not retry — all proven to fail):

- Searching the filesystem (`/tmp`, home, workspace) for the upload: chat
  attachments never land on disk. (`inspect_image_with_vision` does see the
  image — it is the triage path, but it cannot save bytes, so it cannot
  feed the proxy.)
- Default event search order (oldest first, limit 100): recent messages sit
  past the window; always pass `sort_order=TIMESTAMP_DESC`.
- `kind=MessageEvent` (or any `kind`) filter: matches nothing. Filter by
  `source=user` instead.
- `start_page_id` / `next_page_id` paging with a stale id: returns the same
  first page forever. Fresh newest-first search is the reliable path.

Notes: the `data:image/<fmt>;base64,` prefix varies by upload format —
adjust the prefix assertion to match (split on the first comma instead of
hardcoding when unsure). Save under `.agent_tmp/` (scratch, swept after
the trial).

### 2. Call the recognizer

```sh
curl -X POST \
  -F "prompt=Transcribe the Nutrition Facts panel exactly as printed. Reply with ONLY a JSON object, no fences. Include macros (calories_kcal, protein_g, fat_g, carbs_g, fiber_g, saturated_fat_g, sugars_g, sodium_mg, potassium_mg), basis (amount, label as printed, unit), brand, product, price, pack size if visible. If NO panel visible, return no_label true with seen description. Never estimate; illegible values are null." \
  -F "file=@<path>" \
  http://gemini-proxy:8000/vision
```

### 3. Shape the result

Parse the inner `text` as JSON. Expected keys: `brand`, `product`,
`pack_size`, `price`, `basis` (`amount`, `label`, `unit`), flat macro
nutrients. Missing/optional nutrients are `null` (not printed) — never 0
unless the panel prints zero. If `no_label` is true, follow the skill's
no-label rule: say what the photo shows, wait for manual fill or another
image.

## Rules

- Production transcription goes through the proxy only. No
  `inspect_image_with_vision`, no `/v1/chat/completions` image calls for
  panels.
- `inspect_image_with_vision` is allowed for triage only: a fast
  panel-or-not check (`image_index: 0` on the latest message) before paying
  for extraction + proxy. If it reports no panel, follow the no-label rule
  without extracting anything.
- Panel-literal values only. The recognizer transcribes; it does not scale,
  convert, or estimate.
- Every read-back value needs user confirmation before drafting (show the
  side-by-side review page).
