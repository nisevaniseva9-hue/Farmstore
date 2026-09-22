// Minimal JS enhancements only. No SPA framework, no build step.
// Phase-specific small scripts (quantity steppers, image preview, etc.)
// will be added here as those features are built.

document.addEventListener("DOMContentLoaded", function () {
    // Cart page: give instant visual feedback on quantity change, and
    // auto-submit so the customer doesn't have to click "Update" --
    // the server still re-validates (stock, min/max) on every submit,
    // this is purely a convenience layer on top of that.
    var qtyInputs = document.querySelectorAll(".cart-qty-input");

    qtyInputs.forEach(function (input) {
        var debounceTimer = null;

        input.addEventListener("input", function () {
            // Instant client-side estimate so the row's subtotal updates
            // as you type/click the spinner, before the server round trip.
            var unitPrice = parseFloat(input.dataset.unitPrice || "0");
            var qty = parseFloat(input.value || "0");
            var targetId = input.dataset.subtotalTarget;
            if (targetId && !isNaN(unitPrice) && !isNaN(qty)) {
                var target = document.getElementById(targetId);
                if (target) {
                    target.textContent = "₹" + (unitPrice * qty).toFixed(2);
                }
            }

            // Debounced auto-submit so we're not firing a request on
            // every single keystroke/click, but still don't need a
            // separate button press.
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                if (input.value && parseFloat(input.value) > 0) {
                    input.closest("form").requestSubmit();
                }
            }, 700);
        });
    });
});

