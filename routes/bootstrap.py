"""首次初始化引导端点 —— 创建首个管理员账号（需 setup 密钥）"""

import traceback

from flask import Blueprint, render_template, request, abort

from models import User
from services.user_service import create_user

bootstrap_bp = Blueprint('bootstrap', __name__)


def _get_setup_key():
    """读取 .setup_key 文件中的密钥（去首尾空白）"""
    try:
        from flask import current_app
        key_file = current_app.config.get('SETUP_KEY_FILE', '')
        if key_file:
            with open(key_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''


@bootstrap_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """首次初始化引导页 —— 仅在 User 表为空时可访问"""
    if User.query.first() is not None:
        abort(404)

    if request.method == 'POST':
        setup_key = request.form.get('setup_key', '').strip()
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # ── 构建非敏感字段回传（密码不清空，仅不传回模板）
        form_data = {
            'setup_key': setup_key,
            'username': username,
            'display_name': display_name,
        }

        # ── 密钥校验 ──
        expected_key = _get_setup_key()
        if not setup_key or setup_key != expected_key:
            form_data['setup_key'] = ''  # 错误的密钥不回传
            return render_template('setup.html',
                                   error='密钥错误，请查看控制台输出的 setup 密钥后重试',
                                   **form_data)

        # ── 前端二次确认密码一致性 ──
        if password != password_confirm:
            return render_template('setup.html',
                                   error='两次输入的密码不一致，请重新输入',
                                   **form_data)

        try:
            result = create_user(
                username=username,
                display_name=display_name,
                password=password,
                role='admin',
                created_by_id=None,
                created_ip=request.remote_addr or '127.0.0.1',
            )
        except Exception as exc:
            from flask import current_app
            current_app.logger.error(
                'create_user 异常 — %s: %s\n%s',
                type(exc).__name__, str(exc), traceback.format_exc()
            )
            return render_template(
                'setup.html',
                error=f'系统错误：{type(exc).__name__} — {exc}。请查看控制台获取详细信息。',
                username=username,
                display_name=display_name,
            )

        if result['success']:
            return render_template('setup.html',
                                   success='管理员账号创建成功！',
                                   setup_username=username)

        # ── 取第一个非空错误信息 ──
        error = ''
        for field_msgs in result['errors'].values():
            if field_msgs:
                error = field_msgs[0]
                break
        return render_template('setup.html', error=error, **form_data)

    return render_template('setup.html')
