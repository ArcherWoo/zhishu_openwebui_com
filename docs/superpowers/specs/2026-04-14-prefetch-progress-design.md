# Prefetch Progress Feedback Design

## Goal

Make `prefetch_vendor_deps.py` feel alive while it runs, especially during long `pip` and `npm` operations that currently produce no visible terminal output for extended periods.

## Problem

The script currently routes every subprocess through buffered capture. That preserves final error summaries, but it also means the terminal stays silent until each individual command exits. During slow downloads or validation passes, users cannot tell:

- which phase is running
- which package is being processed
- whether the script is still healthy
- whether they should wait or interrupt it

## Requirements

1. Show progress before each major step and package-level operation.
2. Emit periodic heartbeat logs while a subprocess is still running.
3. Keep the existing structured JSON/Markdown report behavior.
4. Add a `--verbose` mode that streams child output live for deeper troubleshooting.
5. Preserve failure tolerance: the script must continue through later checks/downloads even if earlier items fail.

## Design

- Introduce a dedicated prefetch logger with a `[prefetch]` prefix.
- Replace the current fully-buffered subprocess helper with a tracked runner that:
  - logs the phase name and package index before starting
  - monitors the child process while it runs
  - prints a heartbeat every N seconds when the child is still active
  - captures combined output for the existing failure summaries
  - optionally mirrors child output live when `--verbose` is enabled
- Keep heartbeat timing conservative so normal fast commands are not noisy.
- Reuse the tracked runner for Python direct checks, Python bundle downloads/probes, Python full validation, NPM cache prefetch, and NPM offline validation.

## Testing

- Add tests for argument parsing with `--verbose`.
- Add tests for tracked command logging:
  - start/progress log
  - heartbeat log
  - verbose child output passthrough
- Run the focused prefetch/start test suite after implementation.
