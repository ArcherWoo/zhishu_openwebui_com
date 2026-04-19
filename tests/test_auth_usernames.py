from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from open_webui.models import auths as auth_models


class _FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filter_kwargs = None

    def filter_by(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def first(self):
        return self.result


class _FakeDB:
    def __init__(self, auth_record=None):
        self.auth_record = auth_record
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def query(self, _model):
        return _FakeQuery(self.auth_record)


def test_authenticate_user_supports_username_lookup(monkeypatch):
    user = SimpleNamespace(id='user-1', email='alice@example.com')
    fake_db = _FakeDB(auth_record=SimpleNamespace(password='stored-hash', active=True))

    monkeypatch.setattr(auth_models, 'get_db_context', lambda db=None: nullcontext(fake_db))
    monkeypatch.setattr(auth_models.Users, 'get_user_by_email', lambda identifier, db=None: None)
    monkeypatch.setattr(
        auth_models.Users,
        'get_user_by_username',
        lambda identifier, db=None: user if identifier == 'alice' else None,
    )

    authenticated = auth_models.Auths.authenticate_user(
        'alice',
        lambda password_hash: password_hash == 'stored-hash',
    )

    assert authenticated == user


def test_insert_new_auth_generates_username_for_new_local_user(monkeypatch):
    fake_db = _FakeDB()
    captured = {}
    created_user = SimpleNamespace(id='user-2', email='alice@example.com', username='alice')

    monkeypatch.setattr(auth_models, 'get_db_context', lambda db=None: nullcontext(fake_db))
    monkeypatch.setattr(auth_models.Users, 'generate_unique_username', lambda value, db=None: 'alice')

    def fake_insert_new_user(
        id,
        name,
        email,
        profile_image_url='/user.png',
        role='pending',
        username=None,
        oauth=None,
        db=None,
    ):
        captured['id'] = id
        captured['username'] = username
        captured['email'] = email
        return created_user

    monkeypatch.setattr(auth_models.Users, 'insert_new_user', fake_insert_new_user)

    inserted = auth_models.Auths.insert_new_auth(
        email='alice@example.com',
        password='hashed-password',
        name='Alice',
    )

    assert inserted == created_user
    assert captured == {
        'id': fake_db.added[0].id,
        'username': 'alice',
        'email': 'alice@example.com',
    }
