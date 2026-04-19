from __future__ import annotations

import asyncio
from types import SimpleNamespace

from open_webui import config as config_module
from open_webui.utils import models as models_utils


def test_upgrade_legacy_default_user_permissions_enables_workspace_access():
    upgraded = config_module.upgrade_legacy_default_user_permissions(
        config_module.LEGACY_DEFAULT_USER_PERMISSIONS
    )

    assert upgraded['workspace']['models'] is True
    assert upgraded['workspace']['knowledge'] is True
    assert upgraded['workspace']['prompts'] is True
    assert upgraded['workspace']['tools'] is True
    assert upgraded['workspace']['skills'] is True
    assert upgraded['features']['notes'] is True


def test_upgrade_legacy_default_user_permissions_preserves_customized_permissions():
    custom_permissions = {
        'workspace': {
            'models': False,
            'knowledge': True,
            'prompts': False,
            'tools': False,
            'skills': False,
        },
        'features': {
            'notes': False,
        },
    }

    upgraded = config_module.upgrade_legacy_default_user_permissions(custom_permissions)

    assert upgraded == custom_permissions


def test_get_filtered_models_keeps_unconfigured_models_visible_to_users(monkeypatch):
    user = SimpleNamespace(id='user-1', role='user')
    models = [
        {'id': 'deepseek-chat', 'name': 'DeepSeek Chat'},
        {'id': 'managed-model', 'name': 'Managed Model', 'info': {'user_id': 'owner-1'}},
    ]

    monkeypatch.setattr(
        models_utils.Groups,
        'get_groups_by_member_id',
        lambda user_id, db=None: [],
    )
    monkeypatch.setattr(
        models_utils.AccessGrants,
        'get_accessible_resource_ids',
        lambda **kwargs: {'managed-model'},
    )

    filtered = models_utils.get_filtered_models(models, user)

    assert [model['id'] for model in filtered] == ['deepseek-chat', 'managed-model']


def test_get_session_user_backfills_default_knowledge_templates(monkeypatch):
    request = SimpleNamespace(
        headers={'Authorization': 'Bearer token-1'},
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    USER_PERMISSIONS={},
                )
            )
        ),
    )
    response = SimpleNamespace(set_cookie=lambda **kwargs: None)
    user = SimpleNamespace(
        id='user-1',
        email='user-1@example.com',
        name='User 1',
        role='user',
        profile_image_url='/user.png',
        bio=None,
        gender=None,
        date_of_birth=None,
        status_emoji=None,
        status_message=None,
        status_expires_at=None,
    )
    seeded = {}

    monkeypatch.setattr(
        'open_webui.routers.auths.get_http_authorization_cred',
        lambda header: SimpleNamespace(credentials='token-1'),
    )
    monkeypatch.setattr(
        'open_webui.routers.auths.decode_token',
        lambda token: {'exp': None},
    )
    monkeypatch.setattr(
        'open_webui.routers.auths.get_permissions',
        lambda user_id, default_permissions, db=None: {'workspace': {'knowledge': True}},
    )

    async def fake_seed(request_arg, user_arg, db=None):
        seeded['user_id'] = user_arg.id

    monkeypatch.setattr(
        'open_webui.routers.auths.ensure_default_knowledge_templates_for_user',
        fake_seed,
    )

    result = asyncio.run(
        __import__('open_webui.routers.auths', fromlist=['get_session_user']).get_session_user(
            request,
            response,
            user=user,
            db=None,
        )
    )

    assert result['id'] == 'user-1'
    assert seeded == {'user_id': 'user-1'}
