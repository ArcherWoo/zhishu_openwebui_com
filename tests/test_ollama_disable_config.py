from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ollama_is_disabled_by_default_and_exposed_to_frontend():
    config_source = (ROOT / 'backend' / 'open_webui' / 'config.py').read_text(encoding='utf-8')
    main_source = (ROOT / 'backend' / 'open_webui' / 'main.py').read_text(encoding='utf-8')

    assert "os.environ.get('ENABLE_OLLAMA_API', 'False').lower() == 'true'" in config_source
    assert "'enable_ollama_api': app.state.config.ENABLE_OLLAMA_API" in main_source
