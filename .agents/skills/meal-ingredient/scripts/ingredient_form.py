"""Generate the ingredient entry HTML form from the committed DTO schema.

Usage:
    python ingredient_form.py > /tmp/ingredient-form.html

Reads ``schemas/ingredient.schema.json`` (fields, required lists, Field
descriptions), ``data/aisles.yaml`` (aisle dropdown), and
``data/units.yaml`` (unit datalists). Regenerate — never hand-edit the HTML.

The page holds zero domain validation: it serializes the form into the exact
stdin payload for ``validate_ingredient.py --stdin``, and renders a pasted
backend JSON verdict (errors block submit, warnings list for acceptance).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO_ROOT / "schemas" / "ingredient.schema.json"


def _load() -> tuple[dict, list[dict], list[str]]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = schema.get("$defs", {})
    aisles = yaml.safe_load((REPO_ROOT / "data" / "aisles.yaml").read_text())["aisles"]
    units_data = yaml.safe_load((REPO_ROOT / "data" / "units.yaml").read_text())[
        "units"
    ]
    units: list[str] = []
    for group in units_data.values():
        units.extend(group.get("allowed", {}).keys())
    return defs, aisles, units


def _desc(defs: dict, ref: str, prop: str) -> str:
    name = ref.split("/")[-1]
    return defs.get(name, {}).get("properties", {}).get(prop, {}).get("description", "")


def _field(
    name: str,
    label: str,
    desc: str,
    required: bool = False,
    input_type: str = "text",
    datalist: str = "",
    value: str = "",
) -> str:
    req = " required" if required else ""
    list_attr = f' list="{datalist}"' if datalist else ""
    help_html = f'<p class="help">{html.escape(desc)}</p>' if desc else ""
    return (
        f'<label class="field"><span>{html.escape(label)}'
        + (" *" if required else "")
        + f"</span>"
        f'<input name="{name}" type="{input_type}" value="{html.escape(value)}"{req}{list_attr}>'
        f"{help_html}</label>"
    )


def main() -> int:
    defs, aisles, units = _load()
    props = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]
    required_top = set(
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8")).get("required", [])
    )

    aisle_options = "\n".join(
        f'            <option value="{a["id"]}">{html.escape(a["name"])}</option>'
        for a in aisles
    )
    unit_options = "\n".join(f'        <option value="{u}"></option>' for u in units)

    ref_desc = _desc(defs, props["reference"].get("$ref", ""), "")
    ref_props = defs.get("ReferenceInfo", {}).get("properties", {})
    ref_required = set(defs.get("ReferenceInfo", {}).get("required", []))
    macros_props = defs.get("MacrosInfoDTO", {}).get("properties", {})
    macros_required = set(defs.get("MacrosInfoDTO", {}).get("required", []))
    macro_order = [
        "unit",
        "amount",
        "calories_kcal",
        "protein_g",
        "fat_g",
        "carbs_g",
        "fiber_g",
        "saturated_fat_g",
        "sugars_g",
        "sodium_mg",
        "potassium_mg",
    ]

    def ref_field(name: str, label: str) -> str:
        return _field(
            f"reference.{name}",
            label,
            ref_props.get(name, {}).get("description", ""),
            required=name in ref_required,
            input_type="number" if name == "price" else "text",
        )

    def macro_field(name: str) -> str:
        return _field(
            f"macros.{name}",
            name,
            macros_props.get(name, {}).get("description", ""),
            required=name in macros_required,
            input_type="text" if name == "unit" else "number",
        )

    identity_fields = "\n".join(
        [
            _field(
                "id", "id (slug)", props["id"].get("description", ""), required=True
            ),
            _field("name", "name", props["name"].get("description", ""), required=True),
            _field(
                "step_name",
                "step_name",
                props["step_name"].get("description", ""),
                required=True,
            ),
            _field(
                "shelf_life_days",
                "shelf_life_days",
                props["shelf_life_days"].get("description", ""),
                required=True,
                input_type="number",
            ),
        ]
    )
    macro_fields = "\n".join(macro_field(n) for n in macro_order)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>New Ingredient Entry</title>
<style>
:root {{ --bg: #0f172a; --surface: #1e293b; --border: #334155;
--text: #f8fafc; --muted: #94a3b8; --primary: #38bdf8;
--ok: #10b981; --warn: #f59e0b; --err: #ef4444; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text);
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
line-height: 1.5; padding: 24px 16px; }}
.container {{ max-width: 720px; margin: 0 auto; }}
h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
.sub {{ color: var(--muted); margin-bottom: 20px; font-size: 0.9rem; }}
section {{ background: var(--surface); border: 1px solid var(--border);
border-radius: 12px; padding: 18px; margin-bottom: 16px; }}
h2 {{ font-size: 1.05rem; margin-bottom: 12px; }}
.field {{ display: block; margin-bottom: 12px; }}
.field span {{ display: block; font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; }}
.field input, .field select, .field textarea {{
width: 100%; padding: 8px 10px; border-radius: 8px;
border: 1px solid var(--border); background: var(--bg); color: var(--text);
font-size: 0.95rem; }}
.help {{ font-size: 0.8rem; color: var(--muted); margin-top: 3px; }}
.row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
pre {{ background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
padding: 12px; overflow-x: auto; font-size: 0.82rem; white-space: pre-wrap; }}
button {{ padding: 10px 18px; border-radius: 8px; border: none; font-weight: 700;
cursor: pointer; font-size: 0.95rem; margin-right: 8px; }}
#validate-btn {{ background: var(--primary); color: #04222f; }}
#submit-btn {{ background: var(--ok); color: #04150d; }}
#submit-btn:disabled {{ opacity: 0.35; cursor: not-allowed; }}
#verdict {{ margin-top: 12px; }}
.err {{ color: var(--err); }} .warn {{ color: var(--warn); }} .ok {{ color: var(--ok); }}
ul {{ margin: 6px 0 6px 20px; font-size: 0.9rem; }}
textarea.paste {{ min-height: 120px; font-family: monospace; }}
.actions {{ margin: 12px 0; }}
</style>
</head>
<body>
<div class="container">
<h1>New Ingredient Entry</h1>
<p class="sub">Fill every section, Validate, accept warnings, then Submit.
Validation runs in the Python pipeline — this page only renders its verdict.</p>

<section><h2>1 · Slot</h2>
<label class="field"><span>aisle *</span>
<select name="aisle" required>
{aisle_options}
</select>
<p class="help">{html.escape(props["aisle"].get("description", ""))} Must equal the target file stem.</p></label>
<label class="field"><span>storage *</span>
<select name="storage" required>
<option value="ambient">ambient</option>
<option value="refrigerated">refrigerated</option>
<option value="frozen">frozen</option>
</select>
<p class="help">{html.escape(props["storage"].get("description", ""))}</p></label>
</section>

<section><h2>2 · Identity</h2>
{identity_fields}
</section>

<section><h2>3 · Retail reference</h2>
{ref_field("brand", "brand")}
{ref_field("product", "product")}
{ref_field("price", "price (CAD)")}
</section>

<section><h2>4 · Macros basis (transcribe the label verbatim)</h2>
{macro_fields}
</section>

<section><h2>5 · Conversions (one YAML edge per line)</h2>
<label class="field"><span>custom_units (optional, YAML mapping)</span>
<textarea name="custom_units" rows="2" placeholder="clove: [clove, cloves]"></textarea></label>
<label class="field"><span>conversions * (YAML list)</span>
<textarea name="conversions" rows="5" required placeholder="- from: package&#10;  to: g&#10;  factor: 454"></textarea>
<p class="help">{html.escape(props["conversions"].get("description", ""))}</p></label>
</section>

<section><h2>6 · Validate</h2>
<div class="actions"><button id="validate-btn" type="button">Validate</button></div>
<pre id="payload" hidden></pre>
<p class="help">Validate shows the exact stdin payload below. Copy it, run
<code>python .agents/skills/meal-ingredient/scripts/validate_ingredient.py --stdin</code>
with it pasted on stdin, then paste the JSON verdict:</p>
<label class="field"><span>Backend verdict (paste JSON)</span>
<textarea id="verdict-paste" class="paste" placeholder='{{"ok": true, ...}}'></textarea></label>
<div class="actions"><button id="render-btn" type="button">Render verdict</button></div>
<div id="verdict"></div>
</section>

<section><h2>7 · Submit</h2>
<div class="actions"><button id="submit-btn" type="button" disabled>Submit</button></div>
<pre id="entry-yaml" hidden></pre>
<p class="help">Submit enables only when the last verdict has no errors.
Copy the YAML above into <code>data/ingredients/&lt;aisle&gt;.yaml</code> in id-sorted
position, then continue the skill close-out in chat.</p>
</section>
</div>

<datalist id="units">
{unit_options}
</datalist>

<script>
"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
let lastOk = false;

function collect() {{
  const entry = {{}};
  for (const el of $$("input[name], select[name]")) {{
    if (!el.value) continue;
    const parts = el.name.split(".");
    if (parts.length === 1) entry[parts[0]] = coerce(el.value);
    else {{
      entry[parts[0]] = entry[parts[0]] || {{}};
      entry[parts[0]][parts[1]] = coerce(el.value);
    }}
  }}
  const cu = document.querySelector('textarea[name="custom_units"]').value.trim();
  if (cu) entry["_custom_units_raw"] = cu;
  const conv = document.querySelector('textarea[name="conversions"]').value.trim();
  if (conv) entry["_conversions_raw"] = conv;
  return entry;
}}

function coerce(v) {{
  if (v !== "" && !isNaN(Number(v))) return Number(v);
  return v;
}}

function toYaml(entry) {{
  const lines = [];
  lines.push("aisle_file: " + entry.aisle + ".yaml");
  for (const k of ["id", "name", "step_name", "aisle", "storage", "shelf_life_days"]) {{
    if (entry[k] !== undefined) lines.push(k + ": " + JSON.stringify(entry[k]));
  }}
  for (const section of ["reference", "macros"]) {{
    if (!entry[section]) continue;
    lines.push(section + ":");
    for (const [k, v] of Object.entries(entry[section])) {{
      lines.push("  " + k + ": " + JSON.stringify(v));
    }}
  }}
  if (entry["_custom_units_raw"]) {{
    lines.push("custom_units:");
    for (const raw of entry["_custom_units_raw"].split("\\n")) {{
      lines.push("  " + raw.trim());
    }}
  }}
  if (entry["_conversions_raw"]) {{
    lines.push("conversions:");
    for (const raw of entry["_conversions_raw"].split("\\n")) {{
      lines.push(raw.trimEnd() ? "  " + raw : raw);
    }}
  }}
  return lines.join("\\n") + "\\n";
}}

$("#validate-btn").addEventListener("click", () => {{
  const yamlText = toYaml(collect());
  const payload = $("#payload");
  payload.textContent = yamlText;
  payload.hidden = false;
  const out = $("#entry-yaml");
  out.textContent = yamlText.replace(/^aisle_file: .*\\n/, "");
  out.hidden = false;
  lastOk = false;
  $("#submit-btn").disabled = true;
  $("#verdict").innerHTML = "";
}});

$("#render-btn").addEventListener("click", () => {{
  const box = $("#verdict");
  let verdict;
  try {{
    verdict = JSON.parse($("#verdict-paste").value);
  }} catch (e) {{
    box.innerHTML = '<p class="err">Pasted text is not valid JSON.</p>';
    return;
  }}
  let outHtml = "";
  if (verdict.errors && verdict.errors.length) {{
    outHtml += '<p class="err"><strong>Errors — fix and re-validate:</strong></p><ul>'
      + verdict.errors.map((e) => "<li>" + escapeHtml(e) + "</li>").join("") + "</ul>";
  }}
  if (verdict.warnings && verdict.warnings.length) {{
    outHtml += '<p class="warn"><strong>Warnings — confirm each with the user:</strong></p><ul>'
      + verdict.warnings.map((w) => "<li>" + escapeHtml(w) + "</li>").join("") + "</ul>";
  }}
  if (verdict.ok && verdict.derived) {{
    const d = verdict.derived;
    outHtml += '<p class="ok"><strong>Derived:</strong> package ' + d.package_weight_g
      + 'g · $' + d.price_per_100g + '/100g · ' + d.calories_kcal + ' kcal · P '
      + d.protein_g + 'g F ' + d.fat_g + 'g C ' + d.carbs_g + 'g fiber ' + d.fiber_g + 'g</p>';
  }}
  if (!outHtml) outHtml = '<p class="err">Verdict has no errors, warnings, or derived block.</p>';
  box.innerHTML = outHtml;
  lastOk = verdict.ok === true && (!verdict.errors || !verdict.errors.length);
  $("#submit-btn").disabled = !lastOk;
}});

function escapeHtml(s) {{
  return String(s).replace(/[&<>"']/g, (c) => ({{ "&": "&amp;", "<": "&lt;",
    ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[c]));
}}

$("#submit-btn").addEventListener("click", () => {{
  if (!lastOk) return;
  const out = $("#entry-yaml");
  out.hidden = false;
  navigator.clipboard.writeText(out.textContent).catch(() => {{}});
}});
</script>
</body>
</html>
"""
    _ = (ref_desc, required_top)
    print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
