document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-select-on-click]").forEach((input) => {
    input.addEventListener("click", () => input.select());
  });

  document.querySelectorAll("[data-reload-page]").forEach((button) => {
    button.addEventListener("click", () => window.location.reload());
  });
});
