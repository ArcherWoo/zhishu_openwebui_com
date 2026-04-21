from pathlib import Path
import tomllib

import start


def parse_requirements(requirements_file: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}

    for raw_line in requirements_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, version = line.split("==", 1)
        requirements[name.strip()] = version.strip()

    return requirements


def parse_pyproject_dependencies(pyproject_file: Path) -> dict[str, str]:
    data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    dependencies: dict[str, str] = {}

    for item in data["project"]["dependencies"]:
        if "==" not in item:
            continue
        name, version = item.split("==", 1)
        dependencies[name.strip()] = version.strip()

    return dependencies


def test_powerpoint_runtime_dependencies_are_declared_consistently():
    requirements = parse_requirements(start.REQUIREMENTS_FILE)
    pyproject = parse_pyproject_dependencies(start.ROOT / "pyproject.toml")

    assert requirements.get("markitdown[pptx]") == "0.1.5"
    assert pyproject.get("markitdown[pptx]") == "0.1.5"
    assert requirements.get("onnxruntime") == "1.20.1"
    assert pyproject.get("onnxruntime") == "1.20.1"


def test_build_python_install_commands_include_ppt_offline_runtime_wheels(monkeypatch, tmp_path):
    venv_python = tmp_path / "python.exe"
    requirements_file = tmp_path / "requirements.txt"
    vendor_dir = tmp_path / "vendor-python"
    ppt_wheels_dir = tmp_path / "ppt_offline_runtime" / "wheels"

    requirements_file.write_text("onnxruntime==1.20.1\n", encoding="utf-8")
    vendor_dir.mkdir()
    ppt_wheels_dir.mkdir(parents=True)

    monkeypatch.setattr(start, "PPT_OFFLINE_RUNTIME_WHEELS_DIR", ppt_wheels_dir, raising=False)

    local_only_command, fallback_command = start.build_python_install_commands(
        venv_python=venv_python,
        vendor_dir=vendor_dir,
        requirements_file=requirements_file,
    )

    assert local_only_command == [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(vendor_dir),
        "--find-links",
        str(ppt_wheels_dir),
        "-r",
        str(requirements_file),
    ]
    assert fallback_command == [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--find-links",
        str(vendor_dir),
        "--find-links",
        str(ppt_wheels_dir),
        "-r",
        str(requirements_file),
    ]
