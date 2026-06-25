/**
 * F4-2 自定义 Autocomplete 组件
 *
 * 用法：
 *   $('#myInput').lanAutocomplete({
 *       source: function (query, done) { ... },  // 异步数据源
 *       onSelect: function (item) { ... },        // 选中回调
 *       renderItem: function (item, query) { ... },// 可选：自定义渲染
 *       minLength: 1,                             // 最少输入字符数触发搜索
 *       placeholder: '请输入...',                 // placeholder
 *       onCreateNew: function (query, done) { ... },// 可选：创建新项目回调
 *       createLabel: '创建新项目',                 // 可选：底部创建入口文案
 *   });
 */
$(function () {
    'use strict';

    var pluginName = 'lanAutocomplete';
    var $doc = $(document);

    function Autocomplete(element, options) {
        this.$input = $(element);
        this.options = $.extend({}, Autocomplete.defaults, options);
        this._init();
    }

    Autocomplete.defaults = {
        source: null,           // function(query, done) — 返回 [{id, display, ...}]
        onSelect: null,         // function(item) — 选中回调
        renderItem: null,       // function(item, query) → html string
        minLength: 1,
        debounceMs: 200,
        placeholder: '',
        createLabel: null,      // 底部"创建新项目"入口文案
        onCreateNew: null,      // function(query, done) — 创建新项目回调
    };

    Autocomplete.prototype._init = function () {
        var self = this;

        // 包裹 input
        if (!this.$input.parent().hasClass('ac-input-wrapper')) {
            this.$input.wrap('<div class="ac-input-wrapper"></div>');
            this.$input.attr('autocomplete', 'off');
            if (this.options.placeholder) {
                this.$input.attr('placeholder', this.options.placeholder);
            }
        }
        this.$wrapper = this.$input.parent();

        // 创建下拉容器
        this.$dropdown = $('<div class="autocomplete-suggestions"></div>');
        this.$wrapper.append(this.$dropdown);

        // 防抖输入事件
        var debounceTimer = null;
        this.$input.on('input', function () {
            clearTimeout(debounceTimer);
            var q = self.$input.val().trim();
            if (q.length < self.options.minLength) {
                self._hide();
                return;
            }
            debounceTimer = setTimeout(function () {
                self._search(q);
            }, self.options.debounceMs);
        });

        // 键盘导航
        this.$input.on('keydown', function (e) {
            var $items = self.$dropdown.find('.autocomplete-item:not(.ac-create)');
            if (!$items.length) return;

            var $active = self.$dropdown.find('.autocomplete-item.active');

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!$active.length) {
                    $items.first().addClass('active');
                } else {
                    var next = $active.next('.autocomplete-item:not(.ac-create)');
                    $active.removeClass('active');
                    if (next.length) next.addClass('active');
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if ($active.length) {
                    var prev = $active.prev('.autocomplete-item:not(.ac-create)');
                    $active.removeClass('active');
                    if (prev.length) prev.addClass('active');
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if ($active.length) {
                    self._select($active);
                }
            } else if (e.key === 'Escape') {
                self._hide();
            }
        });

        // 点击选中
        this.$dropdown.on('click', '.autocomplete-item', function () {
            self._select($(this));
        });

        // 点击外部关闭
        $doc.on('click.autocomplete', function (e) {
            if (!self.$wrapper.is(e.target) && self.$wrapper.has(e.target).length === 0) {
                self._hide();
            }
        });
    };

    Autocomplete.prototype._search = function (query) {
        var self = this;
        this.options.source(query, function (items) {
            self._render(query, items);
        });
    };

    Autocomplete.prototype._render = function (query, items) {
        if (!items || items.length === 0) {
            this._hide();
            return;
        }

        var self = this;
        var renderFn = this.options.renderItem || function (item, q) {
            var highlight = function (text) {
                if (!q) return LanDocHub.Utils.escapeHtml(text);
                var re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                return LanDocHub.Utils.escapeHtml(text).replace(re, '<span class="ac-highlight">$1</span>');
            };
            return '<span class="ac-display">' +
                '<span class="ac-model">' + highlight(item.model) + '</span>' +
                '<span class="ac-separator">-</span>' +
                '<span class="ac-name">' + highlight(item.name) + '</span>' +
                '</span>';
        };

        var html = '';
        $.each(items, function (_i, item) {
            html += '<div class="autocomplete-item" data-value="' + item.id + '" data-display="' + LanDocHub.Utils.escapeHtml(item.display || '') + '">' +
                renderFn(item, query) + '</div>';
        });

        // 底部"创建新项目"入口
        if (this.options.createLabel && this.options.onCreateNew) {
            html += '<div class="autocomplete-item ac-create" data-action="create">' +
                '+ ' + this.options.createLabel + '</div>';
        }

        this.$dropdown.html(html).show();
    };

    Autocomplete.prototype._select = function ($item) {
        var action = $item.data('action');
        if (action === 'create') {
            this._hide();
            if (this.options.onCreateNew) {
                var currentQuery = this.$input.val().trim();
                var self = this;
                this.options.onCreateNew(currentQuery, function (newProject) {
                    if (newProject && self.options.onSelect) {
                        self.options.onSelect(newProject);
                    }
                });
            }
            return;
        }

        var item = {
            id: $item.data('value'),
            display: $item.data('display'),
        };
        this.$input.val(item.display || '');
        this._hide();
        if (this.options.onSelect) {
            this.options.onSelect(item);
        }
    };

    Autocomplete.prototype._hide = function () {
        this.$dropdown.empty().hide();
    };

    Autocomplete.prototype.destroy = function () {
        this.$input.off();
        this.$dropdown.remove();
        this.$input.unwrap();
        $doc.off('click.autocomplete');
    };

    // jQuery 插件注册
    $.fn[pluginName] = function (options) {
        return this.each(function () {
            var $this = $(this);
            var instance = $this.data(pluginName);
            if (instance) {
                instance.destroy();
            }
            $this.data(pluginName, new Autocomplete(this, options));
        });
    };
});
