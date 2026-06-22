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
        $tree.insertBefore($sidebar.find('.sidebar-footer'));
        bindTreeEvents($sidebar);

        // 绑定常驻按钮事件
        $('#btnCreate').off('click').on('click', function () {
            showCreateModal(getActiveFolderContext());
        });
        updateCreateButtonLabel();

        // ── 恢复进入历史页面前的文件夹选中状态 ──
        var urlParams = new URLSearchParams(window.location.search);
        var restoreFolderId = parseInt(urlParams.get('folder'));
        var highlightFileId = parseInt(urlParams.get('highlight')) || null;

        // URL 无文件夹参数时，尝试从 sessionStorage 恢复（刷新场景）
        if (!restoreFolderId) {
            var saved = sessionStorage.getItem('lanhub_active_folder');
            if (saved) restoreFolderId = parseInt(saved);
        }

        if (restoreFolderId) {
            var $targetNode = $sidebar.find('.tree-node[data-folder-id="' + restoreFolderId + '"]');
            if ($targetNode.length) {
                $targetNode.addClass('active');
                var folderName = $targetNode.find('.tree-label').text().trim();
                $(document).trigger('folder-selected', {
                    folderId: restoreFolderId,
                    folderName: folderName,
                    highlightFileId: highlightFileId,
                });
            }
        }
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
            var toggleIcon = hasChildren ? LanDocHub.ICONS.ARROW_RIGHT : LanDocHub.ICONS.DOT;
            var folderIcon = node.is_project_root ? LanDocHub.ICONS.FOLDER_CLOSED : LanDocHub.ICONS.FOLDER_OPEN;

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
                    $toggle.text(LanDocHub.ICONS.ARROW_RIGHT);
                } else {
                    $children.slideDown(150);
                    $toggle.text(LanDocHub.ICONS.ARROW_DOWN);
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
            $btn.text('\uD83D\uDCC1 新增项目');
        } else {
            $btn.text('\uD83D\uDCC1 新增文件夹');
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
            '<div class="modal-dialog" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header">' +
            '<h5 class="modal-title">\uD83D\uDCC1 新建</h5>' +
            '<button type="button" class="close" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="create-mode-toggle mb-3">' +
            '<button type="button" class="btn btn-toggle' + (defaultTab === 'project' ? ' active' : '') + '" ' +
            'id="btnToggleProject" data-mode="project">\uD83D\uDCC1 新增项目</button>' +
            '<button type="button" class="btn btn-toggle' + (defaultTab === 'folder' ? ' active' : '') + '" ' +
            'id="btnToggleFolder" data-mode="folder">\uD83D\uDCC2 新增文件夹</button>' +
            '</div>' +
            '<div id="paneProject" style="display:' + (defaultTab === 'project' ? 'block' : 'none') + ';">' +
            '<div class="form-group">' +
            '<label>项目型号 <small class="text-muted">(英文+数字，最多 20 字符)</small></label>' +
            '<input type="text" class="form-control" id="inputProjectModel" ' +
            'placeholder="例如：PRJ001" maxlength="20">' +
            '<div class="invalid-feedback" id="feedbackProjectModel"></div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>项目名称 <small class="text-muted">(最多 30 字符)</small></label>' +
            '<input type="text" class="form-control" id="inputProjectName" ' +
            'placeholder="例如：某研发项目" maxlength="30">' +
            '<div class="invalid-feedback" id="feedbackProjectName"></div>' +
            '</div>' +
            '</div>' +
            '<div id="paneFolder" style="display:' + (defaultTab === 'folder' ? 'block' : 'none') + ';">' +
            '<div class="form-group">' +
            '<label>文件夹名称</label>' +
            '<input type="text" class="form-control" id="inputFolderName" ' +
            'placeholder="输入文件夹名称，最多 32 个字符" maxlength="32">' +
            '<div class="invalid-feedback" id="feedbackFolderName"></div>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>父文件夹</label>' +
            '<div id="selectedParentDisplay"></div>' +
            '<div id="parentFolderPicker" style="display:none; max-height:200px; overflow-y:auto;" ' +
            'class="border rounded p-2 bg-white"></div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" data-dismiss="modal">取消</button>' +
            '<button type="button" class="btn btn-primary btn-sm" id="btnConfirmCreate">创建</button>' +
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
                    '<span class="text-success">✔ 当前位置：' + name + '</span> ' +
                    '<button class="btn btn-link btn-sm p-0 ml-2" id="btnChangeParent">更改</button>'
                );
                $picker.hide();
            } else {
                $display.html(
                    '<span class="text-muted">请选择父文件夹</span>'
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
                    $picker.html('<div class="text-muted small">暂无可用文件夹</div>');
                    return;
                }
                var flat = LanDocHub.Utils.flattenTree(resp.tree);
                var listHtml = '';
                $.each(flat, function (i, f) {
                    var indent = '&nbsp;&nbsp;&nbsp;&nbsp;'.repeat(f.depth);
                    var icon = f.is_project_root ? LanDocHub.ICONS.FOLDER_CLOSED : LanDocHub.ICONS.FOLDER_OPEN;
                    listHtml += '<a href="#" class="d-block small py-1 parent-picker-item ' +
                        (f.id === selectedParentId ? 'font-weight-bold text-primary' : 'text-dark') + '" ' +
                        'data-parent-id="' + f.id + '" data-parent-name="' + f.name + '">' +
                        indent + icon + ' ' + f.name + '</a>';
                });
                $picker.html(listHtml);
            });
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
                    $('#feedbackProjectModel').text('项目型号不能为空');
                    hasError = true;
                } else {
                    $('#inputProjectModel').removeClass('is-invalid');
                }
                if (!name) {
                    $('#inputProjectName').addClass('is-invalid');
                    $('#feedbackProjectName').text('项目名称不能为空');
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
                    alert('创建失败，请刷新页面后重试');
                });

            } else {
                var folderName = $('#inputFolderName').val().trim();
                if (!folderName) {
                    $('#inputFolderName').addClass('is-invalid');
                    $('#feedbackFolderName').text('文件夹名称不能为空');
                    return;
                }
                $('#inputFolderName').removeClass('is-invalid');

                if (!selectedParentId) {
                    selectedParentId = $('.tree-node[data-is-root="true"]').first().data('folder-id');
                }
                if (!selectedParentId) {
                    alert('未找到可用的父文件夹');
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
                            $tree.insertBefore($('.sidebar .sidebar-footer'));
                            bindTreeEvents($('.sidebar'));
                            $('#btnCreate').off('click').on('click', function () {
                                showCreateModal(getActiveFolderContext());
                            });
                            updateCreateButtonLabel();
                        }
                    });
                })
                .fail(function () {
                    alert('创建失败，请刷新页面后重试');
                });
            }
        });

        $modal.on('hidden.bs.modal', function () {
            $modal.remove();
        });
        $modal.modal('show');
    }
});
