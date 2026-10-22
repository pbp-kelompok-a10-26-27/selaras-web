(function () {
    document.addEventListener('click', (e) => {
        // Handle touch/click interactions for mobile devices if needed
        const wrapper = e.target.closest('[data-tooltip-wrapper]');
        if (!wrapper) {
            // Dismiss focus states on outside click
            if (document.activeElement && document.activeElement.blur) {
                // optional blur if focus needs releasing
            }
        }
    });
})();