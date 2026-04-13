# Disable Ollama By Default Design

## Goal

Disable Ollama by default so a fresh deployment does not probe `localhost:11434`, while keeping administrator model-management access intact and removing Ollama-related frontend entry points when the feature is off.

## Scope

- Change the backend default for `ENABLE_OLLAMA_API` from enabled to disabled.
- Expose the Ollama-enabled state through `/api/config` so the frontend can hide related UI.
- Keep administrator access to workspace model management.
- Hide Ollama-specific admin UI when Ollama is disabled.
- Avoid changing unrelated OpenAI or workspace permissions behavior.

## Current State

- Backend config enables Ollama by default, which leads model-refresh code to probe `localhost:11434`.
- Failed Ollama probes are logged as connection errors.
- Workspace model access is already split correctly: admins always see models, regular users only see them when granted permission.
- Several frontend surfaces still reference Ollama regardless of whether it is actually used:
  - Admin connections settings
  - Admin model management modal
  - Chat about page Ollama version probe
  - Admin documents embedding-engine selector

## Proposed Design

### Backend

- Set the default value of `ENABLE_OLLAMA_API` to `False`.
- Add `enable_ollama_api` to the `/api/config` feature payload.
- Leave the Ollama router in place so explicit re-enable paths still work if needed later.

### Frontend

- Read `config.features.enable_ollama_api`.
- Hide the Ollama section from admin connection settings when the feature is off.
- Prevent the admin model-management modal from selecting or rendering Ollama management when the feature is off.
- Skip the about-page Ollama version request when the feature is off.
- Remove the Ollama embedding-engine option from admin document settings when the feature is off, and coerce an invalid saved value back to the default local embedding engine.

### Permissions

- Do not change workspace routing rules for admin users.
- Do not change non-admin workspace permission semantics.

## Testing Strategy

- Add a Python regression test that checks the backend default and the `/api/config` feature export.
- Verify frontend type/build health with `svelte-check`.

## Risks

- If an existing deployment depended on implicit Ollama auto-enable, it will now need explicit enablement.
- Hiding the Ollama embedding option must not leave the page stuck with a now-hidden selected value.

## Success Criteria

- Startup no longer attempts Ollama connections by default.
- Red connection logs to `localhost:11434` disappear in the default setup.
- Admins still retain workspace model management access.
- Ollama-specific frontend entry points are hidden when the feature is off.
