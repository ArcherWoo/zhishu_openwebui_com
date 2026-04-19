from __future__ import annotations

import asyncio

import pytest

from open_webui.retrieval.utils import get_embedding_function


def test_sentence_transformer_embedding_function_reports_missing_local_model_clearly():
    embedding_function = get_embedding_function(
        embedding_engine='',
        embedding_model='sentence-transformers/all-MiniLM-L6-v2',
        embedding_function=None,
        url='',
        key='',
        embedding_batch_size=8,
    )

    with pytest.raises(RuntimeError, match='Embedding model is not loaded'):
        asyncio.run(embedding_function(['test']))
