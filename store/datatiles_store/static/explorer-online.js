(() => {
  "use strict";
  const explorer = document.querySelector(".explorer");
  const map = document.getElementById("servedMapPreview");
  const scientific = document.getElementById("scientificPreviewPane");
  const modeButtons = document.querySelectorAll("[data-preview-mode]");
  if (!explorer || !map) return;

  const setMode = mode => {
    const online = mode === "map";
    map.hidden = !online;
    if (scientific) scientific.hidden = online;
    modeButtons.forEach(b => b.classList.toggle("active", b.dataset.previewMode === mode));
    if (!online) document.getElementById("reloadPreview")?.click();
  };
  modeButtons.forEach(button => button.addEventListener("click", () => setMode(button.dataset.previewMode)));

  if (window.DataTilesServedMap) {
    window.DataTilesServedMap.mountAll("#servedMapPreview").then(() => {
      if (map.classList.contains("served-map-unavailable")) setMode("scientific");
    });
  }
})();
