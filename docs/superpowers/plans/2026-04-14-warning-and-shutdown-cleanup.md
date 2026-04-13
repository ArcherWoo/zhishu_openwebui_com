# Warning And Shutdown Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up meaningful frontend build warnings, remove the tools-page community recommendation card, and make Windows `Ctrl+C` shutdown quiet and graceful.

**Architecture:** The frontend work stays surgical: fix only project-owned Svelte warnings in the components named by the build output and remove the unwanted tools-page block directly from the page component. The backend shutdown fix stays in `start.py` and tests by isolating Windows process-group behavior behind the existing launcher abstraction.

**Tech Stack:** Python, Pytest, Svelte, TypeScript, Vite.

---

### Task 1: Add Failing Shutdown Regression Tests

**Files:**
- Modify: `tests/test_start.py`
- Modify: `start.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q` and confirm the new assertions fail**
- [ ] **Step 3: Implement the Windows process-group graceful shutdown change in `start.py`**
- [ ] **Step 4: Run `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q` and confirm it passes**

### Task 2: Remove The Tools Community Card

**Files:**
- Modify: `src/lib/components/workspace/Tools.svelte`

- [ ] **Step 1: Add a UI regression test or targeted assertion where practical**
- [ ] **Step 2: Remove the bottom community recommendation block from the tools page**
- [ ] **Step 3: Run `npm run build` and confirm the page still compiles**

### Task 3: Reduce Actionable Frontend Warnings

**Files:**
- Modify: warning-bearing Svelte components reported by the build output

- [ ] **Step 1: Capture the current warning list from `npm run build`**
- [ ] **Step 2: Fix icon-button labels, self-closing non-void tags, clickable static elements, and stale exports in project-owned components**
- [ ] **Step 3: Re-run `npm run build` and compare the warning output**
- [ ] **Step 4: Stop once the remaining warnings are third-party or explicitly deferred**

### Task 4: Final Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run `.\.venv\Scripts\python.exe -m pytest tests/test_start.py -q`**
- [ ] **Step 2: Run `npm run build`**
- [ ] **Step 3: Review `git status --short` and confirm only intended files changed**
- [ ] **Step 4: Commit and push**
