"""F4-1 测试：标签 CRUD、文件-标签关联、7 天权限控制"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Tag, FileTag, File, Folder, Project, User


@pytest.fixture
def app():
    """创建带临时数据库的应用实例"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-key')

    from app import create_app
    app = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'TESTING': True,
        'SETUP_KEY_FILE': key_path,
    })

    yield app

    with app.app_context():
        _db.session.remove()
        _db.engine.dispose()
    os.close(db_fd)
    os.close(key_fd)
    try:
        os.unlink(db_path)
    except PermissionError:
        pass
    try:
        os.unlink(key_path)
    except PermissionError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _api_headers(client):
    """生成带 CSRF Token 的 JSON 请求头"""
    with client.session_transaction() as sess:
        token = sess.get('csrf_token', '')
    return {'X-CSRF-Token': token, 'Content-Type': 'application/json'}


def _login_as(app, username, password, role):
    """创建用户并登录，返回已认证的 test_client"""
    with app.app_context():
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username=username,
            display_name=username.capitalize(),
            password_hash=pw_hash,
            role=role,
            is_active=True,
            created_ip='127.0.0.1',
        )
        _db.session.add(user)
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    resp = client.post('/login', data={
        'csrf_token': token,
        'username': username,
        'password': password,
    })
    return client


def _seed_projects_and_tags(app):
    """创建测试用的项目、根文件夹、两个标签"""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        proj = Project(model='F4TEST', name='测试项目')
        _db.session.add(proj)
        _db.session.flush()

        root = Folder(
            name='F4TEST_测试项目', is_project_root=True,
            project_id=proj.id, parent_id=None, created_by=admin.id,
        )
        _db.session.add(root)
        _db.session.flush()

        tag1 = Tag(name='紧急', color='#ff0000')
        tag2 = Tag(name='待审核', color='#ffaa00')
        _db.session.add_all([tag1, tag2])
        _db.session.commit()

        return {
            'project_id': proj.id,
            'folder_id': root.id,
            'tag_ids': [tag1.id, tag2.id],
        }


# ═══════════════════════════════════════════
# 标签 CRUD 测试
# ═══════════════════════════════════════════

class TestTagCRUD:

    def test_create_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '紧急', 'color': '#ff0000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['success']
        assert data['tag']['name'] == '紧急'
        assert data['tag']['color'] == '#ff0000'

    def test_create_duplicate_tag_returns_409(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        client.post('/api/tags', data=json.dumps({'name': '唯一', 'color': '#000'}), headers=hdrs)
        resp = client.post('/api/tags', data=json.dumps({'name': '唯一', 'color': '#000'}), headers=hdrs)
        assert resp.status_code == 409

    def test_create_tag_name_too_long(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': 'A' * 33, 'color': '#000000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 400

    def test_create_tag_invalid_color(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '测试', 'color': 'red'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 400

    def test_update_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        r = client.post('/api/tags', data=json.dumps({'name': '旧名', 'color': '#ff0000'}), headers=hdrs)
        tag_id = json.loads(r.data)['tag']['id']

        resp = client.put(
            f'/api/tags/{tag_id}',
            data=json.dumps({'name': '新名', 'color': '#00ff00'}),
            headers=hdrs,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['tag']['name'] == '新名'
        assert data['tag']['color'] == '#00ff00'

    def test_update_nonexistent_tag(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.put(
            '/api/tags/9999',
            data=json.dumps({'name': '新名'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 404

    def test_delete_tag_success(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        r = client.post('/api/tags', data=json.dumps({'name': '待删', 'color': '#000000'}), headers=hdrs)
        tag_id = json.loads(r.data)['tag']['id']

        resp = client.delete(f'/api/tags/{tag_id}', headers=hdrs)
        assert resp.status_code == 200

        resp_list = client.get('/api/tags')
        tags = json.loads(resp_list.data)['tags']
        assert all(t['id'] != tag_id for t in tags)

    def test_list_tags(self, app):
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        hdrs = _api_headers(client)
        client.post('/api/tags', data=json.dumps({'name': 'A标签', 'color': '#aaa'}), headers=hdrs)
        client.post('/api/tags', data=json.dumps({'name': 'B标签', 'color': '#bbb'}), headers=hdrs)

        resp = client.get('/api/tags')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['tags']) == 2

    def test_member_cannot_create_tag(self, app):
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        client = _login_as(app, 'member1', 'Member@Pass1', 'member')
        resp = client.post(
            '/api/tags',
            data=json.dumps({'name': '非法标签', 'color': '#ff0000'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════
# 文件-标签关联 + 7 天权限测试
# ═══════════════════════════════════════════

class TestFileTags:

    def test_member_can_set_own_file_tags(self, app):
        """上传者 7 天内可设置自己文件的标签"""
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='test.pdf', original_filename='test.pdf',
                file_path='2026/06/test.pdf', file_number='F-20260625-001',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=1024,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = member_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(member_client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['tags']) == 2

    def test_cannot_edit_others_file_tags(self, app):
        """不能编辑他人上传的文件标签"""
        admin_client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            f = File(
                filename='admin_doc.pdf', original_filename='admin_doc.pdf',
                file_path='2026/06/admin_doc.pdf', file_number='F-20260625-002',
                folder_id=info['folder_id'], uploader_id=admin.id,
                project_id=info['project_id'], file_type='PDF', file_size=2048,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = member_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(member_client),
        )
        assert resp.status_code == 403

    def test_get_file_tags_with_can_edit_flag(self, app):
        """获取文件标签时应返回 can_edit 和 reason"""
        _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        member_client = _login_as(app, 'member1', 'Member@Pass1', 'member')

        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='member_doc.pdf', original_filename='member_doc.pdf',
                file_path='2026/06/member_doc.pdf', file_number='F-20260625-003',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=2048,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = member_client.get(f'/api/tags/file/{file_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['can_edit'] is True
        assert data['tags'] == []

    def test_admin_can_edit_all_tags(self, app):
        """admin 可编辑任意文件的标签"""
        admin_client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        info = _seed_projects_and_tags(app)
        _login_as(app, 'member1', 'Member@Pass1', 'member')

        with app.app_context():
            member = User.query.filter_by(username='member1').first()
            f = File(
                filename='member_doc2.pdf', original_filename='member_doc2.pdf',
                file_path='2026/06/member_doc2.pdf', file_number='F-20260625-004',
                folder_id=info['folder_id'], uploader_id=member.id,
                project_id=info['project_id'], file_type='PDF', file_size=4096,
                is_current=True, version_number='I',
            )
            _db.session.add(f)
            _db.session.commit()
            file_id = f.id

        resp = admin_client.put(
            f'/api/tags/file/{file_id}',
            data=json.dumps({'tag_ids': info['tag_ids']}),
            headers=_api_headers(admin_client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['tags']) == 2
