# Prefetch Progress Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `prefetch_vendor_deps.py` show real-time progress, heartbeats, and optional verbose subprocess output without losing its final reports.

**Architecture:** Add a tracked subprocess runner inside `prefetch_vendor_deps.py`, route all long-running package operations through it, and cover the user-visible behavior with focused unit tests.

**Tech Stack:** Python 3.11, `subprocess`, `threading`, `pytest`

---

### Task 1: Lock the desired terminal behavior with tests

**Files:**
- Modify: `tests/test_start.py`
- Modify: `prefetch_vendor_deps.py`

- [ ] **Step 1: Write failing tests for `--verbose` parsing and tracked command logs**
- [ ] **Step 2: Run the focused pytest selection to confirm the tests fail**
- [ ] **Step 3: Implement the minimal helpers and argument plumbing**
- [ ] **Step 4: Run the focused pytest selection to confirm the tests pass**

### Task 2: Wire tracked progress through Python and NPM phases

**Files:**
- Modify: `prefetch_vendor_deps.py`

- [ ] **Step 1: Route Python package loops through the tracked runner with phase labels**
- [ ] **Step 2: Route NPM package loops and validations through the tracked runner**
- [ ] **Step 3: Add concise phase-start logs and keep failure collection behavior unchanged**
- [ ] **Step 4: Run the focused pytest selection again**

### Task 3: Verify the user experience and document the new flags

**Files:**
- Modify: `VENDOR_DEPLOYMENT_MANUAL.md`
- Modify: `prefetch_vendor_deps.py`

- [ ] **Step 1: Run a real `--dry-run` execution and inspect the terminal output**
- [ ] **Step 2: Update the deployment manual with the new progress/verbose behavior**
- [ ] **Step 3: Re-run tests and the dry-run command**
- [ ] **Step 4: Commit and push**
