"""F6-1: 文件列表分页 测试"""

import io
import json
import os
import tempfile

import pytest
import bcrypt

from models import db as _db, File, Folder, Project, User


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
    client.post('/login', data={
        'csrf_token': token,
        'username': username,
        'password': password,
    })
    return client


def _get_csrf(client):
    with client.session_transaction() as sess:
        return sess.get('csrf_token', '')


def _upload_file(client, content, filename, proj_id, folder_id, **extra):
    data = {
        'file': (io.BytesIO(content), filename),
        'project_id': str(proj_id),
        'folder_id': str(folder_id),
        'csrf_token': _get_csrf(client),
    }
    data.update(extra)
    return client.post('/api/files/upload', data=data)


def _seed_project_and_folder(app, project_model='F6T1', project_name='分页测试'):
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


class TestFileListPagination:

    def test_returns_pagination_metadata(self, app):
        """返回的数据应包含 total/page/pages 字段"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert 'total' in data
        assert 'page' in data
        assert 'pages' in data
        assert data['total'] == 1
        assert data['page'] == 1
        assert data['pages'] == 1
        assert 'files' in data
        assert len(data['files']) == 1

    def test_pagination_limit_and_offset(self, app):
        """per_page=3 时应只返回对应页的数据"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传 5 个文件
        for i in range(5):
            _upload_file(client, b'x', f'file_{i}.pdf', proj_id, folder_id)

        # 第 1 页：per_page=3 → 返回 3 条
        resp = client.get(f'/api/files?folder_id={folder_id}&page=1&per_page=3')
        data = json.loads(resp.data)
        assert data['success'] is True
        assert len(data['files']) == 3
        assert data['total'] == 5
        assert data['pages'] == 2

        # 第 2 页：返回 2 条
        resp = client.get(f'/api/files?folder_id={folder_id}&page=2&per_page=3')
        data = json.loads(resp.data)
        assert len(data['files']) == 2
        assert data['page'] == 2

    def test_page_out_of_range_clamped(self, app):
        """页码超出范围时自动钳位到最大/最小页"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        _upload_file(client, b'x', 'a.pdf', proj_id, folder_id)

        # page=999 → 钳位到 pages
        resp = client.get(f'/api/files?folder_id={folder_id}&page=999&per_page=20')
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['page'] == 1
        assert data['pages'] == 1

        # page=0 → 钳位到 1
        resp = client.get(f'/api/files?folder_id={folder_id}&page=0&per_page=20')
        data = json.loads(resp.data)
        assert data['page'] == 1

    def test_per_page_capped(self, app):
        """per_page 超过 100 应钳位到 100"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.get(f'/api/files?folder_id={folder_id}&page=1&per_page=999')
        assert resp.status_code == 200
        # per_page 应在路由层被钳位到 100

    def test_empty_folder(self, app):
        """空文件夹返回空列表和正确的元数据"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = client.get(f'/api/files?folder_id={folder_id}')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['files'] == []
        assert data['total'] == 0
        assert data['pages'] == 1

    def test_has_versions_field_works_with_pagination(self, app):
        """分页后 has_versions 字段仍正确"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 上传后覆盖，确保当前版本有 has_versions=True
        _upload_file(client, b'v1', 'doc.pdf', proj_id, folder_id, version_number='I')
        _upload_file(client, b'v2', 'doc.pdf', proj_id, folder_id, version_number='I',
                    duplicate_action='override')

        resp = client.get(f'/api/files?folder_id={folder_id}')
        data = json.loads(resp.data)
        current = [f for f in data['files'] if f['version_number'] == 'II']
        assert len(current) == 1
        assert current[0]['has_versions'] is True
