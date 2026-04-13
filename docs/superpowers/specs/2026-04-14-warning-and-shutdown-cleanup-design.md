# Warning And Shutdown Cleanup Design

## Goal

Reduce the noisy Svelte build warnings that matter, remove the unwanted community recommendation block from the tools workspace page, and make `python start.py` shut down cleanly on Windows `Ctrl+C` without dumping uvicorn traceback noise.

## Scope

- Remove the tools-page community recommendation block shown below the empty-state list.
- Fix the actionable frontend warnings currently emitted during `npm run build`.
- Improve Windows process shutdown so `Ctrl+C` is handled by the launcher first and forwarded to uvicorn in a controlled way.
- Keep existing admin and workspace behavior intact.

## Problem Summary

### Frontend warnings

The current build emits many warnings, but not all of them are equally valuable:

- Accessibility warnings for unlabeled buttons and clickable non-interactive elements are real issues.
- Invalid self-closing non-void tags are noisy and should be normalized for Svelte 5.
- Unused component exports indicate stale component APIs and add noise.
- Third-party package metadata warnings are upstream and can be left alone for now.

### Shutdown traceback on `Ctrl+C`

The current launcher wraps uvicorn, but on Windows both the parent launcher and child uvicorn process can still receive the console interrupt together. That creates a race where uvicorn begins its own interrupt path and prints traceback noise before the wrapper returns `130`.

## Proposed Design

### Tools page cleanup

- Remove the bottom “Made by Open WebUI Community / Discover a tool” card from the tools workspace page entirely.
- Do not rely on empty translations or CSS hiding; remove the block from the component so it is not rendered at all.

### Frontend warning cleanup

- Fix the concrete warning classes that come from project-owned components:
  - add missing `aria-label` where buttons are icon-only
  - replace clickable static containers with buttons or add proper keyboard semantics when button conversion is not appropriate
  - replace self-closing non-void HTML tags with explicit opening and closing tags
  - remove or convert stale `export let` props that are no longer consumed
- Leave third-party package warnings and chunk-size advisory warnings untouched for this pass.
- Focus on the files currently reported by the build output instead of broad refactors.

### Windows shutdown cleanup

- Launch the uvicorn child in its own Windows process group so the user’s console `Ctrl+C` is first handled by `start.py`.
- On Windows graceful shutdown, send `CTRL_BREAK_EVENT` to the child process group instead of immediately calling `terminate()`.
- Keep the existing timeout-based fallback kill path.
- Preserve the current non-Windows behavior.
- Add regression tests around the Windows-specific graceful-stop path.

## Testing Strategy

- Add Python regression tests for the Windows graceful-stop branch and process creation flags.
- Run targeted frontend verification using `npm run build`.
- Run targeted backend tests with `pytest tests/test_start.py -q`.

## Success Criteria

- The tools workspace page no longer shows the community recommendation block.
- `npm run build` no longer emits the project-owned accessibility / self-closing / stale-export warnings fixed in this pass.
- `python start.py` on Windows can be interrupted with `Ctrl+C` without dumping the uvicorn traceback shown by the user.
