import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

from langchain_core.documents import Document

from open_webui.retrieval.loaders.powerpoint_converter import (
    PowerPointConversionError,
    PowerPointConverter,
)
from open_webui.retrieval.loaders.powerpoint_fallback import PowerPointFallbackLoader

log = logging.getLogger(__name__)


class MarkItDownPowerPointLoader:
    def __init__(self, file_path: str, timeout_seconds: int = 120):
        self.file_path = file_path
        self.timeout_seconds = timeout_seconds

    def load_markdown(self) -> str:
        from markitdown import MarkItDown

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(MarkItDown().convert, self.file_path)
            try:
                result = future.result(timeout=self.timeout_seconds)
            except FuturesTimeoutError as exc:
                raise TimeoutError(
                    f'MarkItDown timed out after {self.timeout_seconds} seconds'
                ) from exc

        text = getattr(result, 'text_content', None) or getattr(result, 'markdown', None) or ''
        return str(text).strip()


class PowerPointMarkdownLoader:
    def __init__(
        self,
        file_path: str,
        filename: str,
        content_type: str | None,
        converter_command: str = 'soffice',
        converter_timeout_seconds: int = 120,
        markitdown_timeout_seconds: int = 120,
        fallback_enabled: bool = True,
    ):
        self.file_path = file_path
        self.filename = filename
        self.content_type = content_type
        self.converter_command = converter_command
        self.converter_timeout_seconds = converter_timeout_seconds
        self.markitdown_timeout_seconds = markitdown_timeout_seconds
        self.fallback_enabled = self._as_bool(fallback_enabled)

    @staticmethod
    def _as_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def load(self) -> list[Document]:
        suffix = Path(self.filename).suffix.lower()
        target_path = self.file_path
        converted_from_ppt = False
        converter = None

        try:
            log.info('Starting PowerPoint parse for %s', self.filename)

            if suffix == '.ppt':
                log.info('Starting PPT to PPTX conversion for %s', self.filename)
                converter = PowerPointConverter(
                    command=self.converter_command,
                    timeout_seconds=self.converter_timeout_seconds,
                )
                target_path = converter.convert(self.file_path)
                converted_from_ppt = True
                log.info('PPT to PPTX conversion succeeded for %s', self.filename)

            markdown = MarkItDownPowerPointLoader(
                file_path=target_path,
                timeout_seconds=self.markitdown_timeout_seconds,
            ).load_markdown()

            if not markdown:
                raise ValueError('PowerPoint markdown content is empty')

            log.info('MarkItDown parse succeeded for %s', self.filename)
            metadata = {
                'source': self.filename,
                'content_format': 'markdown',
                'parsed_by': 'markitdown',
                'original_extension': suffix.lstrip('.'),
            }
            if converted_from_ppt:
                metadata['converted_from_ppt'] = True

            return [Document(page_content=markdown, metadata=metadata)]
        except PowerPointConversionError:
            log.exception('PowerPoint conversion failed for %s', self.filename)
            raise
        except Exception:
            log.exception('PowerPoint markdown loader failed for %s', self.filename)
            if not self.fallback_enabled:
                raise

            if suffix == '.ppt' and not converted_from_ppt:
                raise

            log.warning('Falling back to python-pptx for %s', self.filename)
            return PowerPointFallbackLoader(file_path=target_path, filename=self.filename).load()
        finally:
            if converter is not None:
                converter.cleanup()
