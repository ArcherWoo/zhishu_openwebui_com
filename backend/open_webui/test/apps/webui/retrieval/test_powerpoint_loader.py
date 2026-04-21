from open_webui.retrieval.loaders.main import Loader
from langchain_core.documents import Document


def test_loader_routes_pptx_to_powerpoint_markdown_loader(monkeypatch, tmp_path):
    target = {}

    class DummyPowerPointMarkdownLoader:
        def __init__(self, file_path, filename, content_type, **kwargs):
            target["loader"] = "powerpoint_markdown"
            target["file_path"] = file_path
            target["filename"] = filename
            target["content_type"] = content_type

        def load(self):
            raise AssertionError("route confirmed")

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.main.PowerPointMarkdownLoader",
        DummyPowerPointMarkdownLoader,
    )

    sample = tmp_path / "sample.pptx"
    sample.write_bytes(b"pptx")

    loader = Loader(engine="")

    try:
        loader.load(
            sample.name,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            str(sample),
        )
    except AssertionError as exc:
        assert str(exc) == "route confirmed"

    assert target == {
        "loader": "powerpoint_markdown",
        "file_path": str(sample),
        "filename": sample.name,
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }


def test_powerpoint_markdown_loader_uses_markitdown_for_pptx(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "deck.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            assert file_path == str(sample)
            assert timeout_seconds == 120

        def load_markdown(self):
            return "# Title\n\n- item"

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        markitdown_timeout_seconds=120,
    ).load()

    assert docs == [
        Document(
            page_content="# Title\n\n- item",
            metadata={
                "source": sample.name,
                "content_format": "markdown",
                "parsed_by": "markitdown",
                "original_extension": "pptx",
            },
        )
    ]


def test_powerpoint_markdown_loader_converts_ppt_before_markitdown(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "legacy.ppt"
    converted = tmp_path / "legacy.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyConverter:
        def __init__(self, command, timeout_seconds):
            assert command == "soffice"
            assert timeout_seconds == 120

        def convert(self, input_path):
            assert input_path == str(sample)
            converted.write_text("converted", encoding="utf-8")
            return str(converted)

        def cleanup(self):
            return None

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            assert file_path == str(converted)
            assert timeout_seconds == 120

        def load_markdown(self):
            return "# Converted"

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointConverter",
        DummyConverter,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.ms-powerpoint",
        converter_command="soffice",
        converter_timeout_seconds=120,
        markitdown_timeout_seconds=120,
    ).load()

    assert docs[0].page_content == "# Converted"
    assert docs[0].metadata["converted_from_ppt"] is True


def test_powerpoint_markdown_loader_uses_fallback_after_markitdown_failure(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "broken.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            pass

        def load_markdown(self):
            raise RuntimeError("markitdown failed")

    class DummyFallbackLoader:
        def __init__(self, file_path, filename):
            assert file_path == str(sample)
            assert filename == sample.name

        def load(self):
            return [Document(page_content="# fallback", metadata={"parsed_by": "python-pptx-fallback"})]

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointFallbackLoader",
        DummyFallbackLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ).load()

    assert docs[0].page_content == "# fallback"


def test_powerpoint_markdown_loader_uses_fallback_after_ppt_conversion(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "broken.ppt"
    converted = tmp_path / "broken.pptx"
    sample.write_text("stub", encoding="utf-8")
    converted.write_text("converted", encoding="utf-8")

    class DummyConverter:
        def __init__(self, command, timeout_seconds):
            pass

        def convert(self, input_path):
            return str(converted)

        def cleanup(self):
            return None

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            assert file_path == str(converted)

        def load_markdown(self):
            raise RuntimeError("markitdown failed")

    class DummyFallbackLoader:
        def __init__(self, file_path, filename):
            assert file_path == str(converted)
            assert filename == sample.name

        def load(self):
            return [Document(page_content="# converted fallback", metadata={"parsed_by": "python-pptx-fallback"})]

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointConverter",
        DummyConverter,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )
    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.PowerPointFallbackLoader",
        DummyFallbackLoader,
    )

    docs = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.ms-powerpoint",
    ).load()

    assert docs[0].page_content == "# converted fallback"


def test_powerpoint_markdown_loader_honors_false_string_for_fallback(monkeypatch, tmp_path):
    from open_webui.retrieval.loaders.powerpoint_markdown import PowerPointMarkdownLoader

    sample = tmp_path / "nofallback.pptx"
    sample.write_text("stub", encoding="utf-8")

    class DummyMarkItDownLoader:
        def __init__(self, file_path, timeout_seconds):
            pass

        def load_markdown(self):
            raise RuntimeError("markitdown failed")

    monkeypatch.setattr(
        "open_webui.retrieval.loaders.powerpoint_markdown.MarkItDownPowerPointLoader",
        DummyMarkItDownLoader,
    )

    loader = PowerPointMarkdownLoader(
        file_path=str(sample),
        filename=sample.name,
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        fallback_enabled="False",
    )

    try:
        loader.load()
    except RuntimeError as exc:
        assert str(exc) == "markitdown failed"
    else:
        raise AssertionError("expected RuntimeError when fallback is disabled")
