from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import start


ROOT = Path(__file__).resolve().parent


def log(message: str) -> None:
    print(f'[prefetch] {message}', flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='预下载 Open WebUI 的前后端依赖到 vendor 目录，并输出缺失报告。',
    )
    parser.add_argument('--python-dir', default=str(start.PYTHON_VENDOR_DIR))
    parser.add_argument('--npm-dir', default=str(start.NPM_VENDOR_DIR))
    parser.add_argument('--report-json', default=str(start.VENDOR_REPORT_JSON))
    parser.add_argument('--report-md', default=str(start.VENDOR_REPORT_MD))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--allow-unsupported-python', action='store_true')
    return parser.parse_args(argv)


def parse_requirements_entries(requirements_file: Path) -> list[str]:
    entries: list[str] = []

    for raw_line in requirements_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        if ' #' in line:
            line = line.split(' #', 1)[0].strip()
        if line:
            entries.append(line)

    return entries


def package_name_from_lock_path(package_path: str) -> str | None:
    if not package_path or 'node_modules/' not in package_path:
        return None

    tail = package_path.split('node_modules/')[-1]
    if not tail:
        return None

    parts = tail.split('/')
    if tail.startswith('@') and len(parts) >= 2:
        return f'{parts[0]}/{parts[1]}'
    return parts[0]


def collect_npm_package_specs(lock_data: dict) -> list[str]:
    specs: set[str] = set()

    for package_path, metadata in (lock_data.get('packages') or {}).items():
        if not package_path:
            continue
        if metadata.get('link'):
            continue

        resolved = str(metadata.get('resolved') or '')
        if resolved.startswith('file:'):
            continue

        version = metadata.get('version')
        name = package_name_from_lock_path(package_path)
        if not name or not version:
            continue

        specs.add(f'{name}@{version}')

    return sorted(specs)


def format_step_label(
    phase: str,
    item_label: str,
    *,
    index: int | None = None,
    total: int | None = None,
) -> str:
    progress = f' [{index}/{total}]' if index is not None and total is not None else ''
    return f'{phase}{progress} {item_label}'.strip()


def run_tracked_command(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path = ROOT,
    phase: str,
    item_label: str,
    index: int | None = None,
    total: int | None = None,
    verbose: bool = False,
    heartbeat_seconds: float = 10.0,
    progress_dir: Path | None = None,
    heartbeat_note: str | None = None,
) -> subprocess.CompletedProcess[str]:
    step_label = format_step_label(phase, item_label, index=index, total=total)
    log(f'{step_label} -> starting')

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    output_chunks: list[str] = []

    def _reader() -> None:
        if not process.stdout:
            return

        for line in iter(process.stdout.readline, ''):
            output_chunks.append(line)
            if verbose:
                print(line, end='', flush=True)

        process.stdout.close()

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    started_at = time.monotonic()
    last_heartbeat_at = started_at
    return_code = process.poll()

    while return_code is None:
        now = time.monotonic()
        if now - last_heartbeat_at >= heartbeat_seconds:
            details = [f'{int(now - started_at)}s elapsed']
            if progress_dir is not None:
                details.append(f'files={count_files(progress_dir)}')
            if heartbeat_note:
                details.append(heartbeat_note)
            log(f"{step_label} -> still running ({', '.join(details)})")
            last_heartbeat_at = now

        time.sleep(0.2)
        return_code = process.poll()

    process.wait()
    reader_thread.join(timeout=1)

    elapsed = time.monotonic() - started_at
    completion_suffix = ''
    if progress_dir is not None:
        completion_suffix = f', files={count_files(progress_dir)}'
    if return_code == 0:
        log(f'{step_label} -> completed in {elapsed:.1f}s{completion_suffix}')
    else:
        log(f'{step_label} -> failed in {elapsed:.1f}s{completion_suffix} (exit {return_code})')

    return subprocess.CompletedProcess(
        command,
        return_code,
        stdout=''.join(output_chunks),
        stderr='',
    )


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for child in path.rglob('*') if child.is_file())


