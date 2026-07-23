// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        document.querySelectorAll('.alert-dismissible').forEach(function(el) {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
            if (bsAlert) bsAlert.close();
        });
    }, 5000);
});

// Register service worker for PWA-like behavior (cache)
if ('serviceWorker' in navigator) {
    // Could add offline support here
}
