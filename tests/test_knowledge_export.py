from __future__ import annotations

import asyncio
import io
import zipfile
from types import SimpleNamespace

from open_webui.routers import knowledge as knowledge_router


async def _read_streaming_response_body(response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b''.join(chunks)


def test_export_knowledge_by_id_converts_text_files_to_markdown(monkeypatch):
    knowledge = SimpleNamespace(id='kb-1', name='部门知识库')
    files = [
        SimpleNamespace(filename='legacy-note.txt', data={'content': '# Legacy'}),
        SimpleNamespace(filename='already-markdown.md', data={'content': '# Markdown'}),
        SimpleNamespace(filename='plain-name', data={'content': '# Plain'}),
        SimpleNamespace(filename='empty.txt', data={'content': ''}),
    ]

    monkeypatch.setattr(
        knowledge_router.Knowledges,
        'get_knowledge_by_id',
        lambda id, db=None: knowledge,
    )
    monkeypatch.setattr(
        knowledge_router.Knowledges,
        'get_files_by_id',
        lambda knowledge_id, db=None: files,
    )

    response = asyncio.run(
        knowledge_router.export_knowledge_by_id(
            'kb-1',
            user=SimpleNamespace(role='admin'),
            db=None,
        )
    )
    body = asyncio.run(_read_streaming_response_body(response))

    with zipfile.ZipFile(io.BytesIO(body), 'r') as archive:
        names = sorted(archive.namelist())

    assert names == ['already-markdown.md', 'legacy-note.md', 'plain-name.md']
