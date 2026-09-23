// Minimal JS enhancements only. No SPA framework, no build step.
// Phase-specific small scripts (quantity steppers, image preview, etc.)
// will be added here as those features are built.

document.addEventListener("DOMContentLoaded", function () {
    // Stepper buttons for plus / minus in Flipkart style cart
    document.querySelectorAll(".cart-stepper-form").forEach(function (form) {
        var input = form.querySelector(".cart-qty-input");
        var minusBtn = form.querySelector(".btn-qty-minus");
        var plusBtn = form.querySelector(".btn-qty-plus");

        if (input && minusBtn && plusBtn) {
            minusBtn.addEventListener("click", function () {
                var current = parseFloat(input.value || "1");
                var min = parseFloat(input.min || "1");
                if (current > min) {
                    input.value = current - 1;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
            });

            plusBtn.addEventListener("click", function () {
                var current = parseFloat(input.value || "1");
                var max = input.max ? parseFloat(input.max) : Infinity;
                if (current < max) {
                    input.value = current + 1;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
            });
        }
    });

    // Cart page: live subtotal and auto-submit
    var qtyInputs = document.querySelectorAll(".cart-qty-input");

    qtyInputs.forEach(function (input) {
        var debounceTimer = null;

        input.addEventListener("input", function () {
            var unitPrice = parseFloat(input.dataset.unitPrice || "0");
            var qty = parseFloat(input.value || "0");
            var targetId = input.dataset.subtotalTarget;
            if (targetId && !isNaN(unitPrice) && !isNaN(qty)) {
                var target = document.getElementById(targetId);
                if (target) {
                    target.textContent = "₹" + (unitPrice * qty).toFixed(2);
                }
            }

            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                if (input.value && parseFloat(input.value) > 0) {
                    input.closest("form").requestSubmit();
                }
            }, 500);
        });
    });
});

