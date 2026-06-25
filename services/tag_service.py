"""标签服务层 —— 标签 CRUD、文件标签关联、7 天可编辑权限"""
from datetime import datetime, timezone

from models import db, Tag, FileTag, File


def _now():
    """当前 UTC naive datetime"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── 标签 CRUD ──

def create_tag(name, color='#3b82f6'):
    """创建标签（仅 admin 调用）

    Args:
        name: 标签名（1-32 字符，不可重复）
        color: Hex 颜色（可选，默认 #3b82f6）

    Returns:
        {'success': bool, 'tag': dict|None, 'errors': dict}
    """
    errors = {}
    name = (name or '').strip()
    if not name:
        errors['name'] = ['标签名不能为空']
    elif len(name) > 32:
        errors['name'] = ['标签名最多 32 个字符']

    color = (color or '').strip() or '#3b82f6'
    if not color.startswith('#') or len(color) not in (4, 7):
        errors['color'] = ['颜色格式不正确，应为 #RRGGBB 或 #RGB']

    if errors:
        return {'success': False, 'tag': None, 'errors': errors}

    existing = Tag.query.filter_by(name=name).first()
    if existing:
        return {
            'success': False, 'tag': None,
            'errors': {'name': [f'标签 "{name}" 已存在']},
        }

    tag = Tag(name=name, color=color.lower())
    db.session.add(tag)
    db.session.commit()

    return {
        'success': True,
        'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color},
        'errors': {},
    }


def update_tag(tag_id, name=None, color=None):
    """编辑标签（仅 admin 调用）

    Args:
        tag_id: 标签 ID
        name: 新名称（可选，None 表示不修改）
        color: 新颜色（可选，None 表示不修改）

    Returns:
        {'success': bool, 'tag': dict|None, 'errors': dict}
    """
    errors = {}
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        return {'success': False, 'tag': None, 'errors': {'tag_id': ['标签不存在']}}

    if name is not None:
        name = name.strip()
        if not name:
            errors['name'] = ['标签名不能为空']
        elif len(name) > 32:
            errors['name'] = ['标签名最多 32 个字符']
        else:
            dup = Tag.query.filter(Tag.name == name, Tag.id != tag_id).first()
            if dup:
                errors['name'] = [f'标签 "{name}" 已存在']

    if color is not None:
        color = color.strip()
        if not color.startswith('#') or len(color) not in (4, 7):
            errors['color'] = ['颜色格式不正确，应为 #RRGGBB 或 #RGB']

    if errors:
        return {'success': False, 'tag': None, 'errors': errors}

    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color.lower()
    db.session.commit()

    return {
        'success': True,
        'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color},
        'errors': {},
    }


def delete_tag(tag_id):
    """删除标签，同时清理 file_tags 关联（仅 admin 调用）

    Args:
        tag_id: 标签 ID

    Returns:
        {'success': bool, 'errors': dict}
    """
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        return {'success': False, 'errors': {'tag_id': ['标签不存在']}}

    FileTag.query.filter_by(tag_id=tag_id).delete()
    db.session.delete(tag)
    db.session.commit()

    return {'success': True, 'errors': {}}


def get_all_tags():
    """获取所有标签列表（所有登录用户可调用）

    Returns:
        list[dict]: [{id, name, color}, ...]
    """
    tags = Tag.query.order_by(Tag.name).all()
    return [{'id': t.id, 'name': t.name, 'color': t.color} for t in tags]


# ── 文件-标签关联 ──

def set_file_tags(file_id, user_id, tag_ids, user_role='member'):
    """设置文件的标签（替换式：先清空再重新写入）

    权限规则：
    - admin 可编辑所有文件的标签
    - 普通成员只能编辑自己上传 + 7 天内的标签

    Args:
        file_id:   文件 ID
        user_id:   操作用户 ID
        tag_ids:   标签 ID 列表（空列表 = 清空所有标签）
        user_role: 用户角色（'admin' 或 'member'）

    Returns:
        {'success': bool, 'tags': list|None, 'errors': dict}
    """
    errors = {}
    f = db.session.get(File, file_id)
    if f is None:
        return {'success': False, 'tags': None, 'errors': {'file_id': ['文件不存在']}}

    # ── 权限校验 ──
    if user_role != 'admin':
        if f.uploader_id != user_id:
            errors['permission'] = ['只能编辑自己上传的文件']
        else:
            delta = _now() - f.created_at
            if delta.days > 7:
                errors['permission'] = ['上传超过 7 天的文件不可修改标签']

    if errors:
        return {'success': False, 'tags': None, 'errors': errors}

    # ── 校验 tag_ids 均存在 ──
    if tag_ids:
        existing_ids = {t.id for t in Tag.query.filter(Tag.id.in_(tag_ids)).all()}
        invalid = set(tag_ids) - existing_ids
        if invalid:
            return {
                'success': False, 'tags': None,
                'errors': {'tag_ids': [f'标签 ID 不存在: {", ".join(map(str, invalid))}']},
            }

    # ── 替换式写入 ──
    FileTag.query.filter_by(file_id=file_id).delete()
    for tid in tag_ids:
        db.session.add(FileTag(file_id=file_id, tag_id=tid))
    db.session.commit()

    # 返回更新后的标签列表
    f_updated = db.session.get(File, file_id)
    tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in f_updated.tags]
    return {'success': True, 'tags': tags, 'errors': {}}


def get_file_tags(file_id):
    """获取某文件的标签列表

    Returns:
        list[dict]: [{id, name, color}, ...]
    """
    f = db.session.get(File, file_id)
    if f is None:
        return []
    return [{'id': t.id, 'name': t.name, 'color': t.color} for t in f.tags]


def can_edit_file_tags(file_id, user_id, user_role='member'):
    """判断用户是否有权编辑某文件的标签

    Returns:
        {'can_edit': bool, 'reason': str|None}
    """
    if user_role == 'admin':
        return {'can_edit': True, 'reason': None}

    f = db.session.get(File, file_id)
    if f is None:
        return {'can_edit': False, 'reason': '文件不存在'}
    if f.uploader_id != user_id:
        return {'can_edit': False, 'reason': '只能编辑自己上传的文件'}
    delta = _now() - f.created_at
    if delta.days > 7:
        return {'can_edit': False, 'reason': '上传超过 7 天的文件不可修改标签'}
    return {'can_edit': True, 'reason': None}
