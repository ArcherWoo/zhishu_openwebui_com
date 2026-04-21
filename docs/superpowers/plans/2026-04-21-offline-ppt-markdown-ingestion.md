# Offline PPT Markdown Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `Windows + CPU` 的公司内网环境中，为 `.pptx` 和 `.ppt` 提供本地离线的 Markdown 解析链路，并稳定进入现有向量库与问答流程。

**Architecture:** 保持现有上传、解密、向量化主干不变，只替换 PowerPoint loader 选择层。`.pptx` 直接走本地 `MarkItDown`，`.ppt` 先用本机 `soffice` 转成临时 `.pptx`，再统一交给 `MarkItDown`；主路径失败时退回 `python-pptx` fallback，并显式记录日志与失败状态。

**Tech Stack:** Python, FastAPI backend, pytest, MarkItDown, python-pptx, LibreOffice/soffice

---

### Task 1: 为 PowerPoint 解析新增测试骨架

**Files:**
- Create: `backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py`
- Modify: `backend/open_webui/retrieval/loaders/main.py`

- [ ] **Step 1: 写出 PowerPoint loader 路由失败测试**

```python
from pathlib import Path

from open_webui.retrieval.loaders.main import Loader


def test_loader_routes_pptx_to_powerpoint_markdown_loader(monkeypatch, tmp_path):
    target = {}

    class DummyPowerPointMarkdownLoader:
        def __init__(self, file_path, filename, content_type, **kwargs):
            target["loader"] = "powerpoint_markdown"
            target["file_path"] = file_path
            target["filename"] = filename
            target["content_type"] = content_type

        def load(self):
            raise AssertionError("route confirmed")

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.main.PowerPointMarkdownLoader",
        DummyPowerPointMarkdownLoader,
    )

    sample = tmp_path / "sample.pptx"
    sample.write_bytes(b"pptx")

    loader = Loader(engine="")

    try:
        loader.load(
            sample.name,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            str(sample),
        )
    except AssertionError as exc:
        assert str(exc) == "route confirmed"

    assert target == {
        "loader": "powerpoint_markdown",
        "file_path": str(sample),
        "filename": sample.name,
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
FAIL ... PowerPointMarkdownLoader not found ...
```

- [ ] **Step 3: 在 `main.py` 中先引入占位 loader 以让导入路径成立**

```python
try:
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader
except ImportError:  # pragma: no cover - implemented in later task
    PowerPointMarkdownLoader = None
```

- [ ] **Step 4: 再次运行测试，确认失败原因转为“类存在但行为未实现”**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
FAIL ... route still points to old UnstructuredPowerPointLoader ...
```

- [ ] **Step 5: 提交**

```bash
git add backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py backend/open_webui/retrieval/loaders/main.py
git commit -m "test: add powerpoint loader routing coverage"
```

### Task 2: 实现 `.ppt/.pptx` 的统一 PowerPointMarkdownLoader

**Files:**
- Create: `backend/open_webui/retrieval/loaders/powerpoint_markdown.py`
- Create: `backend/open_webui/retrieval/loaders/powerpoint_converter.py`
- Create: `backend/open_webui/retrieval/loaders/powerpoint_fallback.py`
- Modify: `backend/open_webui/retrieval/loaders/main.py`
- Test: `backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py`

- [ ] **Step 1: 补充 `.pptx` 主路径与 `.ppt` 转换路径的失败测试**

```python
from langchain_core.documents import Document


def test_powerpoint_markdown_loader_uses_markitdown_for_pptx(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "deck.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            assert file_path == str(sample)
            assert timeout_seconds == 120

        def load_markdown(self):
            return "# Title\n\n- item"

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        markitdown_timeout_seconds=120,
    ).load()

    assert docs == [
        Document(
            page_content="# Title\n\n- item",
            metadata={
                "source": sample.name,
                "content_format": "markdown",
                "parsed_by": "markitdown",
                "original_extension": "pptx",
            },
        )
    ]
