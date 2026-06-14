/**
 * Page-context fill fallback (injected by worker via CDP).
 */
(function () {
  if (window.__JOBNOVA_PAGE_FILL__) return;
  window.__JOBNOVA_PAGE_FILL__ = true;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function signalDone(status, message, applicationId) {
    document.documentElement.setAttribute("data-jobnova-status", status);
    document.documentElement.setAttribute("data-jobnova-message", message || "");
    document.documentElement.setAttribute("data-jobnova-app-id", String(applicationId || ""));
  }

  function setVal(el, value) {
    if (!el || value == null || value === "") return;
    const str = String(value);
    const proto =
      el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc?.set) desc.set.call(el, str);
    else el.value = str;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function askAI(question, data) {
    const fallback = "I am excited about this role and believe my experience is a strong fit.";
    try {
      const res = await fetch(
        `${data.api_url}/applications/worker/${data.application_id}/answer-question`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Worker-Secret": data.worker_secret,
          },
          body: JSON.stringify({
            question,
            company: data.company || "",
            job_title: data.title || "",
          }),
        },
      );
      if (!res.ok) return fallback;
      const body = await res.json();
      return body.answer || fallback;
    } catch (_) {
      return fallback;
    }
  }

  window.__jobnovaPageFill = async function () {
    if (document.documentElement.hasAttribute("data-jobnova-filling")) return;
    document.documentElement.setAttribute("data-jobnova-filling", "1");
    try {
      const raw = document.documentElement.getAttribute("data-jobnova-payload");
      if (!raw) {
        signalDone("failed", "No payload for page fill", null);
        return;
      }
      const data = JSON.parse(raw);
      const answers = data.application_answers || {};
      const form = document.querySelector("form.applications-form") || document.querySelector("form");
      if (!form) {
        signalDone("failed", "Lever form not found", data.application_id);
        return;
      }

      setVal(form.querySelector('input[name="name"]'), data.display_name || data.email?.split("@")[0]);
      setVal(form.querySelector('input[name="email"]'), data.email);
      setVal(form.querySelector('input[name="phone"]'), answers.phone);
      setVal(
        form.querySelector('input[name="urls[LinkedIn]"]') || form.querySelector('input[name*="linkedin"]'),
        answers.linkedin_url,
      );
      setVal(form.querySelector('input[name="location"]'), answers.city);

      for (const ta of form.querySelectorAll("textarea")) {
        if ((ta.value || "").trim()) continue;
        const label = (ta.closest("li, .application-question")?.innerText || "").slice(0, 200);
        setVal(ta, await askAI(label || "Why this role?", data));
        await sleep(150);
      }

      for (const input of form.querySelectorAll('input[name^="questions"]')) {
        if ((input.value || "").trim()) continue;
        const label = (input.closest("li")?.innerText || "").slice(0, 200);
        setVal(input, await askAI(label || "Application question", data));
        await sleep(150);
      }

      // Do NOT auto-submit — leave the filled form for the user to review
      // and submit themselves.
      signalDone(
        "blocked",
        `Form filled for ${data.title} at ${data.company} — review and click Submit yourself`,
        data.application_id,
      );
    } catch (err) {
      signalDone("failed", String(err), null);
    } finally {
      document.documentElement.removeAttribute("data-jobnova-filling");
    }
  };
})();
