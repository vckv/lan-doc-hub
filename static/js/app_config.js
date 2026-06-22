/**
 * LAN Doc Hub — 全局应用配置
 * 所有硬编码常量集中管理，业务模块从此处引用。
 */
window.LanDocHub = window.LanDocHub || {};

LanDocHub.CONFIG = {
    // ── 上传限制 ──
    MAX_FILE_SIZE_MB: 500,
    MAX_FILE_SIZE_BYTES: 500 * 1024 * 1024,
    ACCEPTED_FILE_TYPES: '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.jpg,.jpeg,.png,.gif,.bmp,.webp',

    // ── 输入长度限制 ──
    FOLDER_NAME_MAX_LENGTH: 32,
    PROJECT_MODEL_MAX_LENGTH: 20,
    PROJECT_NAME_MAX_LENGTH: 30,
};

LanDocHub.ICONS = {
    FOLDER_OPEN:   '\u{1F4C2}',
    FOLDER_CLOSED: '\u{1F4C1}',
    FILE_EMPTY:    '\u{1F4C4}',
    UPLOAD:        '\u{1F4E4}',
    LINK:          '\u{1F517}',
    PAGE:          '\u{1F4D6}',
    SEARCH:        '\u{1F50D}',
    CHECK:         '\u2714',
    WARNING:       '\u26A0',
    ARROW_RIGHT:   '\u25B6',
    ARROW_DOWN:    '\u25BC',
    DOT:           '\u00B7',
};
