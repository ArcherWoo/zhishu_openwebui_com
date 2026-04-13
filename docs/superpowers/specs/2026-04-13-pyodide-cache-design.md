# Pyodide Cache Reuse Design

## Goal

Stop `scripts/prepare-pyodide.js` from re-downloading the full Pyodide package set on every build when the local cache is already complete.

## Problem

- The script compares the cached version against the semver range in `package.json` instead of the real installed `node_modules/pyodide` version.
- The script always enters the Pyodide install flow before deciding whether the cache is reusable.
- The script deletes the cache with deprecated `fs.rmdir(..., { recursive: true })`.
- There is no persisted cache metadata describing which PyPI wheels were successfully mirrored.

## Desired Behavior

- Read the actual installed Pyodide version from `node_modules/pyodide/package.json`.
- Validate `static/pyodide/` before calling `loadPyodide`.
- Skip the fetch/install flow entirely when the cache is complete.
- Only clear `static/pyodide/` when the cached Pyodide runtime version is stale.
- Persist cache metadata after a successful refresh so later runs can safely reuse the cache.

## Design

### Cache Metadata

Write `static/pyodide/open-webui-pyodide-cache.json` after a successful refresh. The file stores:

- Schema version
- Installed Pyodide version
- Requested Pyodide package list
- Requested PyPI wheel package list
- Downloaded PyPI wheel filenames

### Validation Rules

The cache is reusable only when all conditions are met:

- Cache metadata exists and matches the current requested package sets.
- The cached Pyodide version matches `node_modules/pyodide`.
- All core files from `node_modules/pyodide` exist in `static/pyodide`.
- All wheel filenames recorded in the cache metadata exist in `static/pyodide`.

### Refresh Rules

- If the cached runtime version is stale, remove `static/pyodide/` with `fs.rm(..., { recursive: true, force: true })`.
- If metadata is missing or incomplete but the runtime version is still current, keep the directory and top it up.
- Only write cache metadata when the Pyodide and PyPI download steps both succeed.

## Testing Strategy

- Add a small pure helper module for cache validation.
- Add Vitest regression coverage for:
  - successful cache reuse
  - version mismatch invalidation
  - missing wheel invalidation
  - package list mismatch invalidation

## Success Criteria

- The first repair run rebuilds or completes the cache and writes metadata.
- A second run prints a cache-hit message and skips the expensive install flow.
- No deprecation warning remains for recursive cache deletion.
