from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class PreviewSandboxError(RuntimeError):
    pass


def _runtime(config: dict[str, Any]) -> str:
    configured = str(config.get("preview_container_runtime") or "").strip()
    if configured:
        found = shutil.which(configured)
        if not found:
            raise PreviewSandboxError(f"Configured preview container runtime is unavailable: {configured}")
        return found
    for candidate in ("podman", "docker"):
        found = shutil.which(candidate)
        if found:
            return found
    raise PreviewSandboxError("Preview builds require Podman or Docker; refusing to execute PR code on the host.")


def _image(config: dict[str, Any]) -> str:
    image = str(config.get("preview_container_image") or "python:3.13-slim").strip()
    if not image:
        raise PreviewSandboxError("preview_container_image must not be empty")
    return image


def _limit(config: dict[str, Any], key: str, default: str) -> str:
    value = str(config.get(key) or default).strip()
    if not value:
        raise PreviewSandboxError(f"{key} must not be empty")
    return value


def _mount(source: Path, target: str, *, readonly: bool = False) -> str:
    mode = ",readonly" if readonly else ""
    return f"type=bind,src={source},dst={target}{mode}"


def _identity_args(runtime: str) -> list[str]:
    if Path(runtime).name == "podman":
        return ["--userns=keep-id"]
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _base_container_args(config: dict[str, Any], runtime: str, sandbox: Path) -> list[str]:
    return [
        runtime,
        "run",
        "--rm",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--pids-limit",
        _limit(config, "preview_pids_limit", "128"),
        "--memory",
        _limit(config, "preview_memory_limit", "512m"),
        "--cpus",
        _limit(config, "preview_cpu_limit", "1.0"),
        *_identity_args(runtime),
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
        "--env",
        "HOME=/sandbox/home",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--mount",
        _mount(sandbox, "/sandbox"),
    ]


def _run(command: list[str], cwd: Path, log) -> None:
    log.write("\n$ " + " ".join(command) + "\n")
    log.flush()
    rc = subprocess.run(command, cwd=str(cwd), text=True, stdout=log, stderr=subprocess.STDOUT).returncode
    log.write(f"\n[exit {rc}]\n")
    log.flush()
    if rc != 0:
        raise PreviewSandboxError(f"Sandbox command failed with exit code {rc}")


def _trusted_requirements(site_root: Path, preview_root: Path, sandbox: Path) -> Path | None:
    trusted = site_root / "requirements.txt"
    requested = preview_root / "requirements.txt"
    if requested.is_file() != trusted.is_file():
        raise PreviewSandboxError("PR changes Python dependencies; preview dependency changes must be reviewed on main first.")
    if not trusted.is_file():
        return None
    trusted_bytes = trusted.read_bytes()
    if requested.read_bytes() != trusted_bytes:
        raise PreviewSandboxError("PR changes Python dependencies; preview dependency changes must be reviewed on main first.")
    copied = sandbox / "requirements.txt"
    copied.write_bytes(trusted_bytes)
    return copied


def _validate_output(root: Path, *, max_files: int, max_bytes: int) -> None:
    files = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PreviewSandboxError(f"Preview output contains a symbolic link: {path.relative_to(root)}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PreviewSandboxError(f"Preview output contains a non-regular file: {path.relative_to(root)}")
        files += 1
        total += path.stat().st_size
        if files > max_files:
            raise PreviewSandboxError(f"Preview output exceeds file limit ({max_files})")
        if total > max_bytes:
            raise PreviewSandboxError(f"Preview output exceeds size limit ({max_bytes} bytes)")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _publish_output(source: Path, destination: Path) -> None:
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}-stage-", dir=parent))
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True, symlinks=False)
        _remove_path(destination)
        stage.rename(destination)
    finally:
        _remove_path(stage)


def run_sandboxed_preview(
    config: dict[str, Any],
    site_root: Path,
    preview_source: Path,
    destination: Path,
    prefix: str,
    log,
) -> None:
    runtime = _runtime(config)
    image = _image(config)
    sandbox_parent = Path(config.get("private_dir") or destination.parent / ".private").expanduser().resolve()
    sandbox_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="preview-sandbox-", dir=sandbox_parent) as temporary:
        sandbox = Path(temporary)
        (sandbox / "home").mkdir()
        dist = sandbox / "site-dist"
        output = sandbox / "output"
        dist.mkdir()
        output.mkdir()
        requirements = _trusted_requirements(site_root, preview_source, sandbox)
        base = _base_container_args(config, runtime, sandbox)

        if requirements is not None:
            _run(
                base
                + [
                    "--network",
                    str(config.get("preview_dependency_network") or "bridge"),
                    image,
                    "/bin/sh",
                    "-ec",
                    "python -m venv /sandbox/venv && /sandbox/venv/bin/python -m pip install --disable-pip-version-check --no-input -r /sandbox/requirements.txt",
                ],
                site_root,
                log,
            )
        else:
            _run(
                base
                + [
                    "--network=none",
                    image,
                    "/bin/sh",
                    "-ec",
                    "python -m venv /sandbox/venv",
                ],
                site_root,
                log,
            )

        build = _base_container_args(config, runtime, sandbox)
        build.extend(
            [
                "--network=none",
                "--mount",
                _mount(preview_source, "/src", readonly=True),
                "--mount",
                _mount(dist, "/site-dist"),
                "--mount",
                _mount(output, "/out"),
                "--workdir",
                "/src",
                image,
                "/sandbox/venv/bin/python",
                "/src/tools/build.py",
                "preview",
                "--root",
                "/src",
                "--to",
                "/out",
                "--prefix",
                prefix,
                "--no-format",
            ]
        )
        _run(build, site_root, log)

        max_files = int(config.get("preview_max_files") or 10000)
        max_bytes = int(config.get("preview_max_bytes") or 100 * 1024 * 1024)
        _validate_output(output, max_files=max_files, max_bytes=max_bytes)
        _publish_output(output, destination)
