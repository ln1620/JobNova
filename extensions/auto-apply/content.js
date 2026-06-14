/**
 * Lever form auto-fill — triggered by worker after resume upload.
 */
(function () {
  const API = "http://127.0.0.1:8000";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let workerMode = false;
  const humanDelay = () => sleep(workerMode ? 80 : 350 + Math.random() * 450);
  const norm = (t) => (t || "").replace(/\s+/g, " ").trim().toLowerCase();

  function send(msg) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage(msg, (r) => {
          void chrome.runtime.lastError;
          resolve(r || { ok: false });
        });
      } catch (_) {
        resolve({ ok: false });
      }
    });
  }

  function signalDone(status, message, applicationId) {
    document.documentElement.setAttribute("data-jobnova-status", status);
    document.documentElement.setAttribute("data-jobnova-message", message || "");
    document.documentElement.setAttribute("data-jobnova-app-id", String(applicationId || ""));
    window.dispatchEvent(
      new CustomEvent("jobnova-done", { detail: { status, message, applicationId } }),
    );
  }

  function setNativeValue(el, value) {
    const str = String(value);
    const proto =
      el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    const tracker = el._valueTracker;
    if (tracker) tracker.setValue(el.value);
    if (desc?.set) desc.set.call(el, str);
    else el.value = str;
  }

  async function humanFill(el, value) {
    if (!el || value == null || value === "") return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    await humanDelay();
    el.focus();
    el.click();
    setNativeValue(el, value);
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: String(value) }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.blur();
    await humanDelay();
  }

  function fieldLabel(el) {
    const id = el.id;
    if (id) {
      const label = document.querySelector(`label[for="${id.replace(/"/g, '\\"')}"]`);
      if (label) return label.textContent.replace(/\*/g, "").trim();
    }
    const wrap = el.closest(
      ".application-field, .application-question, .application-label, li, fieldset, .section",
    );
    const label = wrap?.querySelector("label, .application-label, legend, h3, h4");
    return (label?.textContent || el.name || el.placeholder || el.getAttribute("aria-label") || "")
      .replace(/\*/g, "")
      .trim();
  }

  function sectionText(el) {
    let node = el.parentElement;
    for (let i = 0; i < 8 && node; i++) {
      const h = node.querySelector("h3, h4, .application-label, legend");
      if (h?.textContent?.trim()) return h.textContent.replace(/\*/g, "").trim();
      node = node.parentElement;
    }
    return "";
  }

  function isCriticalField(el, label) {
    const name = el.name || "";
    const l = norm(label);
    return (
      name === "name" ||
      name === "email" ||
      name === "phone" ||
      name === "company" ||
      name === "location" ||
      name.includes("linkedin") ||
      l.includes("current company") ||
      l.includes("current location")
    );
  }

  function isFilled(el) {
    if (el.type === "file") return el.files && el.files.length > 0;
    if (el.tagName === "SELECT") return el.value && el.value !== "";
    return (el.value || "").trim() !== "";
  }

  function scoreOpt(opt, target) {
    const o = norm(opt);
    const v = norm(target);
    if (!o || !v) return 0;
    if (o === v) return 100;
    if (o.includes(v) || v.includes(o)) return 85;
    if (v.startsWith("yes") && o.startsWith("yes")) return 90;
    if (v.startsWith("no") && o.startsWith("no")) return 90;
    if (v.includes("decline") && o.includes("decline")) return 90;
    if (v.includes("not a protected veteran") && o.includes("not a protected veteran")) return 95;
    if (v.includes("do not have") && o.includes("do not have")) return 95;
    return 0;
  }

  function currentCompany(parsed) {
    const exp = parsed?.experience;
    if (Array.isArray(exp) && exp.length) {
      const latest = exp[0];
      return latest.company || latest.employer || latest.organization || "";
    }
    return "";
  }

  function mapAnswer(label, answers, parsed) {
    const l = norm(label);
    if (l.includes("current company") || l === "company") return currentCompany(parsed) || "Independent";
    if (l.includes("authorized") || l.includes("eligible to work")) return answers.authorized_to_work || "Yes";
    if (l.includes("sponsorship") || l.includes("visa")) return answers.require_sponsorship || "No";
    if (l.includes("worked for") || l.includes("employed") || l.includes("before"))
      return answers.previously_employed || "No";
    if (l.includes("veteran")) return answers.veteran_status;
    if (l.includes("disability")) return answers.disability_status;
    if (l.includes("ethnic")) return answers.ethnicity;
    if (l.includes("race")) return answers.race;
    if (l.includes("gender")) return answers.gender;
    if (l.includes("intend to work") || l.includes("current location") || l.includes("city"))
      return answers.city || "";
    if (l.includes("linkedin")) return answers.linkedin_url || "";
    if (l.includes("hear about") || l.includes("referral")) return "LinkedIn";
    return null;
  }

  function mapEeoSelect(name, answers) {
    if (!name) return null;
    if (name.includes("eeo[gender]")) return answers.gender;
    if (name.includes("eeo[race]")) return answers.race;
    if (name.includes("eeo[veteran]")) return answers.veteran_status;
    if (name.includes("eeo[disability]")) return answers.disability_status;
    return null;
  }

  async function askAI(question, ctx) {
    const fallback = "I am excited about this role and believe my experience is a strong fit.";
    const base = ctx.apiUrl || API;
    const path = ctx.applicationId
      ? `/applications/worker/${ctx.applicationId}/answer-question`
      : "/applications/answer-question";
    const headers = ctx.applicationId
      ? { "Content-Type": "application/json", "X-Worker-Secret": ctx.workerSecret || "" }
      : { "Content-Type": "application/json", Authorization: `Bearer ${ctx.accessToken}` };

    try {
      const res = await fetch(`${base}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question,
          company: ctx.job?.company || "",
          job_title: ctx.job?.title || "",
        }),
      });
      if (!res.ok) return fallback;
      const data = await res.json();
      return data.answer || fallback;
    } catch (_) {
      return fallback;
    }
  }

  async function fillSelect(el, value) {
    if (!value) return;
    let best = null;
    let bestScore = 0;
    for (const opt of el.options) {
      const s = scoreOpt(opt.text, value);
      if (s > bestScore) {
        bestScore = s;
        best = opt;
      }
    }
    if (best && bestScore >= 20) {
      el.value = best.value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  async function clickOptionByText(target) {
    const v = norm(target);
    if (!v) return false;
    const candidates = document.querySelectorAll(
      "label, button, span, div, li, option",
    );
    for (const el of candidates) {
      const t = norm(el.textContent);
      if (!t || t.length > 80) continue;
      if (scoreOpt(t, v) >= 85) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        await humanDelay();
        el.click();
        return true;
      }
    }
    return false;
  }

  async function fillRadioGroups(ctx) {
    const seen = new Set();
    for (const radio of document.querySelectorAll('input[type="radio"]')) {
      const name = radio.name;
      if (!name || seen.has(name)) continue;
      seen.add(name);
      const groupLabel = `${sectionText(radio)} ${fieldLabel(radio)}`;
      const mapped = mapAnswer(groupLabel, ctx.answers, ctx.parsed);
      if (!mapped) continue;

      let picked = false;
      const radios = document.querySelectorAll(`input[type="radio"][name="${name.replace(/"/g, '\\"')}"]`);
      for (const r of radios) {
        const rLabel = r.labels?.[0]?.textContent || r.parentElement?.textContent || r.value;
        if (scoreOpt(rLabel, mapped) >= 50) {
          r.scrollIntoView({ behavior: "smooth", block: "center" });
          await humanDelay();
          r.click();
          picked = true;
          break;
        }
      }
      if (!picked) await clickOptionByText(mapped);
    }
  }

  async function fillCheckboxes(ctx) {
    for (const box of document.querySelectorAll('input[type="checkbox"]')) {
      const label = norm(
        `${fieldLabel(box)} ${box.labels?.[0]?.textContent || ""} ${box.value || ""}`,
      );
      if (label.includes("english") || label.includes("(eng)")) {
        if (!box.checked) {
          box.scrollIntoView({ behavior: "smooth", block: "center" });
          await humanDelay();
          box.click();
        }
      }
    }
  }

  async function fillSpecialSelects(ctx) {
    for (const sel of document.querySelectorAll("select")) {
      const label = norm(`${sectionText(sel)} ${fieldLabel(sel)}`);
      if (label.includes("university") || label.includes("school")) {
        let other = null;
        for (const opt of sel.options) {
          const t = norm(opt.text);
          if (t.includes("other") && t.includes("school")) other = opt;
        }
        const schools = ctx.parsed?.education || [];
        const school =
          schools[0]?.institution || schools[0]?.school || schools[0]?.name || "";
        if (school) {
          await fillSelect(sel, school);
        }
        if (!sel.value && other) {
          sel.value = other.value;
          sel.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        const mapped = mapAnswer(label, ctx.answers, ctx.parsed);
        if (mapped) await fillSelect(sel, mapped);
      }
    }
  }

  async function fillField(el, ctx) {
    const { profile, answers } = ctx;
    const name = el.name || "";
    const label = `${sectionText(el)} ${fieldLabel(el)}`;

    if (el.type === "file" || el.type === "radio" || el.type === "checkbox") return;

    if (el.tagName === "SELECT") {
      const eeo = mapEeoSelect(name, answers);
      const mapped = eeo || mapAnswer(label, answers, ctx.parsed);
      if (mapped) await fillSelect(el, mapped);
      return;
    }

    if (el.tagName === "TEXTAREA") {
      if (isFilled(el)) return;
      const mapped = mapAnswer(label, answers, ctx.parsed);
      const text = mapped || (await askAI(label || "Why are you interested?", ctx));
      await humanFill(el, text);
      return;
    }

    if (el.type === "hidden" || el.type === "submit") return;
    if (isFilled(el) && !isCriticalField(el, label)) return;

    if (name === "name") {
      await humanFill(el, profile.display_name || profile.email.split("@")[0]);
    } else if (name === "email") {
      await humanFill(el, profile.email);
    } else if (name === "phone") {
      await humanFill(el, answers.phone || "5555550100");
    } else if (name === "company" || norm(label).includes("current company")) {
      await humanFill(el, currentCompany(ctx.parsed) || "Independent");
    } else if (name === "location" || norm(label).includes("current location")) {
      const loc = answers.city
        ? `${answers.city}${answers.country ? `, ${answers.country}` : ""}`
        : "";
      if (loc) await humanFill(el, loc);
    } else if (name === "urls[linkedin]" || name.includes("linkedin")) {
      await humanFill(el, answers.linkedin_url || `https://linkedin.com/in/${profile.email.split("@")[0]}`);
    } else if (name.startsWith("questions")) {
      const text = await askAI(label || "Application question", ctx);
      await humanFill(el, text);
    } else {
      const mapped = mapAnswer(label, answers, ctx.parsed);
      if (mapped) await humanFill(el, mapped);
    }
  }

  const PLACEHOLDER_OPTION_RE = /^(select|choose|--|please)/;

  async function fillRequiredFieldsFallback(ctx) {
    const form = document.querySelector("form.applications-form") || document.querySelector("form");
    if (!form) return;

    // Text-like inputs and textareas still empty after the normal pass.
    for (const el of form.querySelectorAll("input, textarea")) {
      if (el.type === "hidden" || el.type === "submit" || el.type === "file") continue;
      if (el.type === "radio" || el.type === "checkbox") continue;
      if (!el.required && el.getAttribute("aria-required") !== "true") continue;
      if (isFilled(el)) continue;

      let fallback = "N/A";
      if (el.type === "email") fallback = ctx.profile.email;
      else if (el.type === "tel") fallback = ctx.answers.phone || "5555550100";
      else if (el.type === "url" || (el.name || "").includes("linkedin"))
        fallback = ctx.answers.linkedin_url || `https://linkedin.com/in/${ctx.profile.email.split("@")[0]}`;

      await humanFill(el, fallback);
    }

    // Required selects still unset.
    for (const sel of form.querySelectorAll("select")) {
      if (!sel.required && sel.getAttribute("aria-required") !== "true") continue;
      if (sel.value && sel.value !== "") continue;

      let chosen = null;
      for (const opt of sel.options) {
        const t = norm(opt.text);
        if (!t || !opt.value || PLACEHOLDER_OPTION_RE.test(t)) continue;
        chosen = opt;
        break;
      }
      if (chosen) {
        sel.value = chosen.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        sel.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }

    // Required radio groups with nothing checked.
    const seen = new Set();
    for (const radio of form.querySelectorAll('input[type="radio"]')) {
      const name = radio.name;
      if (!name || seen.has(name)) continue;
      seen.add(name);
      const group = form.querySelectorAll(`input[type="radio"][name="${name.replace(/"/g, '\\"')}"]`);
      const required = [...group].some(
        (r) => r.required || r.getAttribute("aria-required") === "true",
      );
      if (!required) continue;
      const anyChecked = [...group].some((r) => r.checked);
      if (anyChecked) continue;

      const first = [...group].find((r) => !r.disabled);
      if (first) {
        first.scrollIntoView({ behavior: "smooth", block: "center" });
        await humanDelay();
        first.click();
      }
    }
  }

  function readableErrors() {
    return [...document.querySelectorAll(".error, .field-error, [aria-invalid='true']")]
      .map((el) => norm(el.textContent || el.getAttribute("aria-label")))
      .filter((t) => t.includes("required") || t.includes("invalid"))
      .slice(0, 5)
      .join("; ");
  }

  async function clickSubmitAndWait(form) {
    const submit =
      form.querySelector("button.template-btn-submit") ||
      form.querySelector('button[type="submit"]');
    if (!submit) return { status: "failed", message: "No submit button found on Lever form" };

    submit.scrollIntoView({ behavior: "smooth", block: "center" });
    await humanDelay();
    submit.click();

    const start = Date.now();
    while (Date.now() - start < 20000) {
      const body = norm(document.body.innerText);
      const url = norm(location.href);
      if (
        body.includes("thank you") ||
        body.includes("application received") ||
        body.includes("thanks for applying") ||
        body.includes("successfully submitted") ||
        url.includes("thanks") ||
        url.includes("confirmation")
      ) {
        return { status: "submitted", message: "Application submitted successfully" };
      }
      if (hasErrors()) {
        return { status: "validation_error", message: readableErrors() || "Form has validation errors" };
      }
      await sleep(500);
    }
    return { status: "submitted", message: "Application submitted (no confirmation page detected)" };
  }

  async function fillAllFields(ctx) {
    const form = document.querySelector("form.applications-form") || document.querySelector("form");
    if (!form) return false;

    // Scroll through form sections so lazy fields render.
    const sections = form.querySelectorAll("h3, h4, .section, fieldset, .application-field");
    for (const sec of sections) {
      sec.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(200);
    }

    await fillSpecialSelects(ctx);
    await fillRadioGroups(ctx);
    await fillCheckboxes(ctx);

    const fields = [...form.querySelectorAll("input, textarea, select")].filter(
      (el) =>
        el.type !== "hidden" &&
        el.type !== "submit" &&
        el.type !== "radio" &&
        el.type !== "checkbox",
    );

    for (const el of fields) {
      await fillField(el, ctx);
    }
    return true;
  }

  async function waitForForm(timeout = 45000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const form = document.querySelector("form.applications-form, form");
      if (form && form.querySelector('input[name="email"]')) return form;
      await sleep(400);
    }
    return null;
  }

  function hasErrors() {
    return [...document.querySelectorAll(".error, .field-error, [aria-invalid='true']")].some((el) => {
      const t = norm(el.textContent || el.getAttribute("aria-label"));
      return t.includes("required") || t.includes("invalid");
    });
  }

  function readDomPayload() {
    try {
      const raw = document.documentElement.getAttribute("data-jobnova-payload");
      if (raw) return JSON.parse(raw);
    } catch (_) {
      /* ignore */
    }
    return null;
  }

  async function runFill() {
    if (document.documentElement.hasAttribute("data-jobnova-filling")) return;
    document.documentElement.setAttribute("data-jobnova-filling", "1");
    try {
      document.documentElement.removeAttribute("data-jobnova-status");

      let data = readDomPayload();
      if (!data) {
        for (let i = 0; i < 20; i++) {
          const res = await send({ type: "GET_APPLY_DATA" });
          if (res?.ok) {
            data = res;
            break;
          }
          await sleep(300);
        }
      }
      if (!data) {
        signalDone("failed", "No apply data", null);
        return;
      }
      workerMode = Boolean(data.worker_secret);

      const ctx = {
        profile: { email: data.email, display_name: data.display_name },
        parsed: data.parsed_json || {},
        answers: data.application_answers || {},
        job: { company: data.company, title: data.title },
        accessToken: data.access_token,
        applicationId: data.application_id,
        workerSecret: data.worker_secret,
        apiUrl: data.api_url || API,
      };

      const form = await waitForForm();
      if (!form) {
        signalDone("failed", "Lever form not found", data.application_id);
        return;
      }

      for (let i = 0; i < 30; i++) {
        const body = norm(document.body.innerText);
        if (body.includes("success") && document.querySelector('input[type="file"]')) break;
        if (document.querySelector('input[name="name"]')?.value) break;
        await sleep(500);
      }

      await fillAllFields(ctx);
      await sleep(800);
      await fillAllFields(ctx);
      await fillRequiredFieldsFallback(ctx);

      let result = await clickSubmitAndWait(form);
      if (result.status === "validation_error") {
        // One retry: fill anything still missing/invalid, then resubmit.
        await fillAllFields(ctx);
        await fillRequiredFieldsFallback(ctx);
        result = await clickSubmitAndWait(form);
      }

      const status = result.status === "validation_error" ? "failed" : result.status;
      const message =
        result.status === "validation_error"
          ? `Form filled for ${data.title} at ${data.company} but validation errors remained after retry: ${result.message}`
          : result.message;

      signalDone(status, message, data.application_id);
      await send({ type: "JOB_DONE", status, message, applicationId: data.application_id });
    } catch (err) {
      signalDone("failed", String(err), null);
    } finally {
      document.documentElement.removeAttribute("data-jobnova-filling");
    }
  }

  // Worker triggers fill AFTER resume upload via CDP (crosses isolated worlds).
  document.addEventListener(
    "jobnova-fill",
    () => {
      console.log("[jobnova] fill triggered by worker");
      runFill().catch((err) => signalDone("failed", String(err), null));
    },
    true,
  );

  const triggerObserver = new MutationObserver(() => {
    if (!document.documentElement.hasAttribute("data-jobnova-trigger-fill")) return;
    document.documentElement.removeAttribute("data-jobnova-trigger-fill");
    console.log("[jobnova] fill triggered via DOM attribute");
    runFill().catch((err) => signalDone("failed", String(err), null));
  });
  triggerObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-jobnova-trigger-fill"],
  });

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.action === "fill_form") {
      runFill().then(() => sendResponse({ ok: true }));
      return true;
    }
  });

  // Signal worker that extension content script is loaded.
  document.documentElement.setAttribute("data-jobnova-ready", "1");

  // Worker may set trigger BEFORE this script loads — run immediately if already triggered.
  if (document.documentElement.hasAttribute("data-jobnova-trigger-fill")) {
    console.log("[jobnova] fill triggered on load (missed observer)");
    runFill().catch((err) => signalDone("failed", String(err), null));
  }
})();