```

```python
def test_powerpoint_markdown_loader_converts_ppt_before_markitdown(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "legacy.ppt"
    converted = tmp_path / "legacy.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyConverter:
        def __init__(self, command, timeout_seconds):
            assert command == "soffice"
            assert timeout_seconds == 120

        def convert(self, input_path):
            assert input_path == str(sample)
            converted.write_text("converted", encoding="utf-8")
            return str(converted)

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            assert file_path == str(converted)
            assert timeout_seconds == 120

        def load_markdown(self):
            return "# Converted"

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointConverter",
        DummyConverter,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.ms-powerpoint",
        converter_command="soffice",
        converter_timeout_seconds=120,
        markitdown_timeout_seconds=120,
    ).load()

    assert docs[0].page_content == "# Converted"
    assert docs[0].metadata["converted_from_ppt"] is True
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
FAIL ... ModuleNotFoundError for powerpoint_markdown / missing classes ...
```

- [ ] **Step 3: 实现 `PowerPointConverter`**

```python
import shutil
import subprocess
import tempfile
from pathlib import Path


class PowerPointConversionError(RuntimeError):
    pass


class PowerPointConverter:
    def __init__(self, command: str = "soffice", timeout_seconds: int = 120):
        self.command = command
        self.timeout_seconds = timeout_seconds

    def convert(self, input_path: str) -> str:
        if shutil.which(self.command) is None:
            raise PowerPointConversionError(f"{self.command} not found")

        source = Path(input_path)
        if source.suffix.lower() != ".ppt":
            raise PowerPointConversionError("converter only accepts .ppt")

        temp_dir = Path(tempfile.mkdtemp(prefix="ppt-convert-"))

        subprocess.run(
            [
                self.command,
                "--headless",
                "--convert-to",
                "pptx",
                "--outdir",
                str(temp_dir),
                str(source),
            ],
            check=True,
            timeout=self.timeout_seconds,
        )

        converted = temp_dir / f"{source.stem}.pptx"
        if not converted.exists():
            raise PowerPointConversionError("converted pptx not found")

        return str(converted)
```

- [ ] **Step 4: 实现 `PowerPointFallbackLoader`**

```python
from langchain_core.documents import Document
from pptx import Presentation


class PowerPointFallbackLoader:
    def __init__(self, file_path: str, filename: str):
        self.file_path = file_path
        self.filename = filename

    def load(self) -> list[Document]:
        prs = Presentation(self.file_path)
        sections = []
        for idx, slide in enumerate(prs.slides, start=1):
            texts = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    text = shape.text_frame.text.strip()
                    if text:
                        texts.append(text)
            if texts:
                sections.append(f"# Slide {idx}\n\n" + "\n\n".join(texts))

        return [
            Document(
                page_content="\n\n".join(sections).strip(),
                metadata={
                    "source": self.filename,
                    "content_format": "markdown",
                    "parsed_by": "python-pptx-fallback",
                    "original_extension": self.filename.split(".")[-1].lower(),
                },
            )
        ]
```

- [ ] **Step 5: 实现 `PowerPointMarkdownLoader`**

```python
import logging
from pathlib import Path

from langchain_core.documents import Document

from open_webui.retrieval.loaders.powerpoint_converter import (
    PowerPointConverter,
    PowerPointConversionError,
)
from open_webui.retrieval.loaders.powerpoint_fallback import PowerPointFallbackLoader

log = logging.getLogger(__name__)


class MarkItDownPowerPointLoader:
    def __init__(self, file_path: str, timeout_seconds: int = 120):
        self.file_path = file_path
        self.timeout_seconds = timeout_seconds

    def load_markdown(self) -> str:
        from markitdown import MarkItDown

        result = MarkItDown().convert(self.file_path)
        text = getattr(result, "text_content", None) or getattr(result, "markdown", None) or ""
        return str(text).strip()


