"""Process queued GitHub webhook deploy jobs on the hosting server."""

from __future__ import annotations

import argparse
import base64
import json
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
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_HTML = ROOT.parent / "public_html"
DEFAULT_CONFIG = DEFAULT_PUBLIC_HTML / ".private" / "pca-deploy-config.json"


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
def queue_dir(config): return cfg_path(config, "queue_dir", public_html(config) / ".private" / "deploy-queue")
def log_dir(config): return cfg_path(config, "log_dir", public_html(config) / ".private" / "deploy-logs")
def worktree_dir(config): return cfg_path(config, "worktree_dir", site_src(config) / ".deploy-worktrees")
def python_bin(config): return str(config.get("python") or sys.executable or shutil.which("python3") or shutil.which("python"))


def repo_full_name(config: dict[str, Any]) -> str:
    repo = str(config.get("repository") or "").strip()
    if not repo:
        raise DeployError("Missing repository in deploy config.")
    return repo


def base_url(config, key, default): return str(config.get(key) or default).rstrip("/")
def production_url(config): return f"{base_url(config, 'production_base_url', 'https://polandchildabduction.pl')}/"
def preview_url(config, pr_number): return f"{base_url(config, 'preview_base_url', 'https://preview.polandchildabduction.pl')}/pr-{pr_number}/"
def preview_log_url(config, pr_number): return f"{preview_url(config, pr_number)}_deploy.log"


def run(command: list[str], cwd: Path, log, check: bool = True) -> None:
    log.write("\n$ " + " ".join(command) + "\n")
    log.flush()
    rc = subprocess.run(command, cwd=str(cwd), text=True, stdout=log, stderr=subprocess.STDOUT).returncode
    log.write(f"\n[exit {rc}]\n")
    log.flush()
    if check and rc != 0:
        raise DeployError(f"Command failed with exit code {rc}: {' '.join(command)}")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def github_app_private_key(config: dict[str, Any]) -> Path:
    value = config.get("github_app_private_key_path")
    if not value:
        raise DeployError("Missing github_app_private_key_path in deploy config.")
    path = Path(str(value)).expanduser().resolve()
    if not path.is_file():
        raise DeployError(f"GitHub App private key not found: {path}")
    return path


def github_app_jwt(config: dict[str, Any]) -> str:
    app_id = str(config.get("github_app_id") or "").strip()
    if not app_id:
        raise DeployError("Missing github_app_id in deploy config.")

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
    signing_input = (
        b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    ).encode("ascii")

    completed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(github_app_private_key(config))],
        input=signing_input,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise DeployError("Could not sign GitHub App JWT with openssl: " + completed.stderr.decode("utf-8", errors="replace"))

    return signing_input.decode("ascii") + "." + b64url(completed.stdout)


def github_request(token: str, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(f"https://api.github.com{path}", data=body, method=method)
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


def github_installation_token(config: dict[str, Any]) -> str:
    cached = config.get("_github_installation_token")
    if cached:
        return str(cached)

    installation_id = str(config.get("github_app_installation_id") or "").strip()
    if not installation_id:
        raise DeployError("Missing github_app_installation_id in deploy config.")

    data = github_request(github_app_jwt(config), "POST", f"/app/installations/{installation_id}/access_tokens")
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise DeployError("GitHub App installation token response did not include token.")

    config["_github_installation_token"] = token
    return str(token)


def github_api(config, method, path, data=None):
    return github_request(github_installation_token(config), method, path, data)


def create_check_run(config, name, sha, details_url, title, summary, external_id=None):
    if not sha:
        return None
    payload = {
        "name": name,
        "head_sha": sha,
        "status": "in_progress",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "details_url": details_url,
        "output": {"title": title, "summary": summary},
    }
    if external_id:
        payload["external_id"] = external_id
    return github_api(config, "POST", f"/repos/{repo_full_name(config)}/check-runs", payload)


def update_check_run(config, check_run, conclusion, details_url, title, summary):
    if not isinstance(check_run, dict) or not check_run.get("id"):
        return
    github_api(config, "PATCH", f"/repos/{repo_full_name(config)}/check-runs/{check_run['id']}", {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "details_url": details_url,
        "output": {"title": title, "summary": summary},
    })


def get_pull_request(config, pr_number):
    data = github_api(config, "GET", f"/repos/{repo_full_name(config)}/pulls/{pr_number}")
    if not isinstance(data, dict):
        raise DeployError(f"Could not load PR #{pr_number} from GitHub API.")
    return data


def install_requirements(config, root, log):
    requirements = root / "requirements.txt"
    if requirements.is_file():
        py = python_bin(config)
        run([py, "-m", "pip", "install", "--upgrade", "pip"], root, log)
        run([py, "-m", "pip", "install", "-r", str(requirements)], root, log)


def run_build_and_publish(config, root, dest, log, extra=None):
    command = [python_bin(config), str(root / "tools" / "build_and_publish.py"), "--root", str(root), "--dest", str(dest)]
    if extra:
        command.extend(extra)
    run(command, root, log)


def publish_preview_log(config, pr_number, source):
    dest = preview_root(config) / f"pr-{pr_number}"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest / "_deploy.log")