def build_python_download_command(
    python_executable: str,
    requirement: str,
    vendor_dir: Path,
) -> list[str]:
    return [
        python_executable,
        '-m',
        'pip',
        'download',
        '--dest',
        str(vendor_dir),
        requirement,
    ]


def build_python_probe_command(
    python_executable: str,
    requirement: str,
) -> list[str]:
    return [
        python_executable,
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        '--no-deps',
        requirement,
    ]


def build_python_dependency_probe_command(
    python_executable: str,
    requirement: str,
) -> list[str]:
    return [
        python_executable,
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        requirement,
    ]


def build_python_offline_validation_command(
    python_executable: str,
    vendor_dir: Path,
) -> list[str]:
    return [
        python_executable,
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        '--no-index',
        '--find-links',
        str(vendor_dir),
        '-r',
        str(start.REQUIREMENTS_FILE),
    ]


def build_python_online_validation_command(
    python_executable: str,
) -> list[str]:
    return [
        python_executable,
        '-m',
        'pip',
        'install',
        '--dry-run',
        '--ignore-installed',
        '-r',
        str(start.REQUIREMENTS_FILE),
    ]


def build_npm_cache_add_command(
    npm_executable: str,
    package_spec: str,
    vendor_dir: Path,
    *,
    dry_run: bool,
) -> list[str]:
    command = [
        npm_executable,
        'cache',
        'add',
        package_spec,
        '--cache',
        str(vendor_dir),
    ]
    if dry_run:
        command.append('--dry-run')
    return command


def build_npm_validation_command(
    npm_executable: str,
    vendor_dir: Path,
    *,
    dry_run: bool,
) -> list[str]:
    command = [
        npm_executable,
        'ci',
        '--cache',
        str(vendor_dir),
        '--dry-run',
        '--ignore-scripts',
    ]
    if dry_run:
        command.append('--prefer-offline')
    else:
        command.append('--offline')
    return command


def summarize_error(result: subprocess.CompletedProcess[str]) -> str:
    combined = '\n'.join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).strip()
    if not combined:
        return f'Command failed with exit code {result.returncode}'
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    return ' | '.join(lines[-3:])