class PowerPointMarkdownLoader:
    def __init__(
        self,
        file_path: str,
        filename: str,
        content_type: str | None,
        converter_command: str = "soffice",
        converter_timeout_seconds: int = 120,
        markitdown_timeout_seconds: int = 120,
        fallback_enabled: bool = True,
    ):
        self.file_path = file_path
        self.filename = filename
        self.content_type = content_type
        self.converter_command = converter_command
        self.converter_timeout_seconds = converter_timeout_seconds
        self.markitdown_timeout_seconds = markitdown_timeout_seconds
        self.fallback_enabled = fallback_enabled

    def load(self) -> list[Document]:
        suffix = Path(self.filename).suffix.lower()
        target_path = self.file_path
        converted_from_ppt = False

        try:
            if suffix == ".ppt":
                log.info("Starting PPT to PPTX conversion for %s", self.filename)
                target_path = PowerPointConverter(
                    command=self.converter_command,
                    timeout_seconds=self.converter_timeout_seconds,
                ).convert(self.file_path)
                converted_from_ppt = True

            markdown = MarkItDownPowerPointLoader(
                file_path=target_path,
                timeout_seconds=self.markitdown_timeout_seconds,
            ).load_markdown()

            if not markdown:
                raise ValueError("PowerPoint markdown content is empty")

            metadata = {
                "source": self.filename,
                "content_format": "markdown",
                "parsed_by": "markitdown",
                "original_extension": suffix.lstrip("."),
            }
            if converted_from_ppt:
                metadata["converted_from_ppt"] = True

            return [Document(page_content=markdown, metadata=metadata)]
        except Exception:
            log.exception("PowerPoint markdown loader failed for %s", self.filename)
            if not self.fallback_enabled:
                raise

            fallback_path = target_path if Path(target_path).suffix.lower() == ".pptx" else self.file_path
            return PowerPointFallbackLoader(file_path=fallback_path, filename=self.filename).load()
```

- [ ] **Step 6: 在 `main.py` 中切换 PowerPoint 路由**

```python
elif file_content_type in [
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
] or file_ext in ['ppt', 'pptx']:
    loader = PowerPointMarkdownLoader(
        file_path=file_path,
        filename=filename,
        content_type=file_content_type,
        converter_command=self.kwargs.get('PPT_CONVERTER_COMMAND', 'soffice'),
        converter_timeout_seconds=int(self.kwargs.get('PPT_CONVERTER_TIMEOUT_SECONDS', 120)),
        markitdown_timeout_seconds=int(self.kwargs.get('PPT_MARKITDOWN_TIMEOUT_SECONDS', 120)),
        fallback_enabled=bool(self.kwargs.get('PPT_FALLBACK_ENABLED', True)),
    )
```

- [ ] **Step 7: 运行测试，确认通过**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
... 3 passed
```

- [ ] **Step 8: 提交**

```bash
git add backend/open_webui/retrieval/loaders/main.py backend/open_webui/retrieval/loaders/powerpoint_markdown.py backend/open_webui/retrieval/loaders/powerpoint_converter.py backend/open_webui/retrieval/loaders/powerpoint_fallback.py backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py
git commit -m "feat: add offline powerpoint markdown loader"
```

### Task 3: 为失败状态和日志补回归测试

**Files:**
- Modify: `backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py`
- Modify: `backend/open_webui/retrieval/loaders/powerpoint_markdown.py`

- [ ] **Step 1: 写 fallback 与 clear failure 的测试**

```python
def test_powerpoint_markdown_loader_uses_fallback_after_markitdown_failure(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader
    from langchain_core.documents import Document

    sample = tmp_path / "broken.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            pass

        def load_markdown(self):
            raise RuntimeError("markitdown failed")

    class DummyFallbackLoader:
        def __init__(self, file_path, filename):
            assert file_path == str(sample)
            assert filename == sample.name

        def load(self):
            return [Document(page_content="# fallback", metadata={"parsed_by": "python-pptx-fallback"})]

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointFallbackLoader",
        DummyFallbackLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ).load()

    assert docs[0].page_content == "# fallback"
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
FAIL ... fallback path not covered yet ...
```

- [ ] **Step 3: 最小化补全日志与 fallback 行为**

```python
log.info("Starting PowerPoint parse for %s", self.filename)
...
log.info("MarkItDown parse succeeded for %s", self.filename)
...
log.warning("Falling back to python-pptx for %s", self.filename)
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
.... 4 passed
```

- [ ] **Step 5: 提交**

```bash
git add backend/open_webui/retrieval/loaders/powerpoint_markdown.py backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py
git commit -m "test: cover powerpoint fallback behavior"
```

### Task 4: 补启动配置与离线部署文档

**Files:**
- Modify: `start.py`
- Create: `ppt_runtime/README.md`
- Modify: `backend/open_webui/retrieval/loaders/main.py`

- [ ] **Step 1: 写配置默认值的失败测试或自检脚本**

