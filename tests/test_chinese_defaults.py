from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCE = ROOT / 'backend' / 'open_webui' / 'config.py'
PAYLOAD_SOURCE = ROOT / 'backend' / 'open_webui' / 'utils' / 'payload.py'


def read_source(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_default_prompt_suggestions_are_chinese():
    source = read_source(CONFIG_SOURCE)

    assert "'title': ['帮我学习', '准备高考英语词汇']" in source
    assert '请帮我练习英语词汇' in source
    assert "'title': ['Help me study', 'vocabulary for a college entrance exam']" not in source


def test_default_follow_up_prompt_template_forces_simplified_chinese():
    source = read_source(CONFIG_SOURCE)
    start = source.index('DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = """')
    end = source.index('ENABLE_FOLLOW_UP_GENERATION = PersistentConfig(', start)
    follow_up_template_block = source[start:end]

    assert '始终使用简体中文输出所有追问' in follow_up_template_block
    assert 'default to English if multilingual' not in follow_up_template_block


def test_default_model_params_include_chinese_system_prompt():
    source = read_source(CONFIG_SOURCE)

    assert 'DEFAULT_CHINESE_SYSTEM_PROMPT' in source
    assert '你是一名默认使用简体中文交流的 AI 助手' in source
    assert "DEFAULT_MODEL_PARAMS',\n    'models.default_params',\n    default_model_params" in source


def test_merge_model_params_helper_exists_for_default_system_prompt():
    source = read_source(PAYLOAD_SOURCE)

    assert 'def merge_model_params(' in source
    assert '**(default_params or {})' in source
    assert '**(model_params or {})' in source