def ensure_same_repo_preview(config, job):
    if bool(config.get("allow_preview_from_forks", False)):
        return
    head_repo = str(job.get("head_repo") or "")
    base_repo = str(job.get("base_repo") or job.get("repository") or repo_full_name(config))
    if head_repo and base_repo and head_repo != base_repo:
        raise DeployError(f"Refusing to build preview from forked repository: {head_repo}")


def deploy_production(config, job):
    sha = str(job.get("sha") or "") or None
    root = site_src(config)
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"production-{(sha or time.strftime('%Y%m%d-%H%M%S'))[:12]}.log"
    check_run = create_check_run(
        config,
        "PCA Production Deploy",
        sha,
        production_url(config),
        "Production deploy started",
        f"Production deploy started for `{sha or 'unknown'}`.",
        external_id=f"production-{sha or int(time.time())}",
    )
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"Production deploy job: {json.dumps(job, ensure_ascii=False)}\n")
            run(["git", "fetch", "origin", "main"], root, log)
            run(["git", "checkout", "main"], root, log)
            run(["git", "reset", "--hard", "origin/main"], root, log)
            install_requirements(config, root, log)
            run_build_and_publish(config, root, public_html(config), log)
    except Exception as exc:
        update_check_run(
            config,
            check_run,
            "failure",
            production_url(config),
            "Production deploy failed",
            f"Production deploy failed.\n\nError: `{exc}`",
        )
        raise
    update_check_run(
        config,
        check_run,
        "success",
        production_url(config),
        "Production deployed",
        f"Production deploy completed successfully.\n\nSite: {production_url(config)}",
    )


def normalize_preview_job(config, job):
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


def prepare_preview_worktree(config, pr_number, log):
    root = site_src(config)
    target = worktree_dir(config) / f"pr-{pr_number}"
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "fetch", "origin", f"pull/{pr_number}/head"], root, log)
    if target.exists():
        run(["git", "worktree", "remove", "--force", str(target)], root, log, check=False)
        shutil.rmtree(target, ignore_errors=True)
    run(["git", "worktree", "add", "--force", "--detach", str(target), "FETCH_HEAD"], root, log)
    return target


def preview_summary(pr_number, url, log_url, status):
    return f"Preview deploy {status} for PR #{pr_number}.\n\n- Preview: {url}\n- Build log: {log_url}"


def deploy_preview(config, job):
    job = normalize_preview_job(config, job)
    pr_number = int(job["pr_number"])
    sha = str(job.get("sha") or "") or None
    url = preview_url(config, pr_number)
    log_url = preview_log_url(config, pr_number)
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"preview-pr-{pr_number}-{(sha or time.strftime('%Y%m%d-%H%M%S'))[:12]}.log"

    check_run = create_check_run(
        config,
        "PCA Preview Deploy",
        sha,
        url,
        "Preview deploy started",
        preview_summary(pr_number, url, log_url, "started"),
        external_id=f"preview-pr-{pr_number}-{sha or int(time.time())}",
    )
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"Preview deploy job: {json.dumps(job, ensure_ascii=False)}\n")
            root = prepare_preview_worktree(config, pr_number, log)
            install_requirements(config, root, log)
            run_build_and_publish(config, root, preview_root(config) / f"pr-{pr_number}", log, [
                "--url-prefix", f"/pr-{pr_number}", "--lang-in-url", "--write-preview-index",
            ])
    except Exception as exc:
        if log_path.exists():
            publish_preview_log(config, pr_number, log_path)
        update_check_run(
            config,
            check_run,
            "failure",
            log_url,
            "Preview deploy failed",
            preview_summary(pr_number, url, log_url, "failed") + f"\n\nError: `{exc}`",
        )
        raise

    publish_preview_log(config, pr_number, log_path)
    update_check_run(
        config,
        check_run,
        "success",
        url,
        "Preview deployed",
        preview_summary(pr_number, url, log_url, "succeeded"),
    )


def cleanup_preview(config, job):
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Cleanup job is missing pr_number.")
    target = preview_root(config) / f"pr-{pr_number}"
    if target.exists():
        shutil.rmtree(target)


def handle_job(config, job):
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


def process_queue(config, max_jobs):
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


def main():
    parser = argparse.ArgumentParser(description="Process queued PCA deploy webhook jobs.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="deploy config JSON path")
    parser.add_argument("--max-jobs", type=int, default=10, help="maximum queued jobs to process in one run")
    args = parser.parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    with worker_lock(config):
        count = process_queue(config, args.max_jobs)
    print(f"Processed deploy jobs: {count}")


if __name__ == "__main__":
    main()
