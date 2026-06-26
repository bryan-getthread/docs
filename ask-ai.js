// Wire the landing-page "Ask AI" bar to Mintlify's search / assistant modal.
// Auto-loaded by Mintlify on every page; uses event delegation on document so
// it keeps working across client-side (SPA) navigations.
(function () {
  function openSearch() {
    var el =
      document.getElementById("search-bar-entry") ||
      document.getElementById("search-bar-entry-mobile");
    if (el) {
      el.click();
      return true;
    }
    return false;
  }

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest && e.target.closest("#thread-ask-ai");
    if (!trigger) return;
    e.preventDefault();
    if (!openSearch()) {
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
  });
})();