def prefetch_python_dependencies(
    python_executable: str,
    *,
    vendor_dir: Path,
    pip_env: dict[str, str],
    dry_run: bool,
    verbose: bool,
) -> dict:
    vendor_dir.mkdir(parents=True, exist_ok=True)

    direct_entries = parse_requirements_entries(start.REQUIREMENTS_FILE)
    direct_success: list[str] = []
    direct_failures: list[dict[str, str]] = []
    bundle_failures: list[dict[str, str]] = []

    log(
        f'Python phase 1/2: requirement sweep (direct probe + dependency bundle, {len(direct_entries)} items)'
    )

    for index, requirement in enumerate(direct_entries, start=1):
        probe_result = run_tracked_command(
            build_python_probe_command(python_executable, requirement),
            env=pip_env,
            phase='Python direct probe',
            item_label=requirement,
            index=index,
            total=len(direct_entries),
            verbose=verbose,
            progress_dir=vendor_dir,
        )
        if probe_result.returncode == 0:
            direct_success.append(requirement)
        else:
            direct_failures.append(
                {
                    'requirement': requirement,
                    'error': summarize_error(probe_result),
                    'suggested_command': (
                        f'python -m pip download --dest {vendor_dir.as_posix()} "{requirement}"'
                    ),
                }
            )

        bundle_command = (
            build_python_dependency_probe_command(python_executable, requirement)
            if dry_run
            else build_python_download_command(python_executable, requirement, vendor_dir)
        )
        bundle_result = run_tracked_command(
            bundle_command,
            env=pip_env,
            phase='Python dependency bundle' if dry_run else 'Python dependency download',
            item_label=requirement,
            index=index,
            total=len(direct_entries),
            verbose=verbose,
            progress_dir=vendor_dir,
        )
        if bundle_result.returncode != 0:
            bundle_failures.append(
                {
                    'requirement': requirement,
                    'error': summarize_error(bundle_result),
                    'suggested_command': (
                        f'python -m pip download --dest {vendor_dir.as_posix()} "{requirement}"'
                    ),
                }
            )

    log('Python phase 2/2: full dependency closure validation')

    if dry_run:
        full_result = run_tracked_command(
            build_python_online_validation_command(python_executable),
            env=pip_env,
            phase='Python online validation',
            item_label='backend requirements closure',
            verbose=verbose,
            progress_dir=vendor_dir,
            heartbeat_note='file count may not change during validation',
        )
        offline_validation_complete = False
        offline_validation_error = 'dry-run 模式未执行离线 vendor 完整性校验'
    else:
        full_result = run_tracked_command(
            [
                python_executable,
                '-m',
                'pip',
                'download',
                '--dest',
                str(vendor_dir),
                '-r',
                str(start.REQUIREMENTS_FILE),
            ],
            env=pip_env,
            phase='Python full download',
            item_label='backend requirements closure',
            verbose=verbose,
            progress_dir=vendor_dir,
        )
        offline_validation_result = run_tracked_command(
            build_python_offline_validation_command(python_executable, vendor_dir),
            env=pip_env,
            phase='Python offline validation',
            item_label='vendor/python completeness',
            verbose=verbose,
            progress_dir=vendor_dir,
            heartbeat_note='file count may not change during validation',
        )
        offline_validation_complete = offline_validation_result.returncode == 0
        offline_validation_error = (
            '' if offline_validation_complete else summarize_error(offline_validation_result)
        )

    return {
        'vendor_dir': str(vendor_dir),
        'python_executable': python_executable,
        'direct_requirements_total': len(direct_entries),
        'direct_successful': direct_success,
        'direct_failures': direct_failures,
        'bundle_failures': bundle_failures,
        'full_dependency_download_complete': full_result.returncode == 0,
        'full_dependency_error': '' if full_result.returncode == 0 else summarize_error(full_result),
        'offline_validation_complete': offline_validation_complete,
        'offline_validation_error': offline_validation_error,
        'artifact_file_count': count_files(vendor_dir),
    }


def prefetch_npm_dependencies(
    npm_executable: str | None,
    *,
    vendor_dir: Path,
    npm_env: dict[str, str],
    dry_run: bool,
    verbose: bool,
) -> dict:
    vendor_dir.mkdir(parents=True, exist_ok=True)

    if not npm_executable:
        return {
            'vendor_dir': str(vendor_dir),
            'npm_executable': None,
            'attempted_total': 0,
            'successful': [],
            'failures': [
                {
                    'package': '(npm unavailable)',
                    'error': '未找到 npm，可先安装 Node.js/npm 或在有 npm 的机器上执行此脚本。',
                    'suggested_command': 'npm cache add "<package@version>" --cache vendor/npm',
                }
            ],
            'offline_validation_complete': False,
            'offline_validation_error': 'npm 不可用，未执行校验',
            'artifact_file_count': count_files(vendor_dir),
        }

    lock_data = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf-8'))
    package_specs = collect_npm_package_specs(lock_data)

    successful: list[str] = []
    failures: list[dict[str, str]] = []

    log(f'NPM phase 1/2: cache prefetch ({len(package_specs)} items)')

    for index, spec in enumerate(package_specs, start=1):
        result = run_tracked_command(
            build_npm_cache_add_command(
                npm_executable,
                spec,
                vendor_dir,
                dry_run=dry_run,
            ),
            env=npm_env,
            phase='NPM cache add',
            item_label=spec,
            index=index,
            total=len(package_specs),
            verbose=verbose,
            progress_dir=vendor_dir,
        )

        if result.returncode == 0:
            successful.append(spec)
        else:
            failures.append(
                {
                    'package': spec,
                    'error': summarize_error(result),
                    'suggested_command': f'npm cache add "{spec}" --cache {vendor_dir.as_posix()}',
                }
            )

    log('NPM phase 2/2: vendor cache validation')

    validation_result = run_tracked_command(
        build_npm_validation_command(
            npm_executable,
            vendor_dir,
            dry_run=dry_run,
        ),
        env=npm_env,
        phase='NPM validation',
        item_label='package-lock closure',
        verbose=verbose,
        progress_dir=vendor_dir,
        heartbeat_note='file count may not change during validation',
    )

    return {
        'vendor_dir': str(vendor_dir),
        'npm_executable': npm_executable,
        'attempted_total': len(package_specs),
        'successful': successful,
        'failures': failures,
        'offline_validation_complete': validation_result.returncode == 0,
        'offline_validation_error': (
            '' if validation_result.returncode == 0 else summarize_error(validation_result)
        ),
        'artifact_file_count': count_files(vendor_dir),
    }