```python
# Use an inline verification script instead of pytest for start.py env defaults.
import os
from start import build_runtime_env

env = build_runtime_env(os.environ.copy())

assert env["PPT_CONVERTER_COMMAND"] == "soffice"
assert env["PPT_CONVERTER_TIMEOUT_SECONDS"] == "120"
assert env["PPT_MARKITDOWN_TIMEOUT_SECONDS"] == "120"
assert env["PPT_FALLBACK_ENABLED"] == "True"
```

- [ ] **Step 2: 运行脚本，确认当前失败**

Run:

```powershell
@'
import os
from start import build_runtime_env
env = build_runtime_env(os.environ.copy())
print(env.get("PPT_CONVERTER_COMMAND"))
'@ | .\.venv\Scripts\python.exe -
```

Expected:

```text
None
```

- [ ] **Step 3: 在 `start.py` 增加默认环境变量**

```python
    env.setdefault('PPT_CONVERTER_COMMAND', 'soffice')
    env.setdefault('PPT_CONVERTER_TIMEOUT_SECONDS', '120')
    env.setdefault('PPT_MARKITDOWN_TIMEOUT_SECONDS', '120')
    env.setdefault('PPT_FALLBACK_ENABLED', 'True')
```

- [ ] **Step 4: 编写 `ppt_runtime/README.md`**

```md
# PPT 离线运行时说明

## 目标

让公司内网的 `Windows + CPU` 服务器在不访问外网的情况下，支持 `.pptx` 与 `.ppt` 解析成 Markdown。

## 需要准备的东西

1. `MarkItDown` 离线 Python 包
2. `MarkItDown[pptx]` 相关依赖
3. `LibreOffice` Windows 离线安装包

## 自检命令

```powershell
python -c "import markitdown; print('markitdown ok')"
soffice --version
```
```

- [ ] **Step 5: 运行配置自检，确认通过**

Run:

```powershell
@'
import os
from start import build_runtime_env
env = build_runtime_env(os.environ.copy())
for key in ["PPT_CONVERTER_COMMAND", "PPT_CONVERTER_TIMEOUT_SECONDS", "PPT_MARKITDOWN_TIMEOUT_SECONDS", "PPT_FALLBACK_ENABLED"]:
    print(key, env.get(key))
'@ | .\.venv\Scripts\python.exe -
```

Expected:

```text
PPT_CONVERTER_COMMAND soffice
PPT_CONVERTER_TIMEOUT_SECONDS 120
PPT_MARKITDOWN_TIMEOUT_SECONDS 120
PPT_FALLBACK_ENABLED True
```

- [ ] **Step 6: 提交**

```bash
git add start.py ppt_runtime/README.md backend/open_webui/retrieval/loaders/main.py
git commit -m "docs: add offline powerpoint runtime guide"
```

### Task 5: 做最终集成验证

**Files:**
- Verify only: `backend/open_webui/retrieval/loaders/*.py`
- Verify only: `backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py`
- Verify only: `ppt_runtime/README.md`

- [ ] **Step 1: 运行 PowerPoint 单测**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
4 passed
```

- [ ] **Step 2: 运行现有后端相关测试，确认没带崩已有路由**

Run:

```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -m pytest backend/open_webui/test/apps/webui/routers/test_auths.py backend/open_webui/test/apps/webui/routers/test_models.py backend/open_webui/test/apps/webui/routers/test_users.py -q --basetemp=.tmp-pytest-codex
```

Expected:

```text
all passed
```

- [ ] **Step 3: 做一次最小运行时自检**

Run:

```powershell
@'
from pathlib import Path
from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

sample = Path("sample-check.pptx")
print("PowerPoint loader import ok")
'@ | .\.venv\Scripts\python.exe -
```

Expected:

```text
PowerPoint loader import ok
```

- [ ] **Step 4: 提交最终实现**

```bash
git add backend/open_webui/retrieval/loaders/main.py backend/open_webui/retrieval/loaders/powerpoint_markdown.py backend/open_webui/retrieval/loaders/powerpoint_converter.py backend/open_webui/retrieval/loaders/powerpoint_fallback.py backend/open_webui/test/apps/webui/retrieval/test_powerpoint_loader.py start.py ppt_runtime/README.md
git commit -m "feat: add offline powerpoint markdown ingestion"
```
