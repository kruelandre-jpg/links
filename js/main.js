(function () {
  var gift = document.getElementById("quadril");

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function focusGift() {
    if (location.hash !== "#quadril" || !gift) return;
    gift.scrollIntoView({
      block: "nearest",
      behavior: reducedMotion() ? "auto" : "smooth",
    });
    gift.focus({ preventScroll: true });
  }

  focusGift();
  window.addEventListener("hashchange", focusGift);
})();
