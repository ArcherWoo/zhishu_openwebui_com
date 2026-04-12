# Start Scripts Chinese UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start.py` and `start_prod.py` easier to operate in Chinese, print correct localhost/LAN access URLs, shut down gracefully on `Ctrl+C`, and add Chinese deployment instructions for Windows and Linux.

**Architecture:** Keep the runtime binding behavior unchanged (`0.0.0.0` remains the default host), but move user-facing status output and child-process lifecycle handling into shared helpers inside `start.py`. Reuse those helpers from `start_prod.py` so both scripts present the same Chinese UX and graceful shutdown behavior.

**Tech Stack:** Python 3.11+, subprocess, socket/ipaddress helpers, pytest, Markdown docs

---

### Task 1: Expand Regression Tests For Startup UX

**Files:**
- Modify: `tests/test_start.py`

- [ ] **Step 1: Write failing tests for LAN URL display and graceful shutdown helpers**

```python
def test_collect_lan_urls_prefers_private_ipv4_addresses(monkeypatch):
    ...


def test_run_managed_process_logs_graceful_shutdown_and_returns_130(monkeypatch, capsys):
    ...


def test_start_prod_run_cli_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    ...
```

- [ ] **Step 2: Run tests to verify they fail for the expected missing behavior**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
Expected: failures mentioning missing helpers or mismatched log output

- [ ] **Step 3: Keep tests focused on behavior**

Cover only:
- localhost/LAN URL generation
- graceful child shutdown path
- `start_prod.py` top-level keyboard interrupt handling

- [ ] **Step 4: Re-run the same test command and confirm failures are still targeted**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
Expected: same focused failures, no unrelated import errors

### Task 2: Implement Shared Chinese Status And Graceful Shutdown In `start.py`

**Files:**
- Modify: `start.py`
- Test: `tests/test_start.py`

- [ ] **Step 1: Add minimal helpers for Chinese logging, LAN URL calculation, and child process shutdown**

Add focused helpers such as:
- `browser_url()`
- `collect_lan_ipv4_addresses()`
- `format_access_urls()`
- `terminate_process_gracefully()`
- `run_managed_process()`

- [ ] **Step 2: Make `start.py` use the new helpers without changing CLI flags**

Required behavior:
- keep binding host unchanged
- print Chinese startup status
- show localhost URL plus LAN URLs
- manage foreground child process explicitly
- handle `Ctrl+C` with graceful stop, timeout fallback, and exit code `130`

- [ ] **Step 3: Add Chinese comments around key sections**

Comment the sections that explain:
- Python re-exec
- venv preparation
- dependency install cache
- runtime env assembly
- LAN URL display
- graceful shutdown flow

- [ ] **Step 4: Run targeted tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
Expected: all tests pass

### Task 3: Reuse The Same UX And Shutdown Flow In `start_prod.py`

**Files:**
- Modify: `start_prod.py`
- Test: `tests/test_start.py`

- [ ] **Step 1: Wire `start_prod.py` to shared helpers from `start.py`**

Required behavior:
- production foreground startup also uses managed child process waiting
- detached/service flows remain intact
- startup messages are Chinese
- localhost/LAN URL display is consistent with `start.py`

- [ ] **Step 2: Add Chinese comments for production-specific logic**

Explain:
- production defaults
- port preflight check
- detached logs
- Windows service management path

- [ ] **Step 3: Add or adjust tests so production wrapper behavior is covered**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`
Expected: production-related tests pass too

### Task 4: Write Chinese Deployment Documentation

**Files:**
- Create: `docs/DEPLOY_START_SCRIPTS_ZH.md`

- [ ] **Step 1: Write a practical Chinese deployment guide**

Sections to include:
- `start.py` vs `start_prod.py`
- Windows deployment
- Linux deployment
- LAN access explanation
- graceful shutdown explanation
- troubleshooting

- [ ] **Step 2: Include exact commands for common usage**

Include concrete examples for:
- first run
- production run
- detach mode
- service operations on Windows
- port checks on Windows/Linux

- [ ] **Step 3: Mention the `0.0.0.0` vs browser URL distinction explicitly**

Include the rule:
- bind can be `0.0.0.0`
- browser should use `localhost` or printed LAN address

### Task 5: Verify End To End

**Files:**
- Modify: `start.py`
- Modify: `start_prod.py`
- Modify: `tests/test_start.py`
- Create: `docs/DEPLOY_START_SCRIPTS_ZH.md`

- [ ] **Step 1: Run the focused regression tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_start.py`
Expected: all tests pass

- [ ] **Step 2: Smoke-test `start.py` launch text**

Run: `C:\Python313\python.exe start.py --backend-only`
Expected: Chinese startup output includes localhost and, when available, LAN URL

- [ ] **Step 3: Smoke-test `start_prod.py` launch text**

Run: `C:\Python313\python.exe start_prod.py --prepare-only`
Expected: Chinese production bootstrap output appears without traceback

- [ ] **Step 4: Confirm docs file exists and is readable**

Run: `Get-Content docs\DEPLOY_START_SCRIPTS_ZH.md -TotalCount 80`
Expected: Chinese deployment guide content is present
