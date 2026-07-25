/* The direct uploader owns file, preview, and save state.  This module only
 * makes the styled drop zone keyboard/click accessible. */
(() => {
  document.addEventListener("click", (event) => {
    const zone = event.target.closest("[data-report-attachment-picker] .upload-dropzone");
    if (!zone || event.target.matches("input")) return;
    event.preventDefault();
    zone.querySelector("[data-report-attachment-input]")?.click();
  });
  document.addEventListener("keydown", (event) => {
    const zone = event.target.closest("[data-report-attachment-picker] .upload-dropzone");
    if (!zone || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    zone.querySelector("[data-report-attachment-input]")?.click();
  });
})();
