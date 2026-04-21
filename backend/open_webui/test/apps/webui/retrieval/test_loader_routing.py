import sys
import tempfile
import types
from pathlib import Path

import open_webui.retrieval.loaders.external_document as external_document_module
import open_webui.retrieval.loaders.main as loader_module


class _DummyLoader:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def load(self):
        return []


class _DummyResponse:
    ok = True

    @staticmethod
    def json():
        return {'page_content': 'ok', 'metadata': {'source': 'test'}}


def _build_external_loader():
    return loader_module.Loader(
        engine='external',
        EXTERNAL_DOCUMENT_LOADER_URL='http://document-loader.internal',
        EXTERNAL_DOCUMENT_LOADER_API_KEY='secret',
    )


def test_external_engine_keeps_markdown_on_local_text_loader(monkeypatch):
    monkeypatch.setattr(loader_module, 'TextLoader', type('SentinelTextLoader', (_DummyLoader,), {}))
    monkeypatch.setattr(
        loader_module,
        'ExternalDocumentLoader',
        type('SentinelExternalDocumentLoader', (_DummyLoader,), {}),
    )

    loader = _build_external_loader()
    selected_loader = loader._get_loader('knowledge.md', 'text/markdown', 'C:/tmp/knowledge.md')

    assert selected_loader.__class__.__name__ == 'SentinelTextLoader'


def test_external_engine_keeps_pdf_on_local_pdf_loader(monkeypatch):
    monkeypatch.setattr(loader_module, 'PyPDFLoader', type('SentinelPyPDFLoader', (_DummyLoader,), {}))
    monkeypatch.setattr(
        loader_module,
        'ExternalDocumentLoader',
        type('SentinelExternalDocumentLoader', (_DummyLoader,), {}),
    )

    loader = _build_external_loader()
    selected_loader = loader._get_loader('slides.pdf', 'application/pdf', 'C:/tmp/slides.pdf')

    assert selected_loader.__class__.__name__ == 'SentinelPyPDFLoader'


def test_external_engine_keeps_pptx_on_local_powerpoint_loader(monkeypatch):
    monkeypatch.setattr(loader_module, 'PptxLoader', type('SentinelPptxLoader', (_DummyLoader,), {}))
    monkeypatch.setattr(
        loader_module,
        'ExternalDocumentLoader',
        type('SentinelExternalDocumentLoader', (_DummyLoader,), {}),
    )

    fake_doc_loader_module = types.ModuleType('langchain_community.document_loaders')
    monkeypatch.setitem(sys.modules, 'langchain_community.document_loaders', fake_doc_loader_module)

    loader = _build_external_loader()
    selected_loader = loader._get_loader(
        'deck.pptx',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'C:/tmp/deck.pptx',
    )

    assert selected_loader.__class__.__name__ == 'SentinelPptxLoader'


def test_external_engine_still_uses_external_loader_for_images(monkeypatch):
    monkeypatch.setattr(loader_module, 'TextLoader', type('SentinelTextLoader', (_DummyLoader,), {}))
    monkeypatch.setattr(
        loader_module,
        'ExternalDocumentLoader',
        type('SentinelExternalDocumentLoader', (_DummyLoader,), {}),
    )

    loader = _build_external_loader()
    selected_loader = loader._get_loader('photo.png', 'image/png', 'C:/tmp/photo.png')

    assert selected_loader.__class__.__name__ == 'SentinelExternalDocumentLoader'


def test_external_document_loader_applies_request_timeout(monkeypatch):
    captured = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        source_file = Path(temp_dir) / 'image.png'
        source_file.write_bytes(b'fake-image')

        def fake_put(url, data, headers, timeout):
            captured['url'] = url
            captured['timeout'] = timeout
            return _DummyResponse()

        monkeypatch.setattr(external_document_module.requests, 'put', fake_put)

        loader = external_document_module.ExternalDocumentLoader(
            file_path=str(source_file),
            url='http://document-loader.internal',
            api_key='secret',
            mime_type='image/png',
        )

        docs = loader.load()

        assert captured['url'] == 'http://document-loader.internal/process'
        assert captured['timeout'] == 60
        assert docs[0].page_content == 'ok'
