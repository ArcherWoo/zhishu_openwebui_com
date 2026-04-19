from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from open_webui.models.files import FileModel

from open_webui.utils.default_knowledge_initializer import (
    ensure_default_knowledge_templates_for_user,
    seed_default_knowledge_templates_for_existing_users,
)
from open_webui.utils.default_knowledge_templates import (
    DEFAULT_KNOWLEDGE_NAME,
    DEFAULT_SEED_DOCUMENTS,
    DEFAULT_TEMPLATE_VERSION,
)


def build_request() -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    BYPASS_EMBEDDING_AND_RETRIEVAL=True,
                ),
                EMBEDDING_FUNCTION=lambda *_args, **_kwargs: [0.0],
            )
        )
    )


def build_user(user_id: str = 'user-1') -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email=f'{user_id}@example.com',
        name=f'User {user_id}',
        role='user',
    )


def make_file(file_id: str, name: str, seed_document_key: str) -> FileModel:
    return FileModel(
        id=file_id,
        user_id='user-1',
        filename=name,
        path=f'/tmp/{file_id}.md',
        data={'content': '# content'},
        meta={
            'name': name,
            'content_type': 'text/markdown',
            'seeded_by_system': True,
            'seed_template_version': DEFAULT_TEMPLATE_VERSION,
            'seed_template_key': 'department-knowhow-starter',
            'seed_document_key': seed_document_key,
        },
        created_at=1,
        updated_at=1,
    )


def test_default_seed_documents_cover_general_and_procurement_templates():
    assert DEFAULT_KNOWLEDGE_NAME
    assert DEFAULT_TEMPLATE_VERSION == 3
    assert len(DEFAULT_SEED_DOCUMENTS) == 13
    assert [document.key for document in DEFAULT_SEED_DOCUMENTS] == [
        'knowhow-guide',
        'knowhow-fill-template',
        'faq-and-pitfalls',
        'procurement-commercial-boss-review',
        'procurement-classification-governance',
        'knowhow-table-fill',
        'knowhow-table-example',
        'faq-table-fill',
        'faq-table-example',
        'procurement-commercial-table-fill',
        'procurement-commercial-table-example',
        'procurement-classification-table-fill',
        'procurement-classification-table-example',
    ]
    assert all(document.title for document in DEFAULT_SEED_DOCUMENTS)
    assert all(document.content.startswith('#') for document in DEFAULT_SEED_DOCUMENTS)
    table_template_keys = {
        'knowhow-table-fill',
        'knowhow-table-example',
        'faq-table-fill',
        'faq-table-example',
        'procurement-commercial-table-fill',
        'procurement-commercial-table-example',
        'procurement-classification-table-fill',
        'procurement-classification-table-example',
    }
    assert all(
        '\n|' in document.content and '\n| ---' in document.content
        for document in DEFAULT_SEED_DOCUMENTS
        if document.key in table_template_keys
    )


