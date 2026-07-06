from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_HTML = ROOT.parent / "public_html"
DEFAULT_PREVIEW_ROOT = DEFAULT_PUBLIC_HTML / "preview"
DEFAULT_CONFIG = DEFAULT_PREVIEW_ROOT / ".private" / "pca-deploy-config.json"


class DeployError(RuntimeError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Missing deploy config: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Deploy config must be a JSON object.")
    return data


def cfg_path(config: dict[str, Any], key: str, default: Path) -> Path:
    value = config.get(key)
    return Path(str(value)).expanduser().resolve() if value else default.expanduser().resolve()


def site_src(config): return cfg_path(config, "site_src", ROOT)
def public_html(config): return cfg_path(config, "public_html", site_src(config).parent / "public_html")
def preview_root(config): return cfg_path(config, "preview_root", public_html(config) / "preview")
def private_dir(config): return cfg_path(config, "private_dir", preview_root(config) / ".private")
def queue_dir(config): return cfg_path(config, "queue_dir", private_dir(config) / "deploy-queue")
def log_dir(config): return cfg_path(config, "log_dir", private_dir(config) / "deploy-logs")
def worktree_dir(config): return cfg_path(config, "worktree_dir", site_src(config) / ".deploy-worktrees")
def python_bin(config): return str(config.get("python") or sys.executable or shutil.which("python3") or shutil.which("python"))


def run(command: list[str], cwd: Path, log, check: bool = True) -> None:
    log.write("\n$ " + " ".join(command) + "\n")
    log.flush()
    rc = subprocess.run(command, cwd=str(cwd), text=True, stdout=log, stderr=subprocess.STDOUT).returncode
    log.write(f"\n[exit {rc}]\n")
    log.flush()
    if check and rc != 0:
        raise DeployError(f"Command failed with exit code {rc}: {' '.join(command)}")


def install_requirements(config, root: Path, log) -> None:
    requirements = root / "requirements.txt"
    if requirements.is_file():
        py = python_bin(config)
        run([py, "-m", "pip", "install", "--upgrade", "pip"], root, log)
        run([py, "-m", "pip", "install", "-r", str(requirements)], root, log)


def run_builder(config, root: Path, log, *args: str) -> None:
    run([python_bin(config), str(root / "tools" / "build.py"), *args], root, log)


def deploy_production(config, job: dict[str, Any]) -> None:
    root = site_src(config)
    sha = str(job.get("sha") or time.strftime("%Y%m%d-%H%M%S"))[:12]
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"production-{sha}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Production deploy job: {json.dumps(job, ensure_ascii=False)}\n")
        run(["git", "fetch", "origin", "main"], root, log)
        run(["git", "checkout", "main"], root, log)
        run(["git", "reset", "--hard", "origin/main"], root, log)
        install_requirements(config, root, log)
        run_builder(config, root, log, "deploy", "--root", str(root), "--to", str(public_html(config)))


def prepare_preview_worktree(config, pr_number: int, log) -> Path:
    root = site_src(config)
    target = worktree_dir(config) / f"pr-{pr_number}"
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "fetch", "origin", f"pull/{pr_number}/head"], root, log)
    if target.exists():
        run(["git", "worktree", "remove", "--force", str(target)], root, log, check=False)
        shutil.rmtree(target, ignore_errors=True)
    run(["git", "worktree", "add", "--force", "--detach", str(target), "FETCH_HEAD"], root, log)
    return target


def publish_preview_log(config, pr_number: int, source: Path) -> None:
    dest = preview_root(config) / f"pr-{pr_number}"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest / "_deploy.log")


def deploy_preview(config, job: dict[str, Any]) -> None:
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Preview job is missing pr_number.")
    sha = str(job.get("sha") or time.strftime("%Y%m%d-%H%M%S"))[:12]
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"preview-pr-{pr_number}-{sha}.log"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Preview deploy job: {json.dumps(job, ensure_ascii=False)}\n")
        root = prepare_preview_worktree(config, pr_number, log)
        install_requirements(config, root, log)
        run_builder(
            config,
            root,
            log,
            "preview",
            "--root", str(root),
            "--to", str(preview_root(config) / f"pr-{pr_number}"),
            "--prefix", f"pr-{pr_number}",
        )
    publish_preview_log(config, pr_number, log_path)


def cleanup_preview(config, job: dict[str, Any]) -> None:
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Cleanup job is missing pr_number.")
    target = preview_root(config) / f"pr-{pr_number}"
    if target.exists():
        shutil.rmtree(target)


def handle_job(config, job: dict[str, Any]) -> None:
    job_type = str(job.get("type") or "")
    if job_type == "production":
        deploy_production(config, job)
    elif job_type in {"preview", "preview_comment"}:
        deploy_preview(config, job)
    elif job_type == "cleanup_preview":
        cleanup_preview(config, job)
    else:
        raise DeployError(f"Unknown job type: {job_type}")


@contextmanager
def worker_lock(config):
    path = queue_dir(config).parent / "deploy-worker.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def process_queue(config, max_jobs: int) -> int:
    directory = queue_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(directory.glob("*.json")):
        if count >= max_jobs:
            break
        running = path.with_suffix(".running")
        done = path.with_suffix(".done")
        failed = path.with_suffix(".failed")
        path.rename(running)
        try:
            job = json.loads(running.read_text(encoding="utf-8"))
            if not isinstance(job, dict):
                raise DeployError("Queued job JSON is not an object.")
            handle_job(config, job)
            running.rename(done)
        except Exception as exc:
            failed.write_text(running.read_text(encoding="utf-8") + f"\nERROR: {exc}\n", encoding="utf-8")
            running.unlink(missing_ok=True)
            print(f"Deploy job failed: {running.name}: {exc}", file=sys.stderr)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued PCA deploy jobs.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--max-jobs", type=int, default=5)
    args = parser.parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    with worker_lock(config):
        processed = process_queue(config, args.max_jobs)
    if processed:
        print(f"Processed {processed} deploy job(s).")


if __name__ == "__main__":
    main()
