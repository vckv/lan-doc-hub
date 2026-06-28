(function() {
    var loading = document.getElementById('preview-loading');
    if (loading) loading.style.display = 'none';
})();

(function() {
    var sidebar = document.getElementById('preview-sidebar');
    var btn = document.getElementById('sidebar-toggle-btn');
    if (!sidebar || !btn) return;

    var collapsed = false;

    btn.addEventListener('click', function() {
        collapsed = !collapsed;
        if (collapsed) {
            sidebar.classList.add('collapsed');
            btn.innerHTML = '▶';
            btn.title = '展开侧边栏';
        } else {
            sidebar.classList.remove('collapsed');
            btn.innerHTML = '◀';
            btn.title = '收起侧边栏';
        }
    });
})();

(function() {
    var container = document.getElementById('image-viewer');
    var img = document.getElementById('preview-img');
    var indicator = document.getElementById('zoom-indicator');
    if (!container || !img) return;

    var scale = 1;
    var minScale = 0.1;
    var maxScale = 10;
    var translateX = 0;
    var translateY = 0;

    var isPanning = false;
    var startX = 0;
    var startY = 0;
    var startTranslateX = 0;
    var startTranslateY = 0;

    function applyTransform() {
        img.style.transform = 'translate(' + translateX + 'px, ' + translateY + 'px) scale(' + scale + ')';
    }

    function updateIndicator() {
        indicator.textContent = Math.round(scale * 100) + '%';
        indicator.classList.add('visible');
        clearTimeout(indicator._timer);
        indicator._timer = setTimeout(function() {
            indicator.classList.remove('visible');
        }, 1000);
    }

    container.addEventListener('wheel', function(e) {
        e.preventDefault();
        var delta = e.deltaY > 0 ? -0.1 : 0.1;
        var newScale = scale + delta;
        newScale = Math.max(minScale, Math.min(maxScale, newScale));
        if (newScale === scale) return;

        var rect = container.getBoundingClientRect();
        var mouseX = e.clientX - rect.left;
        var mouseY = e.clientY - rect.top;

        var scaleFactor = newScale / scale;
        translateX = mouseX - (mouseX - translateX) * scaleFactor;
        translateY = mouseY - (mouseY - translateY) * scaleFactor;

        scale = newScale;
        applyTransform();
        updateIndicator();
    }, { passive: false });

    container.addEventListener('mousedown', function(e) {
        if (e.button !== 1) return;
        e.preventDefault();
        isPanning = true;
        startX = e.clientX;
        startY = e.clientY;
        startTranslateX = translateX;
        startTranslateY = translateY;
        container.classList.add('grabbing');
    });

    window.addEventListener('mousemove', function(e) {
        if (!isPanning) return;
        translateX = startTranslateX + (e.clientX - startX);
        translateY = startTranslateY + (e.clientY - startY);
        applyTransform();
    });

    window.addEventListener('mouseup', function(e) {
        if (!isPanning) return;
        isPanning = false;
        container.classList.remove('grabbing');
    });

    container.addEventListener('dblclick', function() {
        scale = 1;
        translateX = 0;
        translateY = 0;
        applyTransform();
        indicator.textContent = '100%';
        indicator.classList.add('visible');
        setTimeout(function() { indicator.classList.remove('visible'); }, 1000);
    });
})();
