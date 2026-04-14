from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping


def _repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[3]


def get_embedding_model_dir(
    *,
    base_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    env_map = os.environ if env is None else env
    configured_dir = env_map.get('EMBEDDING_MODEL_DIR', '').strip()
    if configured_dir:
        return Path(configured_dir).expanduser().resolve()

    root = Path(base_dir).resolve() if base_dir is not None else _repo_root_from_module()
    return (root / 'embedding_model').resolve()


def iter_local_model_roots(
    *,
    base_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Iterable[Path]:
    env_map = os.environ if env is None else env

    candidates = [
        env_map.get('EMBEDDING_MODEL_DIR', '').strip(),
        env_map.get('SENTENCE_TRANSFORMERS_HOME', '').strip(),
        env_map.get('HF_HOME', '').strip(),
        str(get_embedding_model_dir(base_dir=base_dir, env=env_map)),
    ]

    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        yield path


def _model_relative_path(model: str) -> Path:
    parts = [part for part in model.replace('\\', '/').split('/') if part]
    return Path(*parts)


def _latest_snapshot_dir(repo_cache_dir: Path) -> str | None:
    snapshots_dir = repo_cache_dir / 'snapshots'
    if not snapshots_dir.is_dir():
        return None

    snapshot_dirs = [path for path in snapshots_dir.iterdir() if path.is_dir()]
    if not snapshot_dirs:
        return None

    snapshot_dirs.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return str(snapshot_dirs[0])


def find_local_embedding_model_path(
    model: str,
    *,
    base_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    if not model:
        return None

    explicit_path = Path(model)
    if explicit_path.exists():
        return str(explicit_path.resolve())

    normalized_model = model.replace('\\', '/')
    relative_model_path = _model_relative_path(model)
    repo_cache_name = f"models--{normalized_model.replace('/', '--')}"

    for root in iter_local_model_roots(base_dir=base_dir, env=env):
        direct_path = root / relative_model_path
        if direct_path.exists():
            return str(direct_path)

        for cache_root in (root, root / 'hub'):
            snapshot_path = _latest_snapshot_dir(cache_root / repo_cache_name)
            if snapshot_path:
                return snapshot_path

    return None
