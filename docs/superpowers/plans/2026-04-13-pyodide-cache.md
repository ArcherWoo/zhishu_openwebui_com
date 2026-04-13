# Pyodide Cache Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/prepare-pyodide.js` reuse a complete local cache instead of re-downloading Pyodide packages on every build.

**Architecture:** Introduce a pure cache-validation helper that compares runtime metadata, requested package lists, and required files before the main script attempts any network work. The main script will then skip, repair, or fully reset based on those validation results.

**Tech Stack:** Node.js, ESM, Vitest.

---

### Task 1: Add Cache Validation Regression Tests

**Files:**
- Create: `scripts/lib/pyodide-cache.test.js`
- Create: `scripts/lib/pyodide-cache.js`

- [ ] **Step 1: Write failing validation tests**
- [ ] **Step 2: Run `npm run test:frontend -- --run scripts/lib/pyodide-cache.test.js` and confirm the new test fails**
- [ ] **Step 3: Implement the helper until the new test passes**

### Task 2: Refactor `prepare-pyodide.js`

**Files:**
- Modify: `scripts/prepare-pyodide.js`

- [ ] **Step 1: Read the real Pyodide version from `node_modules/pyodide/package.json`**
- [ ] **Step 2: Validate `static/pyodide/` before calling `loadPyodide`**
- [ ] **Step 3: Skip the download flow when the cache is already complete**
- [ ] **Step 4: Replace deprecated `rmdir` usage with `rm`**
- [ ] **Step 5: Persist cache metadata only after a successful refresh**

### Task 3: Verify Reuse End-To-End

**Files:**
- Modify: none

- [ ] **Step 1: Run the targeted Vitest regression**
- [ ] **Step 2: Run `node scripts/prepare-pyodide.js` once to repair or write cache metadata**
- [ ] **Step 3: Run `node scripts/prepare-pyodide.js` again and confirm the cache-hit skip path**
- [ ] **Step 4: Run `npm run build` to confirm the build path still works**