def write_reports(
    report: dict,
    *,
    report_json: Path,
    report_md: Path,
) -> None:
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_md.parent.mkdir(parents=True, exist_ok=True)

    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    python_failures = report['python']['direct_failures']
    npm_failures = report['npm']['failures']

    lines = [
        '# Vendor Dependency Prefetch Report',
        '',
        f"- Generated at: `{report['generated_at']}`",
        f"- Mode: `{report['mode']}`",
        f"- Python vendor dir: `{report['python']['vendor_dir']}`",
        f"- NPM vendor dir: `{report['npm']['vendor_dir']}`",
        '',
        '## Python',
        '',
        f"- Direct requirements total: `{report['python']['direct_requirements_total']}`",
        f"- Direct requirements downloaded: `{len(report['python']['direct_successful'])}`",
        f"- Direct requirements missing: `{len(python_failures)}`",
        f"- Requirement bundle failures: `{len(report['python']['bundle_failures'])}`",
        f"- Full dependency closure complete: `{report['python']['full_dependency_download_complete']}`",
        f"- Offline vendor validation complete: `{report['python']['offline_validation_complete']}`",
        f"- Artifact files in vendor/python: `{report['python']['artifact_file_count']}`",
    ]

    if report['python']['full_dependency_error']:
        lines.extend(['', f"- Full dependency error: `{report['python']['full_dependency_error']}`"])
    if report['python']['offline_validation_error']:
        lines.extend(['', f"- Offline validation error: `{report['python']['offline_validation_error']}`"])

    lines.extend(['', '### Python Missing'])
    if python_failures:
        lines.extend([f"- `{item['requirement']}`: {item['error']}" for item in python_failures])
    else:
        lines.append('- None')

    lines.extend(['', '### Python Bundle Failures'])
    if report['python']['bundle_failures']:
        lines.extend(
            [f"- `{item['requirement']}`: {item['error']}" for item in report['python']['bundle_failures']]
        )
    else:
        lines.append('- None')

    lines.extend(
        [
            '',
            '## NPM',
            '',
            f"- Packages attempted: `{report['npm']['attempted_total']}`",
            f"- Packages cached: `{len(report['npm']['successful'])}`",
            f"- Packages missing: `{len(npm_failures)}`",
            f"- Offline vendor validation complete: `{report['npm']['offline_validation_complete']}`",
            f"- Artifact files in vendor/npm: `{report['npm']['artifact_file_count']}`",
            '',
            '### NPM Missing',
        ]
    )
    if npm_failures:
        lines.extend([f"- `{item['package']}`: {item['error']}" for item in npm_failures])
    else:
        lines.append('- None')

    if report['npm']['offline_validation_error']:
        lines.extend(['', f"- NPM validation error: `{report['npm']['offline_validation_error']}`"])

    lines.extend(
        [
            '',
            '## 手工补包命令',
            '',
            '### Python',
        ]
    )
    if python_failures or report['python']['bundle_failures']:
        seen_python_commands: set[str] = set()
        for item in python_failures + report['python']['bundle_failures']:
            command = item.get('suggested_command', '').strip()
            if command and command not in seen_python_commands:
                seen_python_commands.add(command)
                lines.append(f'- `{command}`')
    else:
        lines.append('- None')

    lines.extend(['', '### NPM'])
    if npm_failures:
        seen_npm_commands: set[str] = set()
        for item in npm_failures:
            command = item.get('suggested_command', '').strip()
            if command and command not in seen_npm_commands:
                seen_npm_commands.add(command)
                lines.append(f'- `{command}`')
    else:
        lines.append('- None')

    lines.extend(
        [
            '',
            '## Next Step',
            '',
            '- 把报告里缺失的包在外网环境补齐后放回对应 vendor 目录。',
            '- 然后运行 `python start.py`，它会优先使用这两个 vendor 目录安装。',
        ]
    )

    report_md.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    start.maybe_reexec_with_supported_python(
        args,
        script_path=Path(__file__).resolve(),
        forwarded_args=argv if argv is not None else sys.argv[1:],
    )

    python_vendor_dir = Path(args.python_dir).resolve()
    npm_vendor_dir = Path(args.npm_dir).resolve()
    report_json = Path(args.report_json).resolve()
    report_md = Path(args.report_md).resolve()

    python_executable = sys.executable
    pip_mirror = start.discover_pip_mirror(python_executable)
    pip_env = start.build_pip_env(pip_mirror)

    try:
        npm_executable = start.npm_command()
    except SystemExit as exc:
        npm_executable = None
        start.log(f'npm 不可用，前端预下载将写入缺失报告: {exc}')

    npm_registry = start.discover_npm_registry(npm_executable) if npm_executable else start.NpmRegistry()
    npm_env = start.build_npm_env(npm_registry)
    log(f"mode={'dry-run' if args.dry_run else 'download'} verbose={'on' if args.verbose else 'off'}")

    start.log(f'Python 预下载目录: {python_vendor_dir}')
    start.log(f'NPM 预下载目录: {npm_vendor_dir}')
    if pip_mirror.index_url:
        start.log(f'使用 pip 镜像: {pip_mirror.index_url}')
    else:
        start.log('未检测到 pip 镜像，将使用默认 pip 配置。')
    if npm_registry.registry:
        start.log(f'使用 npm registry: {npm_registry.registry}')
    else:
        start.log('未检测到 npm registry，将使用默认 npm 配置。')

    python_report = prefetch_python_dependencies(
        python_executable,
        vendor_dir=python_vendor_dir,
        pip_env=pip_env,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    npm_report = prefetch_npm_dependencies(
        npm_executable,
        vendor_dir=npm_vendor_dir,
        npm_env=npm_env,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'dry-run' if args.dry_run else 'download',
        'python': {
            **python_report,
            'mirror': {
                'index_url': pip_mirror.index_url,
                'extra_index_url': pip_mirror.extra_index_url,
                'trusted_host': pip_mirror.trusted_host,
                'index_source': pip_mirror.index_source,
                'extra_source': pip_mirror.extra_source,
                'trusted_source': pip_mirror.trusted_source,
            },
        },
        'npm': {
            **npm_report,
            'registry': {
                'registry': npm_registry.registry,
                'source': npm_registry.source,
            },
        },
    }

    log('Final phase: writing JSON/Markdown reports')
    write_reports(report, report_json=report_json, report_md=report_md)
    log(f'report json: {report_json}')
    log(f'report md: {report_md}')
    log('Final phase: report writing complete')

    start.log(f'预下载报告已写入: {report_json}')
    start.log(f'可读报告已写入: {report_md}')

    has_failures = bool(report['python']['direct_failures'] or report['npm']['failures'])
    has_incomplete_python_closure = not report['python']['full_dependency_download_complete']
    has_offline_validation_gap = (
        (not args.dry_run and not report['python']['offline_validation_complete'])
        or not report['npm']['offline_validation_complete']
    )
    return 1 if has_failures or has_incomplete_python_closure or has_offline_validation_gap else 0


if __name__ == '__main__':
    raise SystemExit(main())
