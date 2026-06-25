"""F5-1: 同名文件检测 + 覆盖/另存为 测试"""

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


def _get_csrf(client):
    """从 session 中提取 CSRF Token"""
    with client.session_transaction() as sess:
        return sess.get('csrf_token', '')


def _upload_file(client, content, filename, proj_id, folder_id, **extra):
    """上传文件辅助函数，自动附加 CSRF token"""
    data = {
        'file': (io.BytesIO(content), filename),
        'project_id': str(proj_id),
        'folder_id': str(folder_id),
        'csrf_token': _get_csrf(client),
    }
    data.update(extra)
    return client.post('/api/files/upload', data=data)


def _seed_project_and_folder(app, project_model='F5TEST', project_name='测试项目'):
    """创建测试用的项目和根文件夹，返回 (project_id, folder_id)"""
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
# check-duplicate 端点测试
# ===========================================

class TestCheckDuplicate:

    def test_no_duplicate_returns_false(self, app):
        """目标项目中无同名文件时返回 exists=False"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, _ = _seed_project_and_folder(app)

        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'nonexistent.pdf', 'project_id': proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['exists'] is False

    def test_existing_file_returns_true_and_details(self, app):
        """目标项目中存在同名文件时返回 exists=True 及详细信息"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传一个文件
        resp = _upload_file(client, b'test content', 'report.pdf', proj_id, folder_id,
                           version_number='I')
        assert resp.status_code == 201

        # 检测同名文件
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'report.pdf', 'project_id': proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] is True
        assert data['exists'] is True
        assert data['existing_file']['original_filename'] == 'report.pdf'
        assert data['existing_file']['version_number'] == 'I'

    def test_missing_params_returns_400(self, app):
        """缺少参数时返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'test.pdf'},
        )
        assert resp.status_code == 400

        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'project_id': 1},
        )
        assert resp.status_code == 400

    def test_different_project_no_conflict(self, app):
        """不同项目中的同名文件不算冲突"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app, 'F5TEST', '测试项目')

        # 创建第二个项目
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            other_project = Project(model='PRJ002', name='其他项目')
            _db.session.add(other_project)
            _db.session.flush()
            other_folder = Folder(
                name='PRJ002_其他项目',
                is_project_root=True,
                project_id=other_project.id,
                parent_id=None,
                created_by=admin.id,
            )
            _db.session.add(other_folder)
            _db.session.commit()
            other_proj_id = other_project.id

        # 在第一个项目中上传
        _upload_file(client, b'test', 'shared.pdf', proj_id, folder_id)

        # 在另一个项目中检测 — 应不冲突
        resp = client.get(
            '/api/files/check-duplicate',
            query_string={'filename': 'shared.pdf', 'project_id': other_proj_id},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['exists'] is False


# ===========================================
# 覆盖为新版本测试
# ===========================================

class TestOverrideUpload:

    def test_override_archives_to_file_versions(self, app):
        """覆盖上传时应将旧版本归档到 file_versions 表"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传 v1
        resp = _upload_file(client, b'version one', 'doc.pdf', proj_id, folder_id,
                           version_number='I', version_note='first version')
        assert resp.status_code == 201
        file_id_v1 = json.loads(resp.data)['file']['id']

        # 覆盖为 v2
        resp2 = _upload_file(client, b'version two', 'doc.pdf', proj_id, folder_id,
                            version_number='I', duplicate_action='override')
        assert resp2.status_code == 201

        # 验证旧版本已归档
        with app.app_context():
            versions = (
                FileVersion.query
                .filter_by(file_id=file_id_v1)
                .all()
            )
            assert len(versions) == 1
            assert versions[0].version_number == 'I'
            assert versions[0].version_note == 'first version'
            assert versions[0].file_size == len(b'version one')

            # 验证旧文件 is_current=False
            old = _db.session.get(File, file_id_v1)
            assert old.is_current is False

            # 验证新文件 version_number=II
            new_id = json.loads(resp2.data)['file']['id']
            new = _db.session.get(File, new_id)
            assert new.is_current is True
            assert new.version_number == 'II'

    def test_override_increments_version_roman(self, app):
        """多次覆盖的版本号应依次递增 I → II → III"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        def upload_version(content, dup_action=None, version='I'):
            kwargs = {'version_number': version}
            if dup_action:
                kwargs['duplicate_action'] = dup_action
            return _upload_file(client, content, 'doc.pdf', proj_id, folder_id, **kwargs)

        r1 = upload_version(b'v1')
        assert r1.status_code == 201
        assert json.loads(r1.data)['file']['version_number'] == 'I'

        r2 = upload_version(b'v2', 'override')
        assert r2.status_code == 201
        assert json.loads(r2.data)['file']['version_number'] == 'II'

        r3 = upload_version(b'v3', 'override')
        assert r3.status_code == 201
        assert json.loads(r3.data)['file']['version_number'] == 'III'


# ===========================================
# 另存为新文件测试
# ===========================================

class TestSaveAsNewUpload:

    def test_save_as_new_uses_suffixed_name(self, app):
        """另存为新文件时 original_filename 应包含后缀"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传原文件
        resp = _upload_file(client, b'original', 'report.pdf', proj_id, folder_id)
        assert resp.status_code == 201

        # 另存为新文件
        resp2 = _upload_file(client, b'new content', 'report.pdf', proj_id, folder_id,
                            duplicate_action='save_as_new', new_filename='report (1).pdf')
        assert resp2.status_code == 201
        new_file = json.loads(resp2.data)['file']
        assert new_file['original_filename'] == 'report (1).pdf'
        assert new_file['version_number'] == 'I'

    def test_save_as_new_does_not_archive_old(self, app):
        """另存为新文件时不应归档原文件（原文件保持 is_current=True）"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        # 先上传原文件
        resp = _upload_file(client, b'original', 'data.xlsx', proj_id, folder_id)
        assert resp.status_code == 201
        file_id_v1 = json.loads(resp.data)['file']['id']

        # 另存为新文件
        _upload_file(client, b'new data', 'data.xlsx', proj_id, folder_id,
                    duplicate_action='save_as_new', new_filename='data (1).xlsx')

        # 原文件仍为当前版本
        with app.app_context():
            old = _db.session.get(File, file_id_v1)
            assert old.is_current is True

            # 无新增 FileVersion 记录
            versions = (
                FileVersion.query
                .filter_by(file_id=file_id_v1)
                .all()
            )
            assert len(versions) == 0

    def test_save_as_new_missing_new_filename_returns_400(self, app):
        """save_as_new 但未提供 new_filename 时返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = _upload_file(client, b'test', 'test.txt', proj_id, folder_id,
                           duplicate_action='save_as_new')
        assert resp.status_code == 400

    def test_invalid_duplicate_action_returns_400(self, app):
        """无效的 duplicate_action 返回 400"""
        client = _login_as(app, 'admin', 'Admin@Pass1', 'admin')
        proj_id, folder_id = _seed_project_and_folder(app)

        resp = _upload_file(client, b'test', 'test.txt', proj_id, folder_id,
                           duplicate_action='invalid_action')
        assert resp.status_code == 400
