# Open WebUI

Open WebUI is a self-hosted AI web interface for Ollama and OpenAI-compatible APIs. This repository is configured for local, non-Docker use.

## Highlights

- Local-first startup with `python start.py`
- Offline-friendly runtime options
- Built-in RAG, tools, multi-model chat, and web search integrations
- Svelte frontend with Python backend

## Local Start

Before starting, use Python 3.11 or 3.12.

```bash
python start.py
```

The app will start at `http://localhost:8080`.
`start.py` now defaults to offline-safe mode, which blocks Hugging Face model downloads in restricted networks.
If you explicitly want online model downloads and update checks, use `python start.py --online`.

## Python Package Install

If you want the packaged install instead of running this repository directly:

```bash
pip install open-webui
open-webui serve
```

## Ollama Connectivity

If Open WebUI cannot reach Ollama, verify that `OLLAMA_BASE_URL` points to a reachable server such as:

```bash
http://127.0.0.1:11434
```

You can also review [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Offline Mode

Repository startup now defaults to offline-safe mode for restricted networks.
If you are launching the backend another way, set these variables manually:

```bash
OFFLINE_MODE=True
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

## Development

For local repository development guidance, see:

- [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md)
- [Open WebUI Documentation](https://docs.openwebui.com/)

## License

See [LICENSE](./LICENSE) and [LICENSE_HISTORY](./LICENSE_HISTORY).
