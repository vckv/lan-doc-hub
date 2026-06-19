/**
 * F2-1 文件夹树交互
 * - AJAX 加载 /api/folders/tree
 * - 点击展开/收起子节点
 * - 零第三方依赖（纯 jQuery + Unicode 图标）
 */
$(function () {
    var $sidebar = $('.sidebar');

    // 加载文件夹树
    $.ajax({
        url: '/api/folders/tree',
        method: 'GET',
        dataType: 'json'
    })
    .done(function (resp) {
        if (!resp.success || !resp.tree) {
            $sidebar.find('.sidebar-placeholder').html('<div class="text-muted p-3">暂无项目文件夹</div>');
            return;
        }
        $sidebar.find('.sidebar-placeholder').remove();
        var $tree = buildTreeHtml(resp.tree);
        $sidebar.append($tree);
        bindTreeEvents($sidebar);
    })
    .fail(function () {
        $sidebar.find('.sidebar-placeholder').html(
            '<div class="text-muted p-3">文件夹加载失败<br><small>请刷新页面后重试</small></div>'
        );
    });

    // 递归构建树 HTML（与 partials/folder_tree.html 结构对应）
    function buildTreeHtml(nodes) {
        var $ul = $('<ul class="folder-tree"></ul>');
        $.each(nodes, function (i, node) {
            var $li = $('<li class="tree-node"></li>')
                .attr('data-folder-id', node.id);
            if (node.is_project_root) {
                $li.attr('data-is-root', 'true');
            }

            var $item = $('<div class="tree-item"></div>');
            var hasChildren = node.children && node.children.length > 0;
            var toggleIcon = hasChildren ? '\u25B6' : '\u00B7';
            var folderIcon = node.is_project_root ? '\uD83D\uDCC1' : '\uD83D\uDCC2';

            $item.append('<span class="tree-toggle">' + toggleIcon + '</span>');
            $item.append('<span class="tree-icon">' + folderIcon + '</span>');
            $item.append('<span class="tree-name" title="' + node.name + '">' + node.name + '</span>');
            $li.append($item);

            if (hasChildren) {
                var $childUl = $('<ul class="tree-children" style="display:none;"></ul>');
                $childUl.append(buildTreeHtml(node.children).children());
                $li.append($childUl);
            }

            $ul.append($li);
        });
        return $ul;
    }

    // 绑定展开/收起事件
    function bindTreeEvents($container) {
        $container.on('click', '.tree-toggle', function () {
            var $toggle = $(this);
            var $li = $toggle.closest('.tree-node');
            var $children = $li.children('.tree-children').first();

            if ($children.length === 0) return;

            if ($children.is(':visible')) {
                $children.slideUp(150);
                $toggle.text('\u25B6');
            } else {
                $children.slideDown(150);
                $toggle.text('\u25BC');
            }
        });
    }
});
