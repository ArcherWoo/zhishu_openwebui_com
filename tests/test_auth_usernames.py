from __future__ import annotations

import asyncio
from contextlib import nullcontext
from contextlib import contextmanager
from types import SimpleNamespace

from open_webui.models import auths as auth_models
from open_webui.routers import auths as auth_router


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


def test_signup_handler_initializes_default_knowledge_templates(monkeypatch):
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    DEFAULT_USER_ROLE='user',
                    WEBHOOK_URL='',
                    DEFAULT_GROUP_ID=None,
                    ENABLE_SIGNUP=True,
                )
            )
        )
    )
    created_user = SimpleNamespace(id='user-1', name='Alice', email='alice@example.com', role='user')
    seeded = {}

    monkeypatch.setattr(auth_router, 'get_password_hash', lambda password: f'hashed::{password}')
    monkeypatch.setattr(
        auth_router.Auths,
        'insert_new_auth',
        lambda **kwargs: created_user,
    )
    monkeypatch.setattr(auth_router.Users, 'get_num_users', lambda db=None: 2)
    monkeypatch.setattr(auth_router, 'apply_default_group_assignment', lambda group_id, user_id, db=None: None)

    async def fake_seed(request_arg, user_arg, db=None):
        seeded['user_id'] = user_arg.id

    monkeypatch.setattr(auth_router, 'ensure_default_knowledge_templates_for_user', fake_seed)

    user = asyncio.run(
        auth_router.signup_handler(
            request,
            email='alice@example.com',
            password='password',
            name='Alice',
            db=None,
        )
    )

    assert user == created_user
    assert seeded == {'user_id': 'user-1'}


def test_signin_schedules_default_knowledge_seed_without_blocking(monkeypatch):
    request = SimpleNamespace(
        headers={},
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    JWT_EXPIRES_IN='4w',
                    USER_PERMISSIONS={},
                )
            )
        ),
    )
    response = SimpleNamespace(set_cookie=lambda **kwargs: None)
    authenticated_user = SimpleNamespace(
        id='user-3',
        email='alice@example.com',
        name='Alice',
        role='user',
    )
    scheduled = {}

    monkeypatch.setattr(auth_router, 'ENABLE_PASSWORD_AUTH', True)
    monkeypatch.setattr(auth_router, 'WEBUI_AUTH_TRUSTED_EMAIL_HEADER', '')
    monkeypatch.setattr(auth_router, 'WEBUI_AUTH', True)
    monkeypatch.setattr(auth_router, 'parse_duration', lambda value: None)
    monkeypatch.setattr(auth_router, 'create_token', lambda data, expires_delta=None: 'token-1')
    monkeypatch.setattr(auth_router, 'get_permissions', lambda user_id, permissions, db=None: {})
    monkeypatch.setattr(auth_router, 'verify_password', lambda password, password_hash: True)
    monkeypatch.setattr(auth_router, 'schedule_default_knowledge_template_seed', lambda request_arg, user_arg: scheduled.setdefault('user_id', user_arg.id))
    monkeypatch.setattr(
        auth_router.Auths,
        'authenticate_user',
        lambda identifier, checker, db=None: authenticated_user,
    )

    result = asyncio.run(
        auth_router.signin(
            request,
            response,
            auth_router.SigninForm(email='alice', password='password'),
            db=None,
        )
    )

    assert result['token'] == 'token-1'
    assert result['id'] == 'user-3'
    assert scheduled == {'user_id': 'user-3'}


def test_schedule_default_knowledge_seed_uses_db_context(monkeypatch):
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    user = SimpleNamespace(id='user-4')
    seeded = {}

    @contextmanager
    def fake_get_db():
        yield 'db-session'

    async def fake_seed(request_arg, user_arg, db=None):
        seeded['user_id'] = user_arg.id
        seeded['db'] = db

    def fake_create_task(coro):
        asyncio.run(coro)
        return SimpleNamespace()

    monkeypatch.setattr(auth_router, 'get_db', fake_get_db)
    monkeypatch.setattr(auth_router, 'ensure_default_knowledge_templates_for_user_safe', fake_seed)
    monkeypatch.setattr(auth_router.asyncio, 'create_task', fake_create_task)

    auth_router.schedule_default_knowledge_template_seed(request, user)

    assert seeded == {
        'user_id': 'user-4',
        'db': 'db-session',
    }


def test_add_user_continues_when_default_knowledge_seed_fails(monkeypatch):
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    DEFAULT_GROUP_ID=None,
                )
            )
        )
    )
    admin_user = SimpleNamespace(id='admin-1')
    created_user = SimpleNamespace(id='user-2', email='bob@example.com', name='Bob', role='admin')
    logged = {}

    monkeypatch.setattr(auth_router, 'validate_email_format', lambda value: True)
    monkeypatch.setattr(auth_router.Users, 'get_user_by_email', lambda email, db=None: None)
    monkeypatch.setattr(auth_router.Users, 'get_user_by_username', lambda username, db=None: None)
    monkeypatch.setattr(auth_router, 'validate_password', lambda password: None)
    monkeypatch.setattr(auth_router, 'get_password_hash', lambda password: f'hashed::{password}')
    monkeypatch.setattr(
        auth_router.Auths,
        'insert_new_auth',
        lambda *args, **kwargs: created_user,
    )
    monkeypatch.setattr(auth_router, 'apply_default_group_assignment', lambda group_id, user_id, db=None: None)
    monkeypatch.setattr(auth_router, 'create_token', lambda data: 'token-1')
    monkeypatch.setattr(
        auth_router.log,
        'warning',
        lambda message, *args: logged.setdefault('message', message % args if args else message),
    )

    async def fake_seed(request_arg, user_arg, db=None):
        raise RuntimeError('seed failed')

    monkeypatch.setattr(auth_router, 'ensure_default_knowledge_templates_for_user', fake_seed)

    result = asyncio.run(
        auth_router.add_user(
            request,
            form_data=auth_router.AddUserForm(
                name='Bob',
                email='bob@example.com',
                password='password',
                role='admin',
            ),
            user=admin_user,
            db=None,
        )
    )

    assert result['id'] == 'user-2'
    assert result['email'] == 'bob@example.com'
    assert result['token'] == 'token-1'
    assert logged['message'] == 'Failed to seed default knowledge templates for user user-2: seed failed'
