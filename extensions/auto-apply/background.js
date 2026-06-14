const API = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (msg.type === "SET_APPLY_DATA") {
      await chrome.storage.local.set({ applyData: msg.data });
      sendResponse({ ok: true });
      return;
    }

    if (msg.type === "GET_APPLY_DATA") {
      const { applyData } = await chrome.storage.local.get("applyData");
      sendResponse({ ok: Boolean(applyData), ...(applyData || {}) });
      return;
    }

    if (msg.type === "JOB_DONE") {
      await chrome.storage.local.set({
        jobResult: {
          status: msg.status,
          message: msg.message,
          applicationId: msg.applicationId,
          at: Date.now(),
        },
      });
      sendResponse({ ok: true });
      return;
    }

    if (msg.action === "fill_form" && sender.tab?.id) {
      chrome.tabs.sendMessage(sender.tab.id, { action: "fill_form" }, () => {
        void chrome.runtime.lastError;
      });
      sendResponse({ ok: true });
      return;
    }

    if (msg.type === "CLEAR_JOB_RESULT") {
      await chrome.storage.local.remove("jobResult");
      sendResponse({ ok: true });
      return;
    }
  })();
  return true;
});
