const statusCardId = "status-update-card";
const siteHeader = document.querySelector(".site-header");

function revealStatusControl(card, control) {
  if (siteHeader) {
    const headerHeight = siteHeader.getBoundingClientRect().height;
    card.style.setProperty("--status-header-height", `${headerHeight}px`);
  }
  control.scrollIntoView({ block: "start" });
}

document.addEventListener("htmx:afterSettle", (event) => {
  const card = event.target;
  if (card.id !== statusCardId) return;

  const warning = card.querySelector("#status-balance-warning, #status-transition-error");
  if (!warning) return;

  warning.focus({ preventScroll: true });
  revealStatusControl(card, warning);
});

const statusCard = document.getElementById(statusCardId);
if (statusCard && window.location.hash === `#${statusCardId}`) {
  revealStatusControl(statusCard, statusCard);
}
