from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ABOUT_COMPONENT = ROOT / 'src' / 'lib' / 'components' / 'chat' / 'Settings' / 'About.svelte'


def test_user_about_settings_does_not_show_upstream_branding_or_update_links():
    source = ABOUT_COMPONENT.read_text(encoding='utf-8')

    hidden_phrases = [
        "See what's new",
        'Check for updates',
        'discord.gg',
        'twitter.com/OpenWebUI',
        'github.com/open-webui/open-webui',
        'Twemoji',
        'Copyright (c)',
        'Open WebUI Inc.',
        'Timothy J. Baek',
    ]

    for phrase in hidden_phrases:
        assert phrase not in source
