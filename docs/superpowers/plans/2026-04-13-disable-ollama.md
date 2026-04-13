# Disable Ollama By Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable Ollama by default, stop default localhost probing, and hide Ollama UI when disabled while preserving admin model-management access.

**Architecture:** The backend becomes the source of truth by defaulting `ENABLE_OLLAMA_API` to `False` and exporting that state through `/api/config`. The frontend consumes that feature flag to suppress Ollama-only UI without altering admin access to workspace model pages.

**Tech Stack:** Python, FastAPI, Svelte, TypeScript, Vitest-free frontend verification via `svelte-check`, Pytest.

---

### Task 1: Add Failing Backend Regression Test

**Files:**
- Create: `tests/test_ollama_disable_config.py`
- Test: `tests/test_ollama_disable_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ollama_is_disabled_by_default_and_exposed_to_frontend():
    config_source = (ROOT / 'backend' / 'open_webui' / 'config.py').read_text(encoding='utf-8')
    main_source = (ROOT / 'backend' / 'open_webui' / 'main.py').read_text(encoding='utf-8')

    assert "os.environ.get('ENABLE_OLLAMA_API', 'False').lower() == 'true'" in config_source
    assert "'enable_ollama_api': app.state.config.ENABLE_OLLAMA_API" in main_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ollama_disable_config.py -q`
Expected: `FAIL` because the backend still defaults Ollama to `True` and `/api/config` does not yet expose `enable_ollama_api`.

- [ ] **Step 3: Write minimal implementation**

```python
ENABLE_OLLAMA_API = PersistentConfig(
    'ENABLE_OLLAMA_API',
    'ollama.enable',
    os.environ.get('ENABLE_OLLAMA_API', 'False').lower() == 'true',
)
```

```python
'enable_ollama_api': app.state.config.ENABLE_OLLAMA_API,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ollama_disable_config.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_ollama_disable_config.py backend/open_webui/config.py backend/open_webui/main.py
git commit -m "Disable Ollama by default"
```

### Task 2: Hide Ollama UI Behind Backend Feature Flag

**Files:**
- Modify: `src/lib/stores/index.ts`
- Modify: `src/lib/components/admin/Settings/Connections.svelte`
- Modify: `src/lib/components/admin/Settings/Models/ManageModelsModal.svelte`
- Modify: `src/lib/components/chat/Settings/About.svelte`
- Modify: `src/lib/components/admin/Settings/Documents.svelte`

- [ ] **Step 1: Add the frontend config type field**

```ts
enable_ollama_api?: boolean;
```

- [ ] **Step 2: Gate the admin Connections Ollama section**

```svelte
{#if $config?.features?.enable_ollama_api}
  <!-- existing Ollama settings block -->
{/if}
```

- [ ] **Step 3: Gate the Manage Models modal**

```svelte
if (ollamaConfig?.ENABLE_OLLAMA_API) {
	selected = 'ollama';
	return;
}

selected = '';
```

- [ ] **Step 4: Skip the About-page Ollama version request when disabled**

```svelte
if ($config?.features?.enable_ollama_api) {
	ollamaVersion = await getOllamaVersion(localStorage.token).catch(() => '');
}
```

- [ ] **Step 5: Remove the disabled Ollama embedding choice**

```svelte
{#if $config?.features?.enable_ollama_api}
	<option value="ollama">{$i18n.t('Ollama')}</option>
{/if}
```

```svelte
if (!$config?.features?.enable_ollama_api && RAG_EMBEDDING_ENGINE === 'ollama') {
	RAG_EMBEDDING_ENGINE = '';
	RAG_EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2';
}
```

- [ ] **Step 6: Run frontend verification**

Run: `npm run check`
Expected: `svelte-check` completes without new errors in the modified files.

- [ ] **Step 7: Commit**

```bash
git add src/lib/stores/index.ts src/lib/components/admin/Settings/Connections.svelte src/lib/components/admin/Settings/Models/ManageModelsModal.svelte src/lib/components/chat/Settings/About.svelte src/lib/components/admin/Settings/Documents.svelte
git commit -m "Hide Ollama UI when disabled"
```

### Task 3: Final Verification

**Files:**
- Modify: none
- Test: `tests/test_ollama_disable_config.py`
- Test: `tests/test_start.py`

- [ ] **Step 1: Run backend regression tests**

Run: `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ollama_disable_config.py tests/test_start.py -q`
Expected: all tests pass.

- [ ] **Step 2: Run syntax verification**

Run: `.\\.venv\\Scripts\\python.exe -m py_compile backend\\open_webui\\config.py backend\\open_webui\\main.py`
Expected: no output and exit code `0`.

- [ ] **Step 3: Run frontend verification**

Run: `npm run check`
Expected: no new `svelte-check` errors.

- [ ] **Step 4: Review worktree**

Run: `git status --short`
Expected: only intended modified files appear before the final commit, then a clean worktree after commit.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-13-disable-ollama-design.md docs/superpowers/plans/2026-04-13-disable-ollama.md
git commit -m "Document Ollama disable plan"
```
