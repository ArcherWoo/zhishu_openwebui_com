# 默认禁用 Ollama 实施计划

> **给代理工作者：** 必须使用子技能 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项落实本计划。步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 默认禁用 Ollama，停止默认的 localhost 探测，并在禁用时隐藏 Ollama UI，同时保留管理员的模型管理访问能力。

**架构：** 后端成为唯一真实来源：将 `ENABLE_OLLAMA_API` 默认设为 `False`，并通过 `/api/config` 导出该状态。前端消费这个功能开关，在不改变管理员访问工作区模型页面权限的前提下，屏蔽仅 Ollama 相关的 UI。

**技术栈：** Python、FastAPI、Svelte、TypeScript、通过 `svelte-check` 做无 Vitest 的前端验证、Pytest。

---

### 任务 1：添加失败中的后端回归测试

**文件：**
- 创建：`tests/test_ollama_disable_config.py`
- 测试：`tests/test_ollama_disable_config.py`

- [ ] **步骤 1：编写失败中的测试**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ollama_is_disabled_by_default_and_exposed_to_frontend():
    config_source = (ROOT / 'backend' / 'open_webui' / 'config.py').read_text(encoding='utf-8')
    main_source = (ROOT / 'backend' / 'open_webui' / 'main.py').read_text(encoding='utf-8')

    assert "os.environ.get('ENABLE_OLLAMA_API', 'False').lower() == 'true'" in config_source
    assert "'enable_ollama_api': app.state.config.ENABLE_OLLAMA_API" in main_source
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_ollama_disable_config.py -q`
预期：`FAIL`，因为后端当前仍将 Ollama 默认设为 `True`，且 `/api/config` 还没有暴露 `enable_ollama_api`。

- [ ] **步骤 3：编写最小实现**

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

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_ollama_disable_config.py -q`
预期：`1 passed`

- [ ] **步骤 5：提交**

```bash
git add tests/test_ollama_disable_config.py backend/open_webui/config.py backend/open_webui/main.py
git commit -m "Disable Ollama by default"
```

### 任务 2：用后端功能开关隐藏 Ollama UI

**文件：**
- 修改：`src/lib/stores/index.ts`
- 修改：`src/lib/components/admin/Settings/Connections.svelte`
- 修改：`src/lib/components/admin/Settings/Models/ManageModelsModal.svelte`
- 修改：`src/lib/components/chat/Settings/About.svelte`
- 修改：`src/lib/components/admin/Settings/Documents.svelte`

- [ ] **步骤 1：补充前端配置类型字段**

```ts
enable_ollama_api?: boolean;
```

- [ ] **步骤 2：为管理员 Connections 中的 Ollama 区块加开关**

```svelte
{#if $config?.features?.enable_ollama_api}
  <!-- existing Ollama settings block -->
{/if}
```

- [ ] **步骤 3：为模型管理弹窗加开关**

```svelte
if (ollamaConfig?.ENABLE_OLLAMA_API) {
	selected = 'ollama';
	return;
}

selected = '';
```

- [ ] **步骤 4：在禁用时跳过关于页面的 Ollama 版本请求**

```svelte
if ($config?.features?.enable_ollama_api) {
	ollamaVersion = await getOllamaVersion(localStorage.token).catch(() => '');
}
```

- [ ] **步骤 5：移除被禁用状态下的 Ollama 嵌入选项**

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

- [ ] **步骤 6：运行前端验证**

运行：`npm run check`
预期：`svelte-check` 在修改的文件上没有新增错误。

- [ ] **步骤 7：提交**

```bash
git add src/lib/stores/index.ts src/lib/components/admin/Settings/Connections.svelte src/lib/components/admin/Settings/Models/ManageModelsModal.svelte src/lib/components/chat/Settings/About.svelte src/lib/components/admin/Settings/Documents.svelte
git commit -m "Hide Ollama UI when disabled"
```

### 任务 3：最终验证

**文件：**
- 修改：无
- 测试：`tests/test_ollama_disable_config.py`
- 测试：`tests/test_start.py`

- [ ] **步骤 1：运行后端回归测试**

运行：`.\.venv\Scripts\python.exe -m pytest tests/test_ollama_disable_config.py tests/test_start.py -q`
预期：所有测试通过。

- [ ] **步骤 2：运行语法验证**

运行：`.\.venv\Scripts\python.exe -m py_compile backend\open_webui\config.py backend\open_webui\main.py`
预期：无输出，退出码为 `0`。

- [ ] **步骤 3：运行前端验证**

运行：`npm run check`
预期：没有新增 `svelte-check` 错误。

- [ ] **步骤 4：检查工作区状态**

运行：`git status --short`
预期：最终提交前只出现预期修改的文件；提交后工作区干净。

- [ ] **步骤 5：提交**

```bash
git add docs/superpowers/specs/2026-04-13-disable-ollama-design.md docs/superpowers/plans/2026-04-13-disable-ollama.md
git commit -m "Document Ollama disable plan"
```
