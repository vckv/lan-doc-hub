"""F3-1 测试：文件上传、编号生成、文件列表"""

import os
import tempfile
import json
import io

import pytest
import bcrypt

from models import db as _db, Folder, Project, User, File
from services.file_service import (
    generate_file_number,
    get_files_by_folder,
)


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    db_uri = 'sqlite:///' + db_path

    key_fd, key_path = tempfile.mkstemp(suffix='.setup_key')
    with open(key_path, 'w', encoding='utf-8') as kf:
        kf.write('test-key')

    upload_dir = tempfile.mkdtemp(suffix='_uploads')

    from app import create_app
    app = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'TESTING': True,
        'SETUP_KEY_FILE': key_path,
        'UPLOAD_FOLDER': upload_dir,
        'MAX_CONTENT_LENGTH': 50 * 1024 * 1024,
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
    import shutil
    try:
        shutil.rmtree(upload_dir)
    except Exception:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def _api_headers(client):
    with client.session_transaction() as sess:
        token = sess.get('csrf_token', '')
    return {'X-CSRF-Token': token}


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


def _setup_project_and_folder(app):
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        proj = Project(model='PRJ-T', name='测试项目')
        _db.session.add(proj)
        _db.session.flush()
        folder = Folder(name='PRJ-T_测试项目', is_project_root=True,
                         project_id=proj.id, parent_id=None,
                         created_by=admin.id)
        _db.session.add(folder)
        _db.session.flush()
        _db.session.commit()
        return {'project_id': proj.id, 'folder_id': folder.id}


# ═══════════════════════════════════════════
# 文件编号生成
# ═══════════════════════════════════════════

class TestFileNumber:

    def test_first_file_number_of_day(self, app):
        with app.app_context():
            num = generate_file_number()
            assert num.startswith('F-')
            assert num.endswith('-001')

    def test_sequential_file_number(self, app):
        with app.app_context():
            pw_hash = bcrypt.hashpw(b'Admin@Pass1', bcrypt.gensalt()).decode('utf-8')
            admin = User(username='admin', display_name='Admin',
                         password_hash=pw_hash, role='admin', is_active=True,
                         created_ip='127.0.0.1', created_by_id=None)
            _db.session.add(admin)
            _db.session.flush()
            admin.created_by_id = admin.id
            _db.session.commit()

            proj = Project(model='T', name='T')
            _db.session.add(proj)
            _db.session.flush()
            folder = Folder(name='T_T', is_project_root=True,
                            project_id=proj.id, parent_id=None,
                            created_by=admin.id)
            _db.session.add(folder)
            _db.session.flush()
            _db.session.commit()

            f1 = File(filename='a.pdf', original_filename='a.pdf',
                       file_path='/tmp/a.pdf', file_number=generate_file_number(),
                       folder_id=folder.id, uploader_id=admin.id,
                       project_id=proj.id, file_type='PDF', file_size=100)
            _db.session.add(f1)
            _db.session.commit()

            num2 = generate_file_number()
            assert int(num2[-3:]) >= 2


# ═══════════════════════════════════════════
# 文件上传 API
# ═══════════════════════════════════════════

class TestUploadAPI:

    def test_upload_pdf_success(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_folder(app)

        data = {
            'file': (io.BytesIO(b'%PDF-1.4 fake pdf content'), 'test.pdf'),
            'project_id': str(info['project_id']),
            'folder_id': str(info['folder_id']),
        }
        resp = client.post(
            '/api/files/upload', data=data,
            content_type='multipart/form-data',
            headers=_api_headers(client),
        )
        assert resp.status_code == 201
        result = json.loads(resp.data)
        assert result['success']
        assert result['file']['original_filename'] == 'test.pdf'
        assert result['file']['file_type'] == 'PDF'

    def test_upload_rejects_no_file(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_folder(app)

        resp = client.post(
            '/api/files/upload',
            data={'project_id': info['project_id'], 'folder_id': info['folder_id']},
            headers=_api_headers(client),
        )
        assert resp.status_code == 400

    def test_upload_rejects_bad_extension(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_folder(app)

        data = {
            'file': (io.BytesIO(b'dangerous!'), 'virus.exe'),
            'project_id': str(info['project_id']),
            'folder_id': str(info['folder_id']),
        }
        resp = client.post(
            '/api/files/upload', data=data,
            content_type='multipart/form-data',
            headers=_api_headers(client),
        )
        assert resp.status_code == 400
        assert '不支持' in str(json.loads(resp.data))

    def test_upload_requires_login(self, client):
        with client.session_transaction() as sess:
            sess['csrf_token'] = 'test-csrf'
        resp = client.post('/api/files/upload',
                           headers={'X-CSRF-Token': 'test-csrf'})
        assert resp.status_code == 401

    def test_pre_number_returns_valid_format(self, app):
        client = _setup_admin(app)
        resp = client.post('/api/files/pre-number', headers=_api_headers(client))
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['file_number'].startswith('F-')
        assert len(data['file_number']) == 14  # F-YYYYMMDD-NNN


# ═══════════════════════════════════════════
# 文件列表 API
# ═══════════════════════════════════════════

class TestFileListAPI:

    def test_empty_folder_returns_empty_list(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_folder(app)

        resp = client.get(f"/api/files?folder_id={info['folder_id']}")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['files'] == []

    def test_folder_with_files_returns_list(self, app):
        client = _setup_admin(app)
        info = _setup_project_and_folder(app)

        data = {
            'file': (io.BytesIO(b'%PDF-1.4 test'), 'doc.pdf'),
            'project_id': str(info['project_id']),
            'folder_id': str(info['folder_id']),
        }
        client.post(
            '/api/files/upload', data=data,
            content_type='multipart/form-data',
            headers=_api_headers(client),
        )

        resp = client.get(f"/api/files?folder_id={info['folder_id']}")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['files']) == 1
        assert data['files'][0]['original_filename'] == 'doc.pdf'

    def test_list_requires_login(self, client):
        resp = client.get('/api/files?folder_id=1')
        assert resp.status_code == 401

    def test_list_without_folder_id_fails(self, app):
        client = _setup_admin(app)
        resp = client.get('/api/files')
        assert resp.status_code == 400
