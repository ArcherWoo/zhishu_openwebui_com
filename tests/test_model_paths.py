from __future__ import annotations

import importlib
import tempfile
from pathlib import Path


def test_find_local_embedding_model_path_supports_repo_relative_model_layout():
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_root = Path(temp_dir) / 'repo'
        model_dir = repo_root / 'embedding_model' / 'sentence-transformers' / 'all-MiniLM-L6-v2'
        model_dir.mkdir(parents=True)

        model_paths = importlib.import_module('open_webui.utils.model_paths')

        resolved = model_paths.find_local_embedding_model_path(
            'sentence-transformers/all-MiniLM-L6-v2',
            base_dir=repo_root,
            env={},
        )

        assert Path(resolved).resolve() == model_dir.resolve()
