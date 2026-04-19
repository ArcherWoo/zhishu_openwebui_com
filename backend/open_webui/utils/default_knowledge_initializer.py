from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from open_webui.models.files import FileForm, FileModel, Files
from open_webui.internal.db import get_db
from open_webui.models.knowledge import KnowledgeForm, KnowledgeModel, Knowledges
from open_webui.models.users import Users
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.routers.retrieval import ProcessFileForm, process_file
from open_webui.storage.provider import Storage
from open_webui.utils.default_knowledge_templates import (
    DEFAULT_KNOWLEDGE_DESCRIPTION,
    DEFAULT_KNOWLEDGE_NAME,
    DEFAULT_SEED_DOCUMENTS,
    DEFAULT_TEMPLATE_KEY,
    DEFAULT_TEMPLATE_VERSION,
    SeedDocumentTemplate,
)

log = logging.getLogger(__name__)

KNOWLEDGE_BASES_COLLECTION = 'knowledge-bases'


@dataclass(slots=True)
class SeedInitializationResult:
    user_id: str
    knowledge_id: str | None
    knowledge_created: bool
    created_document_keys: list[str] = field(default_factory=list)
    skipped_document_keys: list[str] = field(default_factory=list)
    failed_document_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SeedBackfillResult:
    total_users: int
    processed_users: int
    created_knowledge_bases: int
    created_documents: int
    failed_users: list[dict[str, str]] = field(default_factory=list)


def _seed_meta() -> dict[str, Any]:
    return {
        'seeded_by_system': True,
        'seed_template_key': DEFAULT_TEMPLATE_KEY,
        'seed_template_version': DEFAULT_TEMPLATE_VERSION,
    }


def _get_seed_document_key(file: FileModel) -> str | None:
    meta = file.meta or {}
    if meta.get('seed_document_key'):
        return meta.get('seed_document_key')

    data = meta.get('data')
    if isinstance(data, dict):
        return data.get('seed_document_key')

    return None


def find_seeded_knowledge_base(user_id: str, db=None) -> KnowledgeModel | Any | None:
    knowledge_bases = Knowledges.get_knowledge_bases_by_user_id(user_id, db=db)
    for knowledge_base in knowledge_bases:
        meta = getattr(knowledge_base, 'meta', None) or {}
        if meta.get('seed_template_key') == DEFAULT_TEMPLATE_KEY:
            return knowledge_base
    return None


def _sanitize_storage_basename(value: str) -> str:
    sanitized = re.sub(r'[<>:"/\\\\|?*]+', '-', value).strip().strip('.')
    return sanitized or 'seed-document'


def _create_seed_document_file(request, knowledge, template: SeedDocumentTemplate, user, db=None):
    document_filename = f'{template.title}.md'
    storage_filename = f'{uuid.uuid4()}_{_sanitize_storage_basename(template.title)}.md'
    storage_tags = {
        'OpenWebUI-User-Email': user.email,
        'OpenWebUI-User-Id': user.id,
        'OpenWebUI-User-Name': user.name,
        'OpenWebUI-Seed-Template-Key': DEFAULT_TEMPLATE_KEY,
    }
    content_bytes = template.content.encode('utf-8')
    _, file_path = Storage.upload_file(io.BytesIO(content_bytes), storage_filename, storage_tags)

    file_item = Files.insert_new_file(
        user.id,
        FileForm(
            id=str(uuid.uuid4()),
            filename=document_filename,
            path=file_path,
            data={
                'status': 'pending',
                'content': template.content,
            },
            meta={
                'name': document_filename,
                'content_type': 'text/markdown',
                'size': len(content_bytes),
                **_seed_meta(),
                'seed_document_key': template.key,
            },
        ),
        db=db,
    )
    if not file_item:
        raise RuntimeError(f'Failed to create default seed document: {template.key}')

    if db is not None:
        process_file(
            request,
            ProcessFileForm(file_id=file_item.id, collection_name=knowledge.id),
            user=user,
            db=db,
        )
    else:
        with get_db() as process_db:
            process_file(
                request,
                ProcessFileForm(file_id=file_item.id, collection_name=knowledge.id),
                user=user,
                db=process_db,
            )

    Knowledges.add_file_to_knowledge_by_id(knowledge.id, file_item.id, user.id, db=db)
    return file_item


