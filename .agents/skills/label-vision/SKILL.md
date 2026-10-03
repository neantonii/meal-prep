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
disk. Run the extract script — one call, no manual conversation-id
surgery (it discovers the newest conversation and searches newest-first):

```sh
python .agents/skills/label-vision/scripts/extract_chat_image.py .agent_tmp/label
```

It saves `.agent_tmp/label.<fmt>` (extension from the upload MIME type)
and prints the path + byte count. Nonzero exit with a plain error means
no image found — the user hasn't dropped one yet.

`.agent_tmp/` is shared across chats in the same repo: never trust files
already there (another conversation's `draft.json` / `label.png` may be
sitting in it). Always extract fresh, and use distinct names per run
(`label-turkey`, `label-beans`) when juggling multiple photos.

Dead ends (do not retry — all proven to fail):

- Searching the filesystem (`/tmp`, home, workspace) for the upload: chat
  attachments never land on disk. (`inspect_image_with_vision` does see the
  image — it is the triage path, but it cannot save bytes, so it cannot
  feed the proxy.)
- Hand-rolled `curl /events/search` pipelines: the script already does
  newest-first + `source=user` filtering. Reimplementing it in chat wastes
  ~10 tool calls on CID discovery, stale-file forensics, and repeated
  searches.

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

## Scripts

- **`scripts/extract_chat_image.py`** — extracts the latest user-attached
  chat image to disk: `python scripts/extract_chat_image.py
  .agent_tmp/label` → saves `.agent_tmp/label.<fmt>`, prints path + bytes.
  Discovers the newest conversation, searches newest-first, decodes the
  first image block. Nonzero exit = no image found. Stdlib only.
