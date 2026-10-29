document.addEventListener("click", (event) => {
  const chip = event.target.closest('[data-toggleable="true"]');

  if (!chip || chip.disabled) return;

  const isSelected = chip.dataset.selected === "true";
  const newState = !isSelected;

  chip.dataset.selected = newState;
  chip.setAttribute("aria-pressed", newState);
});
