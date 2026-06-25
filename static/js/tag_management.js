/**
 * F4-1 标签管理 —— admin 端标签 CRUD 弹窗
 */
$(function () {
    'use strict';

    var $btnTagManage = $('#btnTagManage');
    if (!$btnTagManage.length) return;

    $btnTagManage.on('click', function () {
        openTagManagementModal();
    });

    function openTagManagementModal() {
        $('#tagManagementModal').remove();

        var html =
            '<div class="modal fade" id="tagManagementModal" tabindex="-1" role="dialog">' +
            '<div class="modal-dialog modal-dialog-centered" role="document">' +
            '<div class="modal-content">' +
            '<div class="modal-header bg-primary text-white">' +
            '<h5 class="modal-title">🏷️ 标签管理</h5>' +
            '<button type="button" class="close text-white" data-dismiss="modal">&times;</button>' +
            '</div>' +
            '<div class="modal-body">' +
            '<div class="form-row mb-3">' +
            '<div class="col-6">' +
            '<input type="text" class="form-control form-control-sm" id="inputNewTagName" ' +
            'placeholder="新标签名，最多 32 字" maxlength="32">' +
            '</div>' +
            '<div class="col-3">' +
            '<input type="color" class="form-control form-control-sm" id="inputNewTagColor" ' +
            'value="#3b82f6" style="height:31px;padding:2px;">' +
            '</div>' +
            '<div class="col-3">' +
            '<button class="btn btn-success btn-sm btn-block" id="btnCreateTag">创建</button>' +
            '</div>' +
            '</div>' +
            '<div class="tag-mgmt-list" id="tagMgmtList">' +
            '<div class="text-center text-muted py-2 small">加载中...</div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>' +
            '</div>';

        $('body').append(html);
        var $modal = $('#tagManagementModal');
        $modal.modal('show');
        $modal.on('hidden.bs.modal', function () { $modal.remove(); });

        loadTagMgmtList();

        // 创建标签
        $('#btnCreateTag').on('click', function () {
            var name = $('#inputNewTagName').val().trim();
            var color = $('#inputNewTagColor').val().trim() || '#3b82f6';
            if (!name) { alert('请输入标签名'); return; }

            $.ajax({
                url: '/api/tags',
                method: 'POST',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
                data: JSON.stringify({ name: name, color: color }),
            }).done(function (resp) {
                if (resp.success) {
                    $('#inputNewTagName').val('');
                    $('#inputNewTagColor').val('#3b82f6');
                    loadTagMgmtList();
                } else {
                    var msg = Object.values(resp.errors || {}).flat().join('; ');
                    alert(msg || '创建失败');
                }
            }).fail(function () {
                alert('创建失败，请重试');
            });
        });

        // ── 编辑标签 ──
        $('#tagMgmtList').on('click', '.btn-edit-tag', function () {
            var $item = $(this).closest('.tag-mgmt-item');
            var tagId = $item.data('tag-id');
            var currentName = $item.data('tag-name');
            var currentColor = $item.data('tag-color');

            var newName = prompt('编辑标签名（留空不修改）：', currentName);
            if (newName === null) return;

            var payload = {};
            if (newName.trim() && newName.trim() !== currentName) {
                payload.name = newName.trim();
            }

            var newColor = prompt('编辑颜色（如 #ff0000，留空不修改）：', currentColor);
            if (newColor !== null && newColor.trim() && newColor.trim() !== currentColor) {
                payload.color = newColor.trim();
            }

            if ($.isEmptyObject(payload)) return;

            $.ajax({
                url: '/api/tags/' + tagId,
                method: 'PUT',
                contentType: 'application/json',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
                data: JSON.stringify(payload),
            }).done(function (resp) {
                if (resp.success) {
                    loadTagMgmtList();
                } else {
                    var msg = Object.values(resp.errors || {}).flat().join('; ');
                    alert(msg || '编辑失败');
                }
            }).fail(function () {
                alert('编辑失败，请重试');
            });
        });

        // ── 删除标签 ──
        $('#tagMgmtList').on('click', '.btn-delete-tag', function () {
            var $item = $(this).closest('.tag-mgmt-item');
            var tagId = $item.data('tag-id');
            var tagName = $item.data('tag-name');
            if (!confirm('确定删除标签 "' + tagName + '"？\n删除后所有文件上该标签将被移除。')) return;

            $.ajax({
                url: '/api/tags/' + tagId,
                method: 'DELETE',
                headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
            }).done(function (resp) {
                if (resp.success) {
                    loadTagMgmtList();
                } else {
                    alert('删除失败');
                }
            }).fail(function () {
                alert('删除失败，请重试');
            });
        });
    }

    function loadTagMgmtList() {
        $.ajax({
            url: '/api/tags',
            method: 'GET',
            headers: { 'X-CSRF-Token': LanDocHub.Utils.getCsrfToken() },
            dataType: 'json',
        }).done(function (resp) {
            var $container = $('#tagMgmtList');
            if (!resp.success || !resp.tags) {
                $container.html('<div class="text-center text-muted py-3">加载失败</div>');
                return;
            }
            if (resp.tags.length === 0) {
                $container.html('<div class="text-center text-muted py-3">暂无标签，请在上方创建</div>');
                return;
            }
            var rows = $.map(resp.tags, function (tag) {
                var escName = LanDocHub.Utils.escapeHtml(tag.name);
                var escColor = LanDocHub.Utils.escapeHtml(tag.color);
                return '<div class="tag-mgmt-item" data-tag-id="' + tag.id +
                    '" data-tag-name="' + escName +
                    '" data-tag-color="' + escColor + '">' +
                    '<span class="tag-mgmt-info">' +
                    '<span class="tag-badge" style="background:' + escColor + '20;color:' + escColor + ';border:1px solid ' + escColor + '40;">' +
                    '<span class="tag-dot" style="background:' + escColor + ';"></span>' +
                    escName + '</span>' +
                    '<code class="small text-muted">' + escColor + '</code>' +
                    '</span>' +
                    '<span class="tag-mgmt-actions">' +
                    '<button class="btn btn-outline-secondary btn-sm btn-edit-tag">编辑</button>' +
                    '<button class="btn btn-outline-danger btn-sm btn-delete-tag">删除</button>' +
                    '</span>' +
                    '</div>';
            });
            $container.html(rows.join(''));
        });
    }
});
