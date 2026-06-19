"""F2-1 测试：文件夹树查询、CRUD、权限保护"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Folder, Project, User


@pytest.fixture
def app():
    """创建临时数据库 + setup 密钥的应用实例"""
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
    """从 client 的 session 中提取 CSRF token 作为请求头"""
    with client.session_transaction() as sess:
        token = sess.get('csrf_token', '')
    return {'X-CSRF-Token': token, 'Content-Type': 'application/json'}


def _setup_admin(app):
    """创建管理员并登录，返回已登录的 client"""
    with app.app_context():
        pw_hash = bcrypt.hashpw(b'Admin@Pass1', bcrypt.gensalt()).decode('utf-8')
        admin = User(
            username='admin',
            display_name='Admin',
            password_hash=pw_hash,
            role='admin',
            is_active=True,
            created_ip='127.0.0.1',
            created_by_id=None,
        )
        _db.session.add(admin)
        _db.session.commit()
        admin.created_by_id = admin.id
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    client.post('/login', data={
        'csrf_token': token,
        'username': 'admin',
        'password': 'Admin@Pass1',
    })
    return client


def _setup_project_and_root(app):
    """创建项目 + 一级文件夹，返回 {'project_id', 'root_id', 'root_name'}"""
    with app.app_context():
        proj = Project(model='PRJ001', name='某研发项目')
        _db.session.add(proj)
        _db.session.flush()
        project_id = proj.id

        admin = User.query.filter_by(username='admin').first()
        root_name = f'{proj.model}_{proj.name}'
        root = Folder(
            name=root_name,
            is_project_root=True,
            project_id=project_id,
            parent_id=None,
            created_by=admin.id,
        )
        _db.session.add(root)
        _db.session.flush()
        root_id = root.id
        _db.session.commit()
        return {'project_id': project_id, 'root_id': root_id, 'root_name': root_name}


# ═══════════════════════════════════════════
# get_tree 测试
# ═══════════════════════════════════════════

class TestGetTree:

    def test_empty_tree_returns_empty_list(self, app):
        client = _setup_admin(app)
        resp = client.get('/api/folders/tree')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['tree'] == []

    def test_tree_returns_root_folders(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        resp = client.get('/api/folders/tree')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert len(data['tree']) == 1
        assert data['tree'][0]['name'] == info['root_name']
        assert data['tree'][0]['is_project_root'] is True
        assert data['tree'][0]['children'] == []

    def test_tree_returns_nested_children(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            child = Folder(
                name='子文件夹A',
                is_project_root=False,
                project_id=info['project_id'],
                parent_id=info['root_id'],
                created_by=admin.id,
            )
            _db.session.add(child)
            _db.session.commit()

        resp = client.get('/api/folders/tree')
        data = json.loads(resp.data)
        assert len(data['tree'][0]['children']) == 1
        assert data['tree'][0]['children'][0]['name'] == '子文件夹A'

    def test_tree_requires_login(self, client):
        resp = client.get('/api/folders/tree')
        assert resp.status_code == 401


# ═══════════════════════════════════════════
# 创建子文件夹测试
# ═══════════════════════════════════════════

class TestCreateFolder:

    def test_create_subfolder_success(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        resp = client.post(
            '/api/folders',
            data=json.dumps({'name': '新文件夹', 'parent_id': info['root_id']}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['success']
        assert data['folder']['name'] == '新文件夹'
        assert data['folder']['parent_id'] == info['root_id']

    def test_create_duplicate_name_fails(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        hdrs = _api_headers(client)
        client.post(
            '/api/folders',
            data=json.dumps({'name': '唯一夹', 'parent_id': info['root_id']}),
            headers=hdrs,
        )
        resp = client.post(
            '/api/folders',
            data=json.dumps({'name': '唯一夹', 'parent_id': info['root_id']}),
            headers=hdrs,
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert '同名' in str(data['errors'])

    def test_create_without_login_returns_400(self, client):
        """未登录 → CSRF 先行拦截返回 400"""
        resp = client.post(
            '/api/folders',
            data=json.dumps({'name': 'x', 'parent_id': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════
# 重命名测试
# ═══════════════════════════════════════════

class TestRenameFolder:

    def test_rename_subfolder_success(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            child = Folder(name='旧名', is_project_root=False,
                           project_id=info['project_id'], parent_id=info['root_id'],
                           created_by=admin.id)
            _db.session.add(child)
            _db.session.flush()
            child_id = child.id
            _db.session.commit()

        resp = client.put(
            f'/api/folders/{child_id}',
            data=json.dumps({'name': '新名'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['folder']['name'] == '新名'

    def test_rename_root_folder_fails(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        resp = client.put(
            f'/api/folders/{info["root_id"]}',
            data=json.dumps({'name': 'NewName'}),
            headers=_api_headers(client),
        )
        assert resp.status_code == 403
        data = json.loads(resp.data)
        assert '不可重命名' in str(data['errors'])


# ═══════════════════════════════════════════
# 删除测试
# ═══════════════════════════════════════════

class TestDeleteFolder:

    def test_delete_subfolder_success(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            child = Folder(name='待删', is_project_root=False,
                           project_id=info['project_id'], parent_id=info['root_id'],
                           created_by=admin.id)
            _db.session.add(child)
            _db.session.flush()
            child_id = child.id
            _db.session.commit()

        resp = client.delete(
            f'/api/folders/{child_id}',
            headers=_api_headers(client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']

        tree_resp = client.get('/api/folders/tree')
        tree = json.loads(tree_resp.data)['tree']
        assert len(tree[0]['children']) == 0

    def test_delete_root_folder_fails(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        resp = client.delete(
            f'/api/folders/{info["root_id"]}',
            headers=_api_headers(client),
        )
        assert resp.status_code == 403
        data = json.loads(resp.data)
        assert '不可删除' in str(data['errors'])

    def test_delete_cascades_children(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_root(app)

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            parent = Folder(name='父', is_project_root=False,
                            project_id=info['project_id'], parent_id=info['root_id'],
                            created_by=admin.id)
            _db.session.add(parent)
            _db.session.flush()
            parent_id = parent.id
            child = Folder(name='子', is_project_root=False,
                           project_id=info['project_id'], parent_id=parent_id,
                           created_by=admin.id)
            _db.session.add(child)
            _db.session.flush()
            child_id = child.id
            _db.session.commit()

        resp = client.delete(
            f'/api/folders/{parent_id}',
            headers=_api_headers(client),
        )
        assert resp.status_code == 200

        with app.app_context():
            assert _db.session.get(Folder, parent_id) is None
            assert _db.session.get(Folder, child_id) is None