async def embed_default_knowledge_metadata(request, knowledge) -> bool:
    embedding_function = getattr(request.app.state, 'EMBEDDING_FUNCTION', None)
    if embedding_function is None or getattr(request.app.state.config, 'BYPASS_EMBEDDING_AND_RETRIEVAL', False):
        return False

    try:
        content = f'{knowledge.name}\n\n{knowledge.description}' if knowledge.description else knowledge.name
        embedding = await embedding_function(content)
        VECTOR_DB_CLIENT.upsert(
            collection_name=KNOWLEDGE_BASES_COLLECTION,
            items=[
                {
                    'id': knowledge.id,
                    'text': content,
                    'vector': embedding,
                    'metadata': {
                        'knowledge_base_id': knowledge.id,
                    },
                }
            ],
        )
        return True
    except Exception as exc:
        log.warning('Failed to embed default knowledge metadata for %s: %s', knowledge.id, exc)
        return False


async def ensure_default_knowledge_templates_for_user(request, user, db=None) -> SeedInitializationResult:
    knowledge = find_seeded_knowledge_base(user.id, db=db)
    knowledge_created = False

    if knowledge is None:
        knowledge = Knowledges.insert_new_knowledge(
            user.id,
            KnowledgeForm(
                name=DEFAULT_KNOWLEDGE_NAME,
                description=DEFAULT_KNOWLEDGE_DESCRIPTION,
            ),
            db=db,
        )
        if not knowledge:
            raise RuntimeError(f'Failed to create default knowledge base for user {user.id}')

        updated_knowledge = Knowledges.update_knowledge_meta_by_id(
            knowledge.id,
            _seed_meta(),
            db=db,
        )
        knowledge = updated_knowledge or knowledge
        knowledge_created = True
        await embed_default_knowledge_metadata(request, knowledge)

    existing_files = Knowledges.get_files_by_id(knowledge.id, db=db)
    existing_seed_keys = {
        seed_document_key for file in existing_files if (seed_document_key := _get_seed_document_key(file)) is not None
    }

    result = SeedInitializationResult(
        user_id=user.id,
        knowledge_id=knowledge.id,
        knowledge_created=knowledge_created,
    )

    for template in DEFAULT_SEED_DOCUMENTS:
        if template.key in existing_seed_keys:
            result.skipped_document_keys.append(template.key)
            continue

        try:
            await asyncio.to_thread(
                _create_seed_document_file,
                request,
                knowledge,
                template,
                user,
            )
            result.created_document_keys.append(template.key)
        except Exception as exc:
            log.warning(
                'Failed to seed default knowledge document %s for user %s: %s',
                template.key,
                user.id,
                exc,
            )
            result.failed_document_keys.append(template.key)

    return result


async def seed_default_knowledge_templates_for_existing_users(request, db=None) -> SeedBackfillResult:
    users_result = Users.get_users(db=db)
    users = users_result.get('users', []) if isinstance(users_result, dict) else []

    result = SeedBackfillResult(
        total_users=len(users),
        processed_users=0,
        created_knowledge_bases=0,
        created_documents=0,
    )

    for user in users:
        try:
            seed_result = await ensure_default_knowledge_templates_for_user(request, user, db=db)
            result.processed_users += 1
            if seed_result.knowledge_created:
                result.created_knowledge_bases += 1
            result.created_documents += len(seed_result.created_document_keys)
        except Exception as exc:
            log.warning('Failed to seed default knowledge templates for user %s: %s', user.id, exc)
            result.failed_users.append(
                {
                    'user_id': user.id,
                    'error': str(exc),
                }
            )

    return result
