"""Process queued GitHub webhook deploy jobs on the hosting server.

This worker is intended to be run from cron. The public webhook endpoint writes
small JSON jobs to a private queue, and this worker performs the slower work:
fetching Git refs, building, publishing, writing logs, and updating GitHub commit
statuses.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - worker is designed for Linux hosting.
    fcntl = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_HTML = ROOT.parent / "public_html"
DEFAULT_CONFIG = DEFAULT_PUBLIC_HTML / ".private" / "pca-deploy-config.json"


class DeployError(RuntimeError):
    """Raised when one queued deploy job fails."""


def now_slug() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Missing deploy config: {path}")

    with path.open("r", encoding="utf-8") as fh:
        config = json.load(fh)

    if not isinstance(config, dict):
        raise SystemExit("Deploy config must be a JSON object.")

    return config


def path_from_config(config: dict[str, Any], key: str, default: Path) -> Path:
    value = config.get(key)
    return Path(str(value)).expanduser().resolve() if value else default.expanduser().resolve()


def site_src(config: dict[str, Any]) -> Path:
    return path_from_config(config, "site_src", ROOT)


def public_html(config: dict[str, Any]) -> Path:
    return path_from_config(config, "public_html", site_src(config).parent / "public_html")


def preview_root(config: dict[str, Any]) -> Path:
    return path_from_config(config, "preview_root", public_html(config) / "preview")


def queue_dir(config: dict[str, Any]) -> Path:
    return path_from_config(config, "queue_dir", public_html(config) / ".private" / "deploy-queue")


def log_dir(config: dict[str, Any]) -> Path:
    return path_from_config(config, "log_dir", public_html(config) / ".private" / "deploy-logs")


def worktree_dir(config: dict[str, Any]) -> Path:
    return path_from_config(config, "worktree_dir", site_src(config) / ".deploy-worktrees")


def python_bin(config: dict[str, Any]) -> str:
    return str(config.get("python") or sys.executable or shutil.which("python3") or shutil.which("python"))


def base_url(config: dict[str, Any], key: str, default: str) -> str:
    return str(config.get(key) or default).rstrip("/")


def preview_url(config: dict[str, Any], pr_number: int) -> str:
    return f"{base_url(config, 'preview_base_url', 'https://preview.polandchildabduction.pl')}/pr-{pr_number}/"


def preview_log_url(config: dict[str, Any], pr_number: int) -> str:
    return f"{preview_url(config, pr_number)}_deploy.log"


def production_url(config: dict[str, Any]) -> str:
    return f"{base_url(config, 'production_base_url', 'https://polandchildabduction.pl')}/"


def repo_full_name(config: dict[str, Any]) -> str:
    repo = str(config.get("repository") or "").strip()
    if not repo:
        raise DeployError("Missing repository in deploy config.")
    return repo


def run(command: list[str], cwd: Path, log, check: bool = True) -> subprocess.CompletedProcess[str]:
    log.write("\n$ " + " ".join(command) + "\n")
    log.flush()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    log.write(f"\n[exit {completed.returncode}]\n")
    log.flush()

    if check and completed.returncode != 0:
        raise DeployError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")

    return completed


def github_api(config: dict[str, Any], method: str, path: str, data: dict[str, Any] | None = None) -> Any:
    token = str(config.get("github_token") or "").strip()
    if not token:
        return None

    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise DeployError(f"GitHub API {method} {path} failed: {exc.code} {raw}") from exc


def set_status(
    config: dict[str, Any],
    sha: str | None,
    state: str,
    context: str,
    description: str,
    target_url: str,
) -> None:
    if not sha:
        return

    github_api(
        config,
        "POST",
        f"/repos/{repo_full_name(config)}/statuses/{sha}",
        {
            "state": state,
            "context": context,
            "description": description[:140],
            "target_url": target_url,
        },
    )


def get_pull_request(config: dict[str, Any], pr_number: int) -> dict[str, Any]:
    data = github_api(config, "GET", f"/repos/{repo_full_name(config)}/pulls/{pr_number}")
    if not isinstance(data, dict):
        raise DeployError(f"Could not load PR #{pr_number} from GitHub API.")
    return data


def upsert_pr_comment(config: dict[str, Any], pr_number: int, marker: str, body: str) -> None:
    comments = github_api(config, "GET", f"/repos/{repo_full_name(config)}/issues/{pr_number}/comments?per_page=100")
    existing_id = None

    if isinstance(comments, list):
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            user = comment.get("user") or {}
            if user.get("login") == "github-actions[bot]" and marker in str(comment.get("body") or ""):
                existing_id = comment.get("id")

    if existing_id:
        github_api(config, "PATCH", f"/repos/{repo_full_name(config)}/issues/comments/{existing_id}", {"body": body})
    else:
        github_api(config, "POST", f"/repos/{repo_full_name(config)}/issues/{pr_number}/comments", {"body": body})


def ensure_same_repo_preview(config: dict[str, Any], job: dict[str, Any]) -> None:
    if bool(config.get("allow_preview_from_forks", False)):
        return

    head_repo = str(job.get("head_repo") or "")
    base_repo = str(job.get("base_repo") or job.get("repository") or repo_full_name(config))

    if head_repo and base_repo and head_repo != base_repo:
        raise DeployError(f"Refusing to build preview from forked repository: {head_repo}")


def install_requirements(config: dict[str, Any], root: Path, log) -> None:
    python = python_bin(config)
    requirements = root / "requirements.txt"
    if requirements.is_file():
        run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root, log=log)
        run([python, "-m", "pip", "install", "-r", str(requirements)], cwd=root, log=log)


def run_build_and_publish(config: dict[str, Any], root: Path, dest: Path, log, extra_args: list[str] | None = None) -> None:
    python = python_bin(config)
    script = root / "tools" / "build_and_publish.py"
    command = [python, str(script), "--root", str(root), "--dest", str(dest)]
    if extra_args:
        command.extend(extra_args)
    run(command, cwd=root, log=log)


def production_log_path(config: dict[str, Any], sha: str | None) -> Path:
    slug = sha[:12] if sha else now_slug()
    directory = log_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"production-{slug}.log"


def preview_private_log_path(config: dict[str, Any], pr_number: int, sha: str | None) -> Path:
    slug = sha[:12] if sha else now_slug()
    directory = log_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"preview-pr-{pr_number}-{slug}.log"


def publish_preview_log(config: dict[str, Any], pr_number: int, source: Path) -> None:
    dest_dir = preview_root(config) / f"pr-{pr_number}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest_dir / "_deploy.log")


def deploy_production(config: dict[str, Any], job: dict[str, Any]) -> None:
    sha = str(job.get("sha") or "") or None
    log_path = production_log_path(config, sha)
    root = site_src(config)

    set_status(config, sha, "pending", "pca/production", "Production deploy started", production_url(config))

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Production deploy job: {json.dumps(job, ensure_ascii=False)}\n")
        run(["git", "fetch", "origin", "main"], cwd=root, log=log)
        run(["git", "checkout", "main"], cwd=root, log=log)
        run(["git", "reset", "--hard", "origin/main"], cwd=root, log=log)
        install_requirements(config, root, log)
        run_build_and_publish(config, root, public_html(config), log)

    set_status(config, sha, "success", "pca/production", "Production deployed", production_url(config))


def prepare_preview_worktree(config: dict[str, Any], pr_number: int, log) -> Path:
    root = site_src(config)
    directory = worktree_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"pr-{pr_number}"

    run(["git", "fetch", "origin", f"pull/{pr_number}/head"], cwd=root, log=log)
    if target.exists():
        run(["git", "worktree", "remove", "--force", str(target)], cwd=root, log=log, check=False)
        shutil.rmtree(target, ignore_errors=True)

    run(["git", "worktree", "add", "--force", "--detach", str(target), "FETCH_HEAD"], cwd=root, log=log)
    return target


def normalize_preview_job(config: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Preview job is missing pr_number.")

    if job.get("type") == "preview_comment" or not job.get("sha"):
        pr = get_pull_request(config, pr_number)
        job = dict(job)
        job["sha"] = pr.get("head", {}).get("sha")
        job["head_repo"] = pr.get("head", {}).get("repo", {}).get("full_name")
        job["base_repo"] = pr.get("base", {}).get("repo", {}).get("full_name")

    ensure_same_repo_preview(config, job)
    return job


def deploy_preview(config: dict[str, Any], job: dict[str, Any]) -> None:
    job = normalize_preview_job(config, job)
    pr_number = int(job["pr_number"])
    sha = str(job.get("sha") or "") or None
    log_path = preview_private_log_path(config, pr_number, sha)
    url = preview_url(config, pr_number)
    log_url = preview_log_url(config, pr_number)

    set_status(config, sha, "pending", "pca/preview", "Preview deploy started", url)

    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"Preview deploy job: {json.dumps(job, ensure_ascii=False)}\n")
            root = prepare_preview_worktree(config, pr_number, log)
            install_requirements(config, root, log)
            run_build_and_publish(
                config,
                root,
                preview_root(config) / f"pr-{pr_number}",
                log,
                [
                    "--url-prefix",
                    f"/pr-{pr_number}",
                    "--lang-in-url",
                    "--write-preview-index",
                ],
            )
    finally:
        if log_path.exists():
            publish_preview_log(config, pr_number, log_path)

    marker = "<!-- pca-webhook-preview -->"
    body = (
        f"{marker}\n"
        f"Preview deployed for PR #{pr_number}.\n\n"
        f"- Preview: {url}\n"
        f"- Build log: {log_url}"
    )
    upsert_pr_comment(config, pr_number, marker, body)
    set_status(config, sha, "success", "pca/preview", "Preview deployed", url)


def cleanup_preview(config: dict[str, Any], job: dict[str, Any]) -> None:
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Cleanup job is missing pr_number.")

    target = preview_root(config) / f"pr-{pr_number}"
    if target.exists():
        shutil.rmtree(target)


def handle_job(config: dict[str, Any], job: dict[str, Any]) -> None:
    job_type = str(job.get("type") or "")

    if job_type == "production":
        deploy_production(config, job)
        return

    if job_type in {"preview", "preview_comment"}:
        deploy_preview(config, job)
        return

    if job_type == "cleanup_preview":
        cleanup_preview(config, job)
        return

    raise DeployError(f"Unknown job type: {job_type}")


@contextmanager
def worker_lock(config: dict[str, Any]):
    lock_path = queue_dir(config).parent / "deploy-worker.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def process_queue(config: dict[str, Any], max_jobs: int) -> int:
    directory = queue_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    processed = 0

    for path in sorted(directory.glob("*.json")):
        if processed >= max_jobs:
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
        except Exception as exc:  # Keep failed jobs for inspection.
            failed.write_text(running.read_text(encoding="utf-8") + f"\nERROR: {exc}\n", encoding="utf-8")
            running.unlink(missing_ok=True)
            print(f"Deploy job failed: {running.name}: {exc}", file=sys.stderr)
        processed += 1

    return processed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process queued PCA deploy webhook jobs.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="deploy config JSON path")
    parser.add_argument("--max-jobs", type=int, default=10, help="maximum queued jobs to process in one run")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())

    with worker_lock(config):
        count = process_queue(config, args.max_jobs)

    print(f"Processed deploy jobs: {count}")


if __name__ == "__main__":
    main()