def test_ensure_default_knowledge_templates_for_user_creates_knowledge_and_all_documents(monkeypatch):
    request = build_request()
    user = build_user()
    inserted_forms: list[object] = []
    linked_file_ids: list[str] = []
    processed_files: list[tuple[str, str]] = []

    created_knowledge = SimpleNamespace(
        id='kb-1',
        user_id=user.id,
        name=DEFAULT_KNOWLEDGE_NAME,
        description='desc',
        meta=None,
    )

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_knowledge_bases_by_user_id',
        lambda user_id, permission='write', db=None: [],
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.insert_new_knowledge',
        lambda user_id, form_data, db=None: created_knowledge,
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.update_knowledge_meta_by_id',
        lambda knowledge_id, meta, db=None: SimpleNamespace(
            id=knowledge_id,
            user_id=user.id,
            name=DEFAULT_KNOWLEDGE_NAME,
            description='desc',
            meta=meta,
        ),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_files_by_id',
        lambda knowledge_id, db=None: [],
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Storage.upload_file',
        lambda file_obj, filename, _tags: (file_obj.read(), f'/tmp/{filename}'),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Files.insert_new_file',
        lambda user_id, form_data, db=None: inserted_forms.append(form_data)
        or SimpleNamespace(id=form_data.id, filename=form_data.filename, meta=form_data.meta),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.process_file',
        lambda request, form_data, user=None, db=None: processed_files.append(
            (form_data.file_id, form_data.collection_name)
        ),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.add_file_to_knowledge_by_id',
        lambda knowledge_id, file_id, user_id, db=None: linked_file_ids.append(file_id),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.embed_default_knowledge_metadata',
        lambda request, knowledge: asyncio.sleep(0, result=True),
    )

    result = asyncio.run(ensure_default_knowledge_templates_for_user(request, user))

    assert result.knowledge_created is True
    assert result.knowledge_id == 'kb-1'
    assert result.created_document_keys == [document.key for document in DEFAULT_SEED_DOCUMENTS]
    assert result.skipped_document_keys == []
    assert result.failed_document_keys == []
    assert len(inserted_forms) == len(DEFAULT_SEED_DOCUMENTS)
    assert linked_file_ids == [form_data.id for form_data in inserted_forms]
    assert processed_files == [(form_data.id, 'kb-1') for form_data in inserted_forms]
    assert inserted_forms[0].meta['seeded_by_system'] is True
    assert inserted_forms[0].meta['seed_document_key'] == 'knowhow-guide'
    assert inserted_forms[0].meta['content_type'] == 'text/markdown'
    assert inserted_forms[0].data['content'].startswith('#')
    assert inserted_forms[3].filename == f'{DEFAULT_SEED_DOCUMENTS[3].title}.md'


def test_ensure_default_knowledge_templates_for_user_only_backfills_missing_documents(monkeypatch):
    request = build_request()
    user = build_user()
    inserted_forms: list[object] = []
    linked_file_ids: list[str] = []

    existing_knowledge = SimpleNamespace(
        id='kb-existing',
        user_id=user.id,
        name='已存在的样板库',
        description='desc',
        meta={
            'seeded_by_system': True,
            'seed_template_key': 'department-knowhow-starter',
            'seed_template_version': DEFAULT_TEMPLATE_VERSION,
        },
    )

    existing_files = [
        make_file('file-1', f'{DEFAULT_SEED_DOCUMENTS[0].title}.md', 'knowhow-guide'),
        make_file('file-2', f'{DEFAULT_SEED_DOCUMENTS[1].title}.md', 'knowhow-fill-template'),
    ]

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_knowledge_bases_by_user_id',
        lambda user_id, permission='write', db=None: [existing_knowledge],
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_files_by_id',
        lambda knowledge_id, db=None: existing_files,
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Storage.upload_file',
        lambda file_obj, filename, _tags: (file_obj.read(), f'/tmp/{filename}'),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Files.insert_new_file',
        lambda user_id, form_data, db=None: inserted_forms.append(form_data)
        or SimpleNamespace(id=form_data.id, filename=form_data.filename, meta=form_data.meta),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.process_file',
        lambda request, form_data, user=None, db=None: None,
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.add_file_to_knowledge_by_id',
        lambda knowledge_id, file_id, user_id, db=None: linked_file_ids.append(file_id),
    )

    result = asyncio.run(ensure_default_knowledge_templates_for_user(request, user))

    assert result.knowledge_created is False
    assert result.knowledge_id == 'kb-existing'
    assert result.created_document_keys == [
        'faq-and-pitfalls',
        'procurement-commercial-boss-review',
        'procurement-classification-governance',
        'knowhow-table-fill',
        'knowhow-table-example',
        'faq-table-fill',
        'faq-table-example',
        'procurement-commercial-table-fill',
        'procurement-commercial-table-example',
        'procurement-classification-table-fill',
        'procurement-classification-table-example',
    ]
    assert result.skipped_document_keys == ['knowhow-guide', 'knowhow-fill-template']
    assert result.failed_document_keys == []
    assert len(inserted_forms) == 11
    assert len(linked_file_ids) == 11


