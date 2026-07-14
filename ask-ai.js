// Adds an "Ask AI" button next to the top search bar that opens Thread's
// Mintlify AI assistant. Mintlify auto-loads any root .js file on every page;
// re-injects across client-side (SPA) navigations via a MutationObserver.
(function () {
  var BTN_ID = "thread-ask-ai-nav";

  function openAssistant() {
    // Open Mintlify's search / Ask-AI modal — the same mechanism the internal
    // docs site uses. On Pro this modal is the unified search + AI assistant.
    var s =
      document.getElementById("search-bar-entry") ||
      document.getElementById("search-bar-entry-mobile");
    if (s) {
      s.click();
      return;
    }
    // Fallback: dispatch Cmd/Ctrl+K if the search button isn't found.
    document.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        code: "KeyK",
        keyCode: 75,
        which: 75,
        metaKey: true,
        ctrlKey: true,
        bubbles: true,
      })
    );
  }

  function inject() {
    if (document.getElementById(BTN_ID)) return;
    var search = document.getElementById("search-bar-entry");
    if (!search) return;
    var wrap = search.closest(".flex-1") || search.parentElement;
    if (!wrap || !wrap.parentNode) return;

    var btn = document.createElement("button");
    btn.id = BTN_ID;
    btn.type = "button";
    btn.className = "thread-ask-ai-nav";
    btn.setAttribute("aria-label", "Ask AI");
    btn.innerHTML =
      '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .962 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .962L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.962 0z"/>' +
      '<path d="M20 3v4"/><path d="M22 5h-4"/>' +
      "</svg><span>Ask AI</span>";
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      openAssistant();
    });
    wrap.parentNode.insertBefore(btn, wrap.nextSibling);
  }

  function boot() {
    inject();
    var obs = new MutationObserver(function () {
      inject();
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
