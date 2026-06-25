"""F5-2: 历史版本面板 测试"""

import io
import json
import os
import tempfile

import pytest
import bcrypt

from models import db as _db, File, FileVersion, Folder, Project, User


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


def _get_csrf(client):
    """从 session 中提取 CSRF Token"""
    with client.session_transaction() as sess:
        return sess.get('csrf_token', '')


def _upload_file(client, content, filename, proj_id, folder_id, **extra):
    """上传文件辅助函数"""
    data = {
        'file': (io.BytesIO(content), filename),
        'project_id': str(proj_id),
        'folder_id': str(folder_id),
        'csrf_token': _get_csrf(client),
    }
    data.update(extra)
    return client.post('/api/files/upload', data=data)


def _seed_project_and_folder(app, project_model='F5T2', project_name='测试项目'):
    """创建测试用的项目和根文件夹"""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        proj = Project(model=project_model, name=project_name)
        _db.session.add(proj)
        _db.session.flush()

        root = Folder(
            name=f'{project_model}_{project_name}',
            is_project_root=True,
            project_id=proj.id,
            parent_id=None,
            created_by=admin.id if admin else 1,
        )
        _db.session.add(root)
        _db.session.commit()
        return proj.id, root.id


# ===========================================
# 版本历史 API 测试
# ===========================================

class TestVersionHistoryAPI:

    def test_versions_endpoint_returns_data(self, app):
        """GET /api/files/<id>/versions 返回正确结构"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传一个文件
        resp = _upload_file(client, b'hello', 'doc.pdf', proj_id, folder_id,
                           version_number='I')
        assert resp.status_code == 201
        file_id = json.loads(resp.data)['file']['id']

        # 查询版本
        resp = client.get(f'/api/files/{file_id}/versions')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert 'current_file' in data
        assert 'history' in data
        assert data['current_file']['original_filename'] == 'doc.pdf'
        assert len(data['history']) == 1  # 仅当前版本
        assert data['history'][0]['is_current'] is True
        assert data['history'][0]['version_number'] == 'I'

    def test_versions_endpoint_returns_404_for_nonexistent(self, app):
        """不存在的文件返回 404"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get('/api/files/9999/versions')
        assert resp.status_code == 404

    def test_versions_includes_replaced_files(self, app):
        """被覆盖替换的旧文件也应出现在 history 中"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传 v1，然后覆盖为 v2
        r1 = _upload_file(client, b'v1', 'report.pdf', proj_id, folder_id,
                         version_number='I')
        assert r1.status_code == 201

        r2 = _upload_file(client, b'v2', 'report.pdf', proj_id, folder_id,
                         version_number='I', duplicate_action='override')
        assert r2.status_code == 201

        # 查询版本历史（用 v2 的 ID）
        file_id_v2 = json.loads(r2.data)['file']['id']
        resp = client.get(f'/api/files/{file_id_v2}/versions')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        history = data['history']
        assert len(history) == 2  # v1 + v2

        versions = [v['version_number'] for v in history]
        assert 'I' in versions
        assert 'II' in versions

    def test_unrelated_file_not_in_history(self, app):
        """不同项目或不同文件名的版本不应出现在历史中"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传两个不同名称的文件
        _upload_file(client, b'a', 'alpha.pdf', proj_id, folder_id)
        r2 = _upload_file(client, b'b', 'beta.pdf', proj_id, folder_id)
        assert r2.status_code == 201
        file_id = json.loads(r2.data)['file']['id']

        resp = client.get(f'/api/files/{file_id}/versions')
        data = json.loads(resp.data)
        assert len(data['history']) == 1  # 仅 beta.pdf 自身


# ===========================================
# has_versions 字段测试
# ===========================================

class TestHasVersionsField:

    def test_new_file_has_versions_false(self, app):
        """新上传文件（无历史）的 has_versions 为 False"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'new.pdf', proj_id, folder_id)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        files = json.loads(resp.data)['files']
        assert len(files) == 1
        assert files[0]['has_versions'] is False

    def test_replaced_file_has_versions_true(self, app):
        """被覆盖过的文件（存在旧版本）的 has_versions 为 True"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传然后覆盖
        _upload_file(client, b'v1', 'doc.pdf', proj_id, folder_id, version_number='I')
        _upload_file(client, b'v2', 'doc.pdf', proj_id, folder_id, version_number='I',
                    duplicate_action='override')

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        files = json.loads(resp.data)['files']
        # 找到当前版本（version_number='II'）
        current = [f for f in files if f['version_number'] == 'II']
        assert len(current) == 1
        assert current[0]['has_versions'] is True