def test_seed_default_knowledge_templates_for_existing_users_aggregates_results(monkeypatch):
    request = build_request()
    users = [build_user('user-1'), build_user('user-2')]

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Users.get_users',
        lambda filter=None, skip=None, limit=None, db=None: {'users': users, 'total': len(users)},
    )

    async def fake_ensure(request, user, db=None):
        if user.id == 'user-1':
            return SimpleNamespace(
                user_id=user.id,
                knowledge_id='kb-1',
                knowledge_created=True,
                created_document_keys=['a', 'b'],
                skipped_document_keys=[],
                failed_document_keys=[],
            )
        raise RuntimeError('seed failed')

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.ensure_default_knowledge_templates_for_user',
        fake_ensure,
    )

    result = asyncio.run(seed_default_knowledge_templates_for_existing_users(request))

    assert result.total_users == 2
    assert result.processed_users == 1
    assert result.created_knowledge_bases == 1
    assert result.created_documents == 2
    assert len(result.failed_users) == 1
    assert result.failed_users[0]['user_id'] == 'user-2'
    assert result.failed_users[0]['error'] == 'seed failed'


def test_ensure_default_knowledge_templates_offloads_seed_document_creation(monkeypatch):
    from open_webui.utils import default_knowledge_initializer as initializer

    request = build_request()
    user = build_user()
    created_keys: list[str] = []
    offloaded_calls: list[str] = []

    created_knowledge = SimpleNamespace(
        id='kb-threaded',
        user_id=user.id,
        name=DEFAULT_KNOWLEDGE_NAME,
        description='desc',
        meta=None,
    )

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_knowledge_bases_by_user_id',
        lambda user_id, permission='write', db=None: [],
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.insert_new_knowledge',
        lambda user_id, form_data, db=None: created_knowledge,
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.update_knowledge_meta_by_id',
        lambda knowledge_id, meta, db=None: SimpleNamespace(
            id=knowledge_id,
            user_id=user.id,
            name=DEFAULT_KNOWLEDGE_NAME,
            description='desc',
            meta=meta,
        ),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.get_files_by_id',
        lambda knowledge_id, db=None: [],
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.embed_default_knowledge_metadata',
        lambda request, knowledge: asyncio.sleep(0, result=True),
    )

    def fake_create_seed_document_file(request, knowledge, template, user, db=None):
        created_keys.append(template.key)
        return SimpleNamespace(id=template.key)

    async def fake_to_thread(func, *args, **kwargs):
        offloaded_calls.append(getattr(func, '__name__', str(func)))
        return func(*args, **kwargs)

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer._create_seed_document_file',
        fake_create_seed_document_file,
    )
    monkeypatch.setattr(initializer.asyncio, 'to_thread', fake_to_thread)

    result = asyncio.run(ensure_default_knowledge_templates_for_user(request, user))

    assert result.created_document_keys == [document.key for document in DEFAULT_SEED_DOCUMENTS]
    assert created_keys == [document.key for document in DEFAULT_SEED_DOCUMENTS]
    assert offloaded_calls == ['fake_create_seed_document_file'] * len(DEFAULT_SEED_DOCUMENTS)


def test_create_seed_document_file_uses_db_context_when_none_provided(monkeypatch):
    from open_webui.utils import default_knowledge_initializer as initializer

    request = build_request()
    user = build_user()
    knowledge = SimpleNamespace(id='kb-seed')
    captured = {}

    @contextmanager
    def fake_get_db():
        yield 'db-session'

    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Storage.upload_file',
        lambda file_obj, filename, _tags: (file_obj.read(), f'/tmp/{filename}'),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Files.insert_new_file',
        lambda user_id, form_data, db=None: SimpleNamespace(
            id=form_data.id,
            filename=form_data.filename,
            meta=form_data.meta,
        ),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.Knowledges.add_file_to_knowledge_by_id',
        lambda knowledge_id, file_id, user_id, db=None: captured.setdefault('linked_file_id', file_id),
    )
    monkeypatch.setattr(
        'open_webui.utils.default_knowledge_initializer.process_file',
        lambda request, form_data, user=None, db=None: captured.setdefault('db', db),
    )
    monkeypatch.setattr(initializer, 'get_db', fake_get_db)

    initializer._create_seed_document_file(request, knowledge, DEFAULT_SEED_DOCUMENTS[0], user)

    assert captured['db'] == 'db-session'
