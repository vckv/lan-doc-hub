/**
 * LAN Doc Hub — 共享工具函数
 * 所有业务模块共用的纯逻辑函数，不依赖 DOM / 全局状态。
 */
window.LanDocHub = window.LanDocHub || {};

LanDocHub.Utils = {

    /**
     * 文件大小格式化
     * @param {number|null|undefined} bytes
     * @returns {string}
     */
    formatFileSize: function (bytes) {
        if (bytes === null || bytes === undefined) return '--';
        bytes = parseInt(bytes, 10);
        if (isNaN(bytes)) return '--';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    },

    /**
     * HTML 转义（防 XSS）
     * @param {string} str
     * @returns {string}
     */
    escapeHtml: function (str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    /**
     * 文件夹树扁平化（把嵌套树结构展平为一维数组）
     * @param {Array}  nodes  树节点数组
     * @param {number} depth  当前深度
     * @returns {Array}
     */
    flattenTree: function (nodes, depth) {
        depth = depth || 0;
        var flat = [];
        if (!nodes || !nodes.length) return flat;
        $.each(nodes, function (i, node) {
            flat.push({
                id: node.id,
                name: node.name,
                project_id: node.project_id,
                is_project_root: node.is_project_root,
                depth: depth,
            });
            if (node.children && node.children.length > 0) {
                flat = flat.concat(LanDocHub.Utils.flattenTree(node.children, depth + 1));
            }
        });
        return flat;
    },

    /**
     * 获取 CSRF Token
     * @returns {string}
     */
    getCsrfToken: function () {
        return $('meta[name="csrf-token"]').attr('content') || '';
    },

    /**
     * 在容器中显示内联错误提示（替代 alert）
     * @param {jQuery} $container
     * @param {string} msg
     */
    showInlineError: function ($container, msg) {
        $container.html(
            '<div class="file-empty"><p class="text-danger">' + msg + '</p></div>'
        );
    },

    /**
     * 获取当前登录用户的显示名
     * @returns {string}
     */
    getUserDisplayName: function () {
        return $('.sidebar').data('user-display-name') || '当前用户';
    },
};
