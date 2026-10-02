// Spike v6: two-column — form left, photo preview right.
// Upload: multipart to .agent_tmp/, then one conversation event asks the
// agent to read the panel into the token-scoped sidecar the page polls.
// (Direct /v1/* vision was tried: every call spawns a sidebar conversation,
// nested or not. Agent-turn loop it is.)
// Validate: builds YAML from ALL fields (incl. macros), backend verdict inline.
// Submit: gated on clean verdict, draft to .agent_tmp, signal agent.
const CONV = "9b9616f4-b7d6-48e1-9d1f-d248440a2b1d";
const WORKDIR = "/projects/meal-prep";

function el(tag, text, css) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (css) n.style.cssText = css;
  return n;
}

export function activate(host) {
  return host.registerPage("ping", ({ container }) => {
    const wrap = el(
      "section",
      undefined,
      "min-height:100%;padding:2rem;color:#fff;background:#111;"
    );
    wrap.append(el("h1", "Spike v5", "font-size:1.4rem;font-weight:600;"));

    const cols = el(
      "div",
      undefined,
      "display:flex;gap:1.5rem;margin-top:1rem;flex-wrap:wrap;"
    );
    const left = el("div", undefined, "flex:1;min-width:280px;max-width:420px;");
    const right = el("div", undefined, "flex:1;min-width:280px;");
    cols.append(left, right);
    wrap.append(cols);

    const mkField = (parent, labelText, name, value) => {
      const lab = el("label", undefined, "display:block;margin-bottom:0.6rem;");
      lab.append(el("span", labelText, "display:block;font-weight:600;font-size:0.9rem;"));
      const inp = document.createElement("input");
      inp.name = name;
      inp.value = value;
      inp.style.cssText =
        "width:100%;padding:0.4rem 0.6rem;border-radius:6px;border:1px solid #555;background:#0f172a;color:#fff;";
      lab.append(inp);
      parent.append(lab);
      return inp;
    };

    const inId = mkField(left, "id (slug)", "id", "spike-butter");
    const inPrice = mkField(left, "price (CAD)", "price", "6.69");
    const inCal = mkField(left, "calories (kcal per 100g)", "cal", "");
    const inPro = mkField(left, "protein (g per 100g)", "pro", "");
    const inFat = mkField(left, "fat (g per 100g)", "fat", "");
    const inCarb = mkField(left, "carbs (g per 100g)", "carb", "");
    const inFib = mkField(left, "fiber (g per 100g)", "fib", "");

    const photoLab = el("label", undefined, "display:block;margin:0.6rem 0;");
    photoLab.append(
      el("span", "Label photo (optional)", "display:block;font-weight:600;font-size:0.9rem;")
    );
    const photoInput = document.createElement("input");
    photoInput.type = "file";
    photoInput.accept = "image/*";
    photoLab.append(photoInput);
    left.append(photoLab);

    right.append(
      el("h2", "Label photo", "font-size:1rem;font-weight:600;opacity:0.8;")
    );
    const preview = el(
      "img",
      undefined,
      "display:none;max-width:100%;border-radius:8px;border:1px solid #444;margin-top:0.5rem;"
    );
    preview.alt = "label preview";
    preview.onerror = () => {
      preview.style.display = "none";
      previewNote.textContent =
        "Preview not supported for this format in-browser (e.g. HEIC) — the upload still works; check the original on your phone.";
    };
    const previewNote = el(
      "p",
      "No photo yet — upload one to compare against the filled macros.",
      "opacity:0.6;font-size:0.9rem;margin-top:0.5rem;"
    );
    right.append(preview, previewNote);

    const btn = el(
      "button",
      "Validate",
      "margin-top:0.5rem;padding:0.6rem 1.4rem;font-size:1rem;font-weight:700;border:none;border-radius:8px;cursor:pointer;"
    );
    const submitBtn = el(
      "button",
      "Submit",
      "margin-top:0.5rem;margin-left:0.5rem;padding:0.6rem 1.4rem;font-size:1rem;font-weight:700;border:none;border-radius:8px;cursor:pointer;opacity:0.35;"
    );
    submitBtn.disabled = true;
    const status = el("p", "", "margin-top:0.6rem;font-weight:600;");
    const out = el(
      "pre",
      "Verdict appears here.",
      "margin-top:0.6rem;padding:1rem;background:#0f172a;border-radius:8px;white-space:pre-wrap;font-size:0.85rem;"
    );
    const row = el("div", undefined, undefined);
    row.append(btn, submitBtn);
    left.append(row, status, out);

    const stale = () => {
      submitBtn.disabled = true;
      submitBtn.style.opacity = "0.35";
      if (status.textContent === "Valid — Submit enabled.")
        status.textContent = "Edited — re-validate to re-enable Submit.";
    };
    [inId, inPrice, inCal, inPro, inFat, inCarb, inFib].forEach((i) =>
      i.addEventListener("input", stale)
    );

    function fillMacros(sidecar) {
      const m = sidecar.macros || {};
      const basis = sidecar.basis || { amount: 100 };
      const scale = basis.amount && basis.amount !== 100 ? 100 / basis.amount : 1;
      const map = { calories_kcal: inCal, protein_g: inPro, fat_g: inFat, carbs_g: inCarb, fiber_g: inFib };
      Object.entries(map).forEach(([k, input]) => {
        if (m[k] !== undefined && m[k] !== null) {
          const v = Number(m[k]) * scale;
          input.value = String(Math.round(v * 100) / 100);
        }
      });
      return { scale, basis };
    }

    async function pollSidecar(token, photoName, tries = 20) {
      for (let i = 0; i < tries; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        try {
          const r = await host.agentServer.request({
            method: "GET",
            path: `/api/file/download?path=${encodeURIComponent(`${WORKDIR}/.agent_tmp/spike-macros-${token}.json`)}`,
          });
          const text = typeof r === "string" ? r : r.content || r.data || JSON.stringify(r);
          const sidecar = JSON.parse(text);
          if (sidecar && sidecar.token === token) {
            if (sidecar.no_label) {
              status.textContent =
                `No Nutrition Facts in ${photoName}` +
                (sidecar.seen ? ` (photo shows: ${sidecar.seen})` : "") +
                ` — fill macros manually from a source you name, or upload a different image.`;
              return;
            }
            if (sidecar.error) {
              status.textContent = `Label read failed: ${sidecar.error} — fill manually or re-upload.`;
              return;
            }
            if (sidecar.macros) {
              const { scale, basis } = fillMacros(sidecar);
              const basisLabel = basis.label || `per ${basis.amount}g`;
              status.textContent =
                `Macros filled from ${photoName} (panel: ${basisLabel}` +
                (scale !== 1 ? `, scaled x${Math.round(scale * 100) / 100} to per-100g` : "") +
                `) — check against the photo, then Validate.`;
              stale();
              return;
            }
          }
        } catch (_) {}
        status.textContent = `Waiting for agent read… (${i + 1}/${tries})`;
      }
      status.textContent = "Agent read timed out — fill macros manually or re-upload.";
    }

    photoInput.addEventListener("change", async () => {
      stale();
      const f = photoInput.files[0];
      [inCal, inPro, inFat, inCarb, inFib].forEach((i) => {
        i.value = "";
      });
      if (!f) {
        preview.style.display = "none";
        previewNote.textContent = "No photo yet.";
        return;
      }
      const token =
        Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      const storedName = `spike-${token}-${f.name}`;
      preview.src = URL.createObjectURL(f);
      preview.style.display = "block";
      previewNote.textContent = f.name;
      status.textContent = "Uploading photo…";
      try {
        const fd = new FormData();
        fd.append("file", f, f.name);
        await host.agentServer.request({
          method: "POST",
          path: `/api/file/upload?path=${encodeURIComponent(`${WORKDIR}/.agent_tmp/${storedName}`)}`,
          body: fd,
        });
        await host.agentServer.request({
          method: "POST",
          path: `/api/conversations/${CONV}/events`,
          body: {
            role: "user",
            content: [
              {
                type: "text",
                text:
                  `[ping-app] photo saved as .agent_tmp/${storedName} with token ${token} — ` +
                  `read the Nutrition Facts panel and write .agent_tmp/spike-macros-${token}.json ` +
                  `with "token": "${token}", panel-literal "macros" (calories_kcal, protein_g, fat_g, ` +
                  `carbs_g, fiber_g required; saturated_fat_g, sugars_g, sodium_mg, potassium_mg when ` +
                  `printed, else null), "basis" {amount, label as printed, unit}, and "note". ` +
                  `If NO panel is visible, write {"no_label": true, "seen": "<product, weight, price if shown>"}. ` +
                  `Never estimate; illegible values are null.`,
              },
            ],
            run: true,
          },
        });
        status.textContent = "Photo uploaded — agent reading…";
        pollSidecar(token, f.name);
      } catch (e) {
        status.textContent = `Upload failed: ${(e && e.message) || e}`;
      }
    });

    btn.addEventListener("click", async () => {
      const v = {
        id: inId.value.trim(),
        price: inPrice.value.trim() || "0",
        cal: inCal.value.trim() || "0",
        pro: inPro.value.trim() || "0",
        fat: inFat.value.trim() || "0",
        carb: inCarb.value.trim() || "0",
        fib: inFib.value.trim() || "0",
      };
      status.textContent = "Validating…";
      out.textContent = "";
      try {
        const yaml =
          `aisle_file: dairy.yaml\nid: ${v.id}\nname: Spike Butter\nstep_name: ${v.id}\n` +
          `aisle: dairy\nstorage: refrigerated\nshelf_life_days: 90\n` +
          `reference:\n  brand: Spike\n  product: Spike Butter\n  price: ${v.price}\n` +
          `macros:\n  unit: g\n  amount: 100\n  calories_kcal: ${v.cal}\n` +
          `  protein_g: ${v.pro}\n  fat_g: ${v.fat}\n  carbs_g: ${v.carb}\n  fiber_g: ${v.fib}\n` +
          `conversions:\n  - from: package\n    to: g\n    factor: 454\n`;
        const cmd =
          `cat > ${WORKDIR}/.agent_tmp/spike-v4.yaml <<'YAMLEOF'\n${yaml}YAMLEOF\n` +
          `python ${WORKDIR}/.agents/skills/meal-ingredient/scripts/validate_ingredient.py --stdin < ${WORKDIR}/.agent_tmp/spike-v4.yaml`;
        const r = await host.agentServer.request({
          method: "POST",
          path: "/api/bash/execute_bash_command",
          body: { command: cmd },
        });
        let verdict = null;
        const raw = r.stdout !== undefined ? r.stdout : r.output;
        try {
          verdict = typeof raw === "string" ? JSON.parse(raw) : raw;
          if (typeof verdict === "string") verdict = JSON.parse(verdict);
        } catch (_) {}
        if (!verdict || typeof verdict !== "object") {
          status.textContent = "Backend did not return JSON.";
          out.textContent = (typeof raw === "string" ? raw : JSON.stringify(r)).slice(0, 800);
          return;
        }
        const lines = [];
        if (verdict.errors && verdict.errors.length) {
          lines.push("ERRORS (fix and re-validate):");
          verdict.errors.forEach((e) => lines.push("  - " + e));
        }
        if (verdict.warnings && verdict.warnings.length) {
          lines.push("WARNINGS (confirm each):");
          verdict.warnings.forEach((w) => lines.push("  - " + w));
        }
        if (verdict.ok && verdict.derived) {
          const d = verdict.derived;
          lines.push(
            `DERIVED: package ${d.package_weight_g}g, $${d.price_per_100g}/100g, ${d.calories_kcal} kcal`
          );
        }
        out.textContent = lines.join("\n") || "(empty verdict)";
        const clean = verdict.ok && !(verdict.errors && verdict.errors.length);
        submitBtn.disabled = !clean;
        submitBtn.style.opacity = clean ? "1" : "0.35";
        status.textContent = clean ? "Valid — Submit enabled." : "Invalid — see errors.";
      } catch (e) {
        status.textContent = `Failed: ${(e && e.message) || e}`;
      }
    });

    submitBtn.addEventListener("click", async () => {
      if (submitBtn.disabled) return;
      status.textContent = "Submitting…";
      try {
        const r = await host.agentServer.request({
          method: "POST",
          path: "/api/bash/execute_bash_command",
          body: {
            command: `cp ${WORKDIR}/.agent_tmp/spike-v4.yaml ${WORKDIR}/.agent_tmp/spike-submitted.yaml && echo submitted`,
          },
        });
        out.textContent += `\nSUBMIT: ${(r.stdout || r.output || "").trim()} (.agent_tmp/spike-submitted.yaml)`;
        status.textContent = "Submitted — agent will place it in the catalog.";
        await host.agentServer.request({
          method: "POST",
          path: `/api/conversations/${CONV}/events`,
          body: {
            role: "user",
            content: [
              {
                type: "text",
                text: "[ping-app] v5 submit: draft at .agent_tmp/spike-submitted.yaml — please place it in the catalog",
              },
            ],
            run: true,
          },
        });
      } catch (e) {
        status.textContent = `Submit failed: ${(e && e.message) || e}`;
      }
    });

    container.append(wrap);
    return () => wrap.remove();
  });
}
