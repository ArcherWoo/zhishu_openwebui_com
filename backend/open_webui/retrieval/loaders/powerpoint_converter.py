import shutil
import subprocess
import tempfile
from pathlib import Path


class PowerPointConversionError(RuntimeError):
    pass


class PowerPointConverter:
    def __init__(self, command: str = 'soffice', timeout_seconds: int = 120):
        self.command = command
        self.timeout_seconds = timeout_seconds
        self._temp_dir: str | None = None

    def convert(self, input_path: str) -> str:
        if shutil.which(self.command) is None:
            raise PowerPointConversionError(f'{self.command} not found')

        source = Path(input_path)
        if source.suffix.lower() != '.ppt':
            raise PowerPointConversionError('converter only accepts .ppt')

        self._temp_dir = tempfile.mkdtemp(prefix='ppt-convert-')
        temp_dir = Path(self._temp_dir)

        try:
            subprocess.run(
                [
                    self.command,
                    '--headless',
                    '--convert-to',
                    'pptx',
                    '--outdir',
                    str(temp_dir),
                    str(source),
                ],
                check=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise PowerPointConversionError(
                f'PowerPoint conversion timed out after {self.timeout_seconds} seconds'
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise PowerPointConversionError(
                f'PowerPoint conversion failed with exit code {exc.returncode}'
            ) from exc

        converted = temp_dir / f'{source.stem}.pptx'
        if not converted.exists():
            raise PowerPointConversionError('converted pptx not found')

        return str(converted)

    def cleanup(self) -> None:
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
