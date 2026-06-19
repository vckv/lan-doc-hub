"""F2-2 测试：跨项目上传校验、文件夹自动创建、快捷方式"""

import os
import tempfile
import json

import pytest
import bcrypt

from models import db as _db, Folder, Project, User, File
from services.upload_validation_service import (
    validate_folder_project,
    ensure_project_folder,
    create_shortcut_record,
)


@pytest.fixture
def app():
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


def _setup_admin(app):
    with app.app_context():
        pw_hash = bcrypt.hashpw(b'Admin@Pass1', bcrypt.gensalt()).decode('utf-8')
        admin = User(username='admin', display_name='Admin',
                     password_hash=pw_hash, role='admin', is_active=True,
                     created_ip='127.0.0.1', created_by_id=None)
        _db.session.add(admin)
        _db.session.commit()
        admin.created_by_id = admin.id
        _db.session.commit()

    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        token = sess.get('csrf_token')
    client.post('/login', data={
        'csrf_token': token, 'username': 'admin', 'password': 'Admin@Pass1',
    })
    return client


def _api_headers(client):
    with client.session_transaction() as sess:
        token = sess.get('csrf_token', '')
    return {'X-CSRF-Token': token, 'Content-Type': 'application/json'}


def _setup_two_projects(app):
    with app.app_context():
        # 确保 admin 存在（服务层测试可能不先调用 _setup_admin）
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            pw_hash = bcrypt.hashpw(b'Admin@Pass1', bcrypt.gensalt()).decode('utf-8')
            admin = User(username='admin', display_name='Admin',
                         password_hash=pw_hash, role='admin', is_active=True,
                         created_ip='127.0.0.1', created_by_id=None)
            _db.session.add(admin)
            _db.session.commit()
            admin.created_by_id = admin.id
            _db.session.commit()

        pa = Project(model='PRJ-A', name='项目A')
        pb = Project(model='PRJ-B', name='项目B')
        _db.session.add_all([pa, pb])
        _db.session.flush()

        fa = Folder(name='PRJ-A_项目A', is_project_root=True,
                     project_id=pa.id, parent_id=None, created_by=admin.id)
        fb = Folder(name='PRJ-B_项目B', is_project_root=True,
                     project_id=pb.id, parent_id=None, created_by=admin.id)
        _db.session.add_all([fa, fb])
        _db.session.flush()
        _db.session.commit()
        return {
            'project_a': {'id': pa.id, 'model': pa.model, 'name': pa.name},
            'project_b': {'id': pb.id, 'model': pb.model, 'name': pb.name},
            'folder_a_id': fa.id,
            'folder_b_id': fb.id,
        }


# ═══════════════════════════════════════════
# validate_folder_project 服务层
# ═══════════════════════════════════════════

