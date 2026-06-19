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
        if (!resp.success || !resp.tree || resp.tree.length === 0) {
            $sidebar.find('.sidebar-placeholder').html(
                '<div class="text-muted p-3 text-center">暂无项目文件夹</div>'
            );
            // 绑定常驻按钮 — 空树时也支持通过底部按钮打开模态框
            $('#btnCreate').off('click').on('click', function () {
                showCreateModal({ isRoot: true, folderId: null, folderName: null, hasAny: false });
            });
            updateCreateButtonLabel();
            return;
        }
        $sidebar.find('.sidebar-placeholder').remove();
        var $tree = buildTreeHtml(resp.tree);
        $sidebar.append($tree);
        bindTreeEvents($sidebar);

        // 绑定常驻按钮事件
        $('#btnCreate').off('click').on('click', function () {
            showCreateModal(getActiveFolderContext());
        });
        updateCreateButtonLabel();
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
                .attr('data-folder-id', node.id)
                .attr('data-project-id', node.project_id);
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

    // 绑定展开/收起 + 选中事件（合并到整行点击）
    function bindTreeEvents($container) {
        $container.off('click', '.tree-item');
        $container.on('click', '.tree-item', function (e) {
            var $item = $(this);
            var $node = $item.closest('.tree-node');
            var $children = $node.children('.tree-children').first();
            var $toggle = $item.find('.tree-toggle');

            // ── 展开/收起子文件夹（有子节点时）──
            if ($children.length > 0) {
                if ($children.is(':visible')) {
                    $children.slideUp(150);
                    $toggle.text('\u25B6');
                } else {
                    $children.slideDown(150);
                    $toggle.text('\u25BC');
                }
            }

            // ── 选中并触发 folder-selected ──
            var folderId = $node.data('folder-id');
            var folderName = $node.find('.tree-name').text();

            $container.find('.tree-node.active').removeClass('active');
            $node.addClass('active');

            $(document).trigger('folder-selected', {
                folderId: folderId,
                folderName: folderName,
            });
            updateCreateButtonLabel();
        });
    }

    // ── 获取当前选中文件夹上下文 ──
    function getActiveFolderContext() {
        var $active = $('.tree-node.active');
        if (!$active.length) {
            var $roots = $('.tree-node[data-is-root="true"]');
            if ($roots.length === 0) {
                return { isRoot: true, folderId: null, folderName: null, hasAny: false };
            }
            return {
                isRoot: true,
                folderId: $roots.first().data('folder-id'),
                folderName: $roots.first().find('.tree-name').text(),
                hasAny: true,
            };
        }
        return {
            isRoot: !!$active.data('is-root'),
            folderId: $active.data('folder-id'),
            folderName: $active.find('.tree-name').text(),
            hasAny: true,
        };
    }

    // ── 根据选中上下文更新按钮文案 ──
    function updateCreateButtonLabel() {
        var ctx = getActiveFolderContext();
        var $btn = $('#btnCreate');
        if (!ctx.hasAny) {
            $btn.text('\uD83D\uDCC1 \u65B0\u589E\u9879\u76EE');
        } else {
            $btn.text('\uD83D\uDCC1 \u65B0\u589E\u6587\u4EF6\u5939');
        }
    }

    // ── 统一新建模态框（项目 / 文件夹 分段按钮切换）──
    function showCreateModal(ctx) {
        $('#createModal').remove();

        var defaultTab = (!ctx.hasAny) ? 'project' : 'folder';
        var parentId = (!ctx.isRoot && ctx.hasAny) ? ctx.folderId : null;
        var parentName = (!ctx.isRoot && ctx.hasAny) ? ctx.folderName : null;

        if (defaultTab === 'folder' && !parentId) {
            defaultTab = 'project';
        }

        var html =
            '<div class="modal fade" id="createModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header">' +
            '<h5 class="modal-title">\uD83D\uDCC1 \u65B0\u5EFA</h5>' +
            '<button type="button" class="close" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="create-mode-toggle mb-3">' +
            '<button type="button" class="btn btn-toggle' + (defaultTab === 'project' ? ' active' : '') + '" ' +
            'id="btnToggleProject" data-mode="project">\uD83D\uDCC1 \u65B0\u589E\u9879\u76EE</button>' +
            '<button type="button" class="btn btn-toggle' + (defaultTab === 'folder' ? ' active' : '') + '" ' +
            'id="btnToggleFolder" data-mode="folder">\uD83D\uDCC2 \u65B0\u589E\u6587\u4EF6\u5939</button>' +
            '</div>' +
            '<div id="paneProject" style="display:' + (defaultTab === 'project' ? 'block' : 'none') + ';">' +
            '<div class="form-group">' +
            '<label>\u9879\u76EE\u578B\u53F7 <small class="text-muted">(\u82F1\u6587+\u6570\u5B57\uFF0C\u6700\u591A 20 \u5B57\u7B26)</small></label>' +
            '<input type="text" class="form-control" id="inputProjectModel" ' +
            'placeholder="\u4F8B\u5982\uFF1APRJ001" maxlength="20">' +
            '<div class="invalid-feedback" id="feedbackProjectModel"></div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>\u9879\u76EE\u540D\u79F0 <small class="text-muted">(\u6700\u591A 30 \u5B57\u7B26)</small></label>' +
            '<input type="text" class="form-control" id="inputProjectName" ' +
            'placeholder="\u4F8B\u5982\uFF1A\u67D0\u7814\u53D1\u9879\u76EE" maxlength="30">' +
            '<div class="invalid-feedback" id="feedbackProjectName"></div>' +
            '</div>' +
            '</div>' +
            '<div id="paneFolder" style="display:' + (defaultTab === 'folder' ? 'block' : 'none') + ';">' +
            '<div class="form-group">' +
            '<label>\u6587\u4EF6\u5939\u540D\u79F0</label>' +
            '<input type="text" class="form-control" id="inputFolderName" ' +
            'placeholder="\u8F93\u5165\u6587\u4EF6\u5939\u540D\u79F0\uFF0C\u6700\u591A 32 \u4E2A\u5B57\u7B26" maxlength="32">' +
            '<div class="invalid-feedback" id="feedbackFolderName"></div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>\u7236\u6587\u4EF6\u5939</label>' +
            '<div id="selectedParentDisplay"></div>' +
            '<div id="parentFolderPicker" style="display:none; max-height:200px; overflow-y:auto;" ' +
            'class="border rounded p-2 bg-white"></div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">\u53D6\u6D88</button>' +
            '<button type="button" class="btn btn-primary btn-sm" id="btnConfirmCreate">\u521B\u5EFA</button>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        $('body').append(html);
        var $modal = $('#createModal');
        var currentTab = defaultTab;
        var selectedParentId = parentId;

        function renderParentDisplay() {
            var $display = $('#selectedParentDisplay');
            var $picker = $('#parentFolderPicker');

            if (selectedParentId) {
                var name = parentName;
                var $match = $('.tree-node[data-folder-id="' + selectedParentId + '"]');
                if ($match.length) {
                    name = $match.find('.tree-name').text();
                }
                $display.html(
                    '<span class="text-success">\u2714 \u5F53\u524D\u4F4D\u7F6E\uFF1A' + name + '</span> ' +
                    '<button class="btn btn-link btn-sm p-0 ml-2" id="btnChangeParent">\u66F4\u6539</button>'
                );
                $picker.hide();
            } else {
                $display.html(
                    '<span class="text-muted">\u8BF7\u9009\u62E9\u7236\u6587\u4EF6\u5939</span>'
                );
                loadParentPicker();
                $picker.show();
            }
        }

        function loadParentPicker() {
            var $picker = $('#parentFolderPicker');
            $.ajax({
                url: '/api/folders/tree',
                method: 'GET',
                dataType: 'json',
            }).done(function (resp) {
                if (!resp.success || !resp.tree || resp.tree.length === 0) {
                    $picker.html('<div class="text-muted small">\u6682\u65E0\u53EF\u7528\u6587\u4EF6\u5939</div>');
                    return;
                }
                var flat = flattenTree(resp.tree);
                var listHtml = '';
                $.each(flat, function (i, f) {
                    var indent = '&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(f.depth);
                    var icon = f.is_project_root ? '\uD83D\uDCC1' : '\uD83D\uDCC2';
                    listHtml += '<a href="#" class="d-block small py-1 parent-picker-item ' +
                        (f.id === selectedParentId ? 'font-weight-bold text-primary' : 'text-dark') + '" ' +
                        'data-parent-id="' + f.id + '" data-parent-name="' + f.name + '">' +
                        indent + icon + ' ' + f.name + '</a>';
                });
                $picker.html(listHtml);
            });
        }

        function flattenTree(nodes, depth) {
            depth = depth || 0;
            var flat = [];
            $.each(nodes, function (i, node) {
                flat.push({
                    id: node.id,
                    name: node.name,
                    project_id: node.project_id,
                    is_project_root: node.is_project_root,
                    depth: depth,
                });
                if (node.children && node.children.length > 0) {
                    flat = flat.concat(flattenTree(node.children, depth + 1));
                }
            });
            return flat;
        }

        renderParentDisplay();

        $modal.on('click', '#btnChangeParent', function () {
            selectedParentId = null;
            renderParentDisplay();
        });

        $modal.on('click', '.parent-picker-item', function (e) {
            e.preventDefault();
            selectedParentId = $(this).data('parent-id');
            parentName = $(this).data('parent-name');
            renderParentDisplay();
        });

        $modal.on('click', '.btn-toggle', function () {
            var mode = $(this).data('mode');
            currentTab = mode;
            $modal.find('.btn-toggle').removeClass('active');
            $(this).addClass('active');
            if (mode === 'project') {
                $('#paneProject').show();
                $('#paneFolder').hide();
            } else {
                $('#paneProject').hide();
                $('#paneFolder').show();
                if (!selectedParentId) {
                    renderParentDisplay();
                }
            }
        });

        $('#btnConfirmCreate').on('click', function () {
            if (currentTab === 'project') {
                var model = $('#inputProjectModel').val().trim().toUpperCase();
                var name = $('#inputProjectName').val().trim();
                var hasError = false;

                if (!model) {
                    $('#inputProjectModel').addClass('is-invalid');
                    $('#feedbackProjectModel').text('\u9879\u76EE\u578B\u53F7\u4E0D\u80FD\u4E3A\u7A7A');
                    hasError = true;
                } else {
                    $('#inputProjectModel').removeClass('is-invalid');
                }
                if (!name) {
                    $('#inputProjectName').addClass('is-invalid');
                    $('#feedbackProjectName').text('\u9879\u76EE\u540D\u79F0\u4E0D\u80FD\u4E3A\u7A7A');
                    hasError = true;
                } else {
                    $('#inputProjectName').removeClass('is-invalid');
                }
                if (hasError) return;

                var csrfToken = $('meta[name="csrf-token"]').attr('content') || '';
                $.ajax({
                    url: '/api/projects',
                    method: 'POST',
                    contentType: 'application/json',
                    headers: { 'X-CSRF-Token': csrfToken },
                    data: JSON.stringify({ model: model, name: name }),
                })
                .done(function (resp) {
                    if (!resp.success) {
                        var errs = resp.errors || {};
                        if (errs.model) {
                            $('#inputProjectModel').addClass('is-invalid');
                            $('#feedbackProjectModel').text(errs.model[0]);
                        }
                        if (errs.name) {
                            $('#inputProjectName').addClass('is-invalid');
                            $('#feedbackProjectName').text(errs.name[0]);
                        }
                        return;
                    }
                    $modal.modal('hide');
                    location.reload();
                })
                .fail(function () {
                    alert('\u521B\u5EFA\u5931\u8D25\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5');
                });

            } else {
                var folderName = $('#inputFolderName').val().trim();
                if (!folderName) {
                    $('#inputFolderName').addClass('is-invalid');
                    $('#feedbackFolderName').text('\u6587\u4EF6\u5939\u540D\u79F0\u4E0D\u80FD\u4E3A\u7A7A');
                    return;
                }
                $('#inputFolderName').removeClass('is-invalid');

                if (!selectedParentId) {
                    selectedParentId = $('.tree-node[data-is-root="true"]').first().data('folder-id');
                }
                if (!selectedParentId) {
                    alert('\u672A\u627E\u5230\u53EF\u7528\u7684\u7236\u6587\u4EF6\u5939');
                    return;
                }

                var csrfToken2 = $('meta[name="csrf-token"]').attr('content') || '';
                $.ajax({
                    url: '/api/folders',
                    method: 'POST',
                    contentType: 'application/json',
                    headers: { 'X-CSRF-Token': csrfToken2 },
                    data: JSON.stringify({ name: folderName, parent_id: selectedParentId }),
                })
                .done(function (resp) {
                    if (!resp.success) {
                        var errs = resp.errors || {};
                        var msg = Object.values(errs).flat().join('; ');
                        $('#inputFolderName').addClass('is-invalid');
                        $('#feedbackFolderName').text(msg);
                        return;
                    }
                    $modal.modal('hide');
                    $.ajax({
                        url: '/api/folders/tree',
                        method: 'GET',
                        dataType: 'json',
                    }).done(function (treeResp) {
                        $('.sidebar .folder-tree').remove();
                        if (treeResp.success && treeResp.tree) {
                            var $tree = buildTreeHtml(treeResp.tree);
                            $('.sidebar').append($tree);
                            bindTreeEvents($('.sidebar'));
                            $('#btnCreate').off('click').on('click', function () {
                                showCreateModal(getActiveFolderContext());
                            });
                            updateCreateButtonLabel();
                        }
                    });
                })
                .fail(function () {
                    alert('\u521B\u5EFA\u5931\u8D25\uFF0C\u8BF7\u5237\u65B0\u9875\u9762\u540E\u91CD\u8BD5');
                });
            }
        });

        $modal.on('hidden.bs.modal', function () {
            $modal.remove();
        });
        $modal.modal('show');
    }
});