class TestValidateFolderProject:

    def test_match_same_project(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            result = validate_folder_project(info['folder_a_id'], info['project_a']['id'])
            assert result['match'] is True
            assert 'errors' not in result

    def test_mismatch_different_project(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            result = validate_folder_project(info['folder_a_id'], info['project_b']['id'])
            assert result['match'] is False
            assert result['folder_project']['id'] == info['project_a']['id']
            assert result['declared_project']['id'] == info['project_b']['id']

    def test_folder_not_found(self, app):
        with app.app_context():
            result = validate_folder_project(99999, 1)
            assert result['match'] is None
            assert 'errors' in result

    def test_project_not_found(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            result = validate_folder_project(info['folder_a_id'], 99999)
            assert result['match'] is None
            assert 'errors' in result

    def test_child_folder_inherits_parent_project(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            child = Folder(name='子文件夹', is_project_root=False,
                           project_id=info['project_a']['id'],
                           parent_id=info['folder_a_id'],
                           created_by=admin.id)
            _db.session.add(child)
            _db.session.flush()
            _db.session.commit()
            child_id = child.id

            result = validate_folder_project(child_id, info['project_a']['id'])
            assert result['match'] is True


# ═══════════════════════════════════════════
# ensure_project_folder 服务层
# ═══════════════════════════════════════════

class TestEnsureProjectFolder:

    def test_existing_folder_returns_its_id(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            result = ensure_project_folder(info['project_a']['id'])
            assert result['success']
            assert result['folder_id'] == info['folder_a_id']
            assert result['created'] is False

    def test_missing_folder_auto_creates(self, app):
        with app.app_context():
            proj = Project(model='NEW', name='新项目')
            _db.session.add(proj)
            _db.session.flush()
            pid = proj.id
            _db.session.commit()

            result = ensure_project_folder(pid)
            assert result['success']
            assert result['created'] is True
            assert result['folder_name'] == 'NEW_新项目'

            root = Folder.query.filter_by(project_id=pid, is_project_root=True).first()
            assert root is not None
            assert root.name == 'NEW_新项目'

    def test_project_not_found(self, app):
        with app.app_context():
            result = ensure_project_folder(99999)
            assert not result['success']
            assert 'errors' in result


# ═══════════════════════════════════════════
# create_shortcut_record 服务层
# ═══════════════════════════════════════════

class TestCreateShortcutRecord:

    def test_shortcut_record_created(self, app):
        info = _setup_two_projects(app)
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            real = File(
                filename='uuid_test.pdf',
                original_filename='测试文档.pdf',
                file_path='uploads/2026/06/uuid_test.pdf',
                file_number='F-20260619-001',
                folder_id=info['folder_b_id'],
                uploader_id=admin.id,
                project_id=info['project_b']['id'],
                file_type='PDF',
                file_size=1024,
                is_current=True,
            )
            _db.session.add(real)
            _db.session.flush()
            _db.session.commit()
            real_id = real.id

            result = create_shortcut_record(
                file_id=real_id,
                current_folder_id=info['folder_a_id'],
                declared_project_id=info['project_b']['id'],
                user_id=admin.id,
            )
            assert result['success']
            assert result['shortcut']['folder_id'] == info['folder_a_id']
            assert result['shortcut']['shortcut_target_id'] == real_id
            assert '来自项目' in result['shortcut']['original_filename']

            shortcut = _db.session.get(File, result['shortcut']['id'])
            assert shortcut.is_shortcut is True
            assert shortcut.shortcut_target_id == real_id
            assert shortcut.folder_id == info['folder_a_id']

    def test_shortcut_with_nonexistent_file(self, app):
        with app.app_context():
            result = create_shortcut_record(
                file_id=99999, current_folder_id=1,
                declared_project_id=1, user_id=1,
            )
            assert not result['success']
            assert 'errors' in result


# ═══════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════

class TestUploadValidationAPI:

    def test_validate_api_mismatch(self, app):
        client = _setup_admin(app)
        info = _setup_two_projects(app)

        resp = client.post(
            '/api/validate-upload',
            data=json.dumps({
                'folder_id': info['folder_a_id'],
                'project_id': info['project_b']['id'],
            }),
            headers=_api_headers(client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['match'] is False

    def test_validate_api_match(self, app):
        client = _setup_admin(app)
        info = _setup_two_projects(app)

        resp = client.post(
            '/api/validate-upload',
            data=json.dumps({
                'folder_id': info['folder_a_id'],
                'project_id': info['project_a']['id'],
            }),
            headers=_api_headers(client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['match'] is True

    def test_ensure_folder_api_creates(self, app):
        client = _setup_admin(app)
        with app.app_context():
            proj = Project(model='API-T', name='API测试项目')
            _db.session.add(proj)
            _db.session.flush()
            pid = proj.id
            _db.session.commit()

        resp = client.post(
            f'/api/projects/{pid}/ensure-folder',
            headers=_api_headers(client),
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success']
        assert data['created'] is True
        assert data['folder_name'] == 'API-T_API测试项目'

    def test_create_shortcut_api(self, app):
        client = _setup_admin(app)
        info = _setup_two_projects(app)

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            real = File(
                filename='uuid_test.pdf',
                original_filename='测试.pdf',
                file_path='uploads/2026/06/uuid_test.pdf',
                file_number='F-20260619-099',
                folder_id=info['folder_b_id'],
                uploader_id=admin.id,
                project_id=info['project_b']['id'],
                file_type='PDF',
                file_size=2048,
                is_current=True,
            )
            _db.session.add(real)
            _db.session.flush()
            _db.session.commit()
            real_id = real.id

        resp = client.post(
            '/api/shortcuts',
            data=json.dumps({
                'file_id': real_id,
                'folder_id': info['folder_a_id'],
                'project_id': info['project_b']['id'],
            }),
            headers=_api_headers(client),
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data['success']
        assert '来自项目' in data['shortcut']['original_filename']
