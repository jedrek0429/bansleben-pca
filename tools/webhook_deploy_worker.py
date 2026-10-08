from __future__ import annotations

import argparse
import base64
import hashlib
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

from preview_sandbox import run_sandboxed_preview

try:
    import fcntl
except ImportError:
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_HTML = ROOT.parent / "public_html"
DEFAULT_PREVIEW_ROOT = DEFAULT_PUBLIC_HTML / "preview"
DEFAULT_CONFIG = DEFAULT_PREVIEW_ROOT / ".private" / "pca-deploy-config.json"
PREVIEW_COMMENT_MARKER = "<!-- pca-preview-deploy-comment -->"


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


def repo_full_name(config):
    repo = str(config.get("repository") or "").strip()
    if not repo:
        raise DeployError("Missing repository in deploy config.")
    return repo


def base_url(config, key, default): return str(config.get(key) or default).rstrip("/")
def production_url(config): return f"{base_url(config, 'production_base_url', 'https://polandchildabduction.pl')}/"
def preview_url(config, pr_number): return f"{base_url(config, 'preview_base_url', 'https://preview.polandchildabduction.pl')}/pr-{pr_number}/"
def preview_log_url(config, pr_number): return f"{preview_url(config, pr_number)}_deploy.log"


def with_trailing_slash(url: str) -> str:
    return str(url).strip().rstrip("/") + "/"


def production_site_urls(config: dict[str, Any]) -> dict[str, str]:
    fallback = {"en": production_url(config)}
    sites_dir = site_src(config) / "sites"
    if not sites_dir.is_dir():
        return fallback
    urls = {}
    for path in sorted(sites_dir.glob("*.json")):
        try:
            site = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        url = site.get("url") if isinstance(site, dict) else None
        if str(url or "").strip():
            urls[path.stem] = with_trailing_slash(str(url))
    return urls or fallback


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


def github_private_key(config: dict[str, Any]) -> Path:
    value = config.get("github_app_private_key_path")
    if not value:
        raise DeployError("Missing github_app_private_key_path in deploy config.")
    path = Path(str(value)).expanduser().resolve()
    if not path.is_file():
        raise DeployError(f"GitHub App private key not found: {path}")
    return path


def github_jwt(config: dict[str, Any]) -> str:
    app_id = str(config.get("github_app_id") or "").strip()
    if not app_id:
        raise DeployError("Missing github_app_id in deploy config.")
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
    signing_input = (
        b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(payload, separators=(",", ":")).encode())
    ).encode("ascii")
    signed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(github_private_key(config))],
        input=signing_input,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if signed.returncode != 0:
        raise DeployError("Could not sign GitHub App JWT: " + signed.stderr.decode("utf-8", errors="replace"))
    return signing_input.decode("ascii") + "." + b64url(signed.stdout)


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


def github_token(config: dict[str, Any]) -> str:
    if config.get("_github_token"):
        return str(config["_github_token"])
    installation_id = str(config.get("github_app_installation_id") or "").strip()
    if not installation_id:
        raise DeployError("Missing github_app_installation_id in deploy config.")
    data = github_request(github_jwt(config), "POST", f"/app/installations/{installation_id}/access_tokens")
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        raise DeployError("GitHub App installation token response did not include token.")
    config["_github_token"] = token
    return str(token)


def github_api(config, method, path, data=None):
    return github_request(github_token(config), method, path, data)


def create_check(config, name, sha, details_url, title, summary, external_id):
    if not sha:
        return None
    return github_api(config, "POST", f"/repos/{repo_full_name(config)}/check-runs", {
        "name": name,
        "head_sha": sha,
        "status": "in_progress",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "details_url": details_url,
        "external_id": external_id,
        "output": {"title": title, "summary": summary},
    })


def finish_check(config, check, conclusion, details_url, title, summary):
    if not isinstance(check, dict) or not check.get("id"):
        return
    github_api(config, "PATCH", f"/repos/{repo_full_name(config)}/check-runs/{check['id']}", {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "details_url": details_url,
        "output": {"title": title, "summary": summary},
    })


def pr_data(config, pr_number):
    data = github_api(config, "GET", f"/repos/{repo_full_name(config)}/pulls/{pr_number}")
    if not isinstance(data, dict):
        raise DeployError(f"Could not load PR #{pr_number}.")
    return data


def normalize_preview_job(config, job):
    pr_number = int(job.get("pr_number") or 0)
    if pr_number <= 0:
        raise DeployError("Preview job is missing pr_number.")
    if job.get("type") == "preview_comment" or not job.get("sha"):
        pr = pr_data(config, pr_number)
        job = dict(job)
        job["sha"] = pr.get("head", {}).get("sha")
        job["head_repo"] = pr.get("head", {}).get("repo", {}).get("full_name")
        job["base_repo"] = pr.get("base", {}).get("repo", {}).get("full_name")
    if not bool(config.get("allow_preview_from_forks", False)):
        head_repo = str(job.get("head_repo") or "")
        base_repo = str(job.get("base_repo") or job.get("repository") or repo_full_name(config))
        if head_repo and base_repo and head_repo != base_repo:
            raise DeployError(f"Refusing to build preview from forked repository: {head_repo}")
    return job


def production_summary(config, sha, status, error=None):
    lines = [f"Production deploy {status} for `{sha or 'unknown'}`.", "", "Published sites:"]
    for lang, url in production_site_urls(config).items():
        lines.append(f"- {lang}: {url}")
    if error:
        lines.extend(["", f"Error: `{error}`"])
    return "\n".join(lines)


def preview_summary(pr_number, url, log_url, status, reason, error=None):
    lines = [
        f"Preview deploy {status} for PR #{pr_number}.",
        "",
        f"- Triggered by: {reason or 'unknown'}",
        f"- Preview: {url}",
        f"- Build log: {log_url}",
    ]
    if error:
        lines.extend(["", f"Error: `{error}`"])
    return "\n".join(lines)


def preview_reason(job):
    if str(job.get("type") or "") == "preview_comment":
        user = str(job.get("comment_user") or "").strip()
        return f"issue_comment /preview by @{user}" if user else "issue_comment /preview"
    event = str(job.get("event") or "").strip()
    action = str(job.get("action") or "").strip()
    return f"{event}/{action}" if event and action else event or "unknown"


def preview_comment_body(pr_number, sha, url, log_url, status, title, error=None):
    lines = [
        PREVIEW_COMMENT_MARKER,
        "### PCA Preview Deploy",
        "",
        title,
        "",
        f"- PR: #{pr_number}",
        f"- Commit: `{(sha or 'unknown')[:12]}`",
        f"- Preview: {url}",
        f"- Build log: {log_url}",
    ]
    if error:
        lines.extend(["", f"Error: `{error}`"])
    lines.append("")
    lines.append(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    return "\n".join(lines)


def upsert_preview_comment(config, pr_number, body):
    comments = github_api(config, "GET", f"/repos/{repo_full_name(config)}/issues/{pr_number}/comments?per_page=100")
    if isinstance(comments, list):
        for comment in comments:
            if isinstance(comment, dict) and PREVIEW_COMMENT_MARKER in str(comment.get("body") or "") and comment.get("id"):
                return github_api(config, "PATCH", f"/repos/{repo_full_name(config)}/issues/comments/{comment['id']}", {"body": body})
    return github_api(config, "POST", f"/repos/{repo_full_name(config)}/issues/{pr_number}/comments", {"body": body})


def safe_preview_comment(config, pr_number, sha, url, log_url, status, title, error=None, log=None):
    try:
        upsert_preview_comment(config, pr_number, preview_comment_body(pr_number, sha, url, log_url, status, title, error))
    except Exception as exc:
        message = f"Could not update PR preview comment: {exc}"
        if log:
            log.write("\n" + message + "\n")
            log.flush()
        else:
            print(message, file=sys.stderr)


def ack_preview_command(config, job, log=None):
    if str(job.get("type") or "") != "preview_comment":
        return
    comment_id = job.get("comment_id")
    if not comment_id:
        return
    try:
        github_api(config, "POST", f"/repos/{repo_full_name(config)}/issues/comments/{comment_id}/reactions", {"content": "eyes"})
        github_api(config, "DELETE", f"/repos/{repo_full_name(config)}/issues/comments/{comment_id}")
    except Exception as exc:
        if log:
            log.write(f"\nCould not acknowledge /preview command: {exc}\n")
            log.flush()


def requirements_digest(requirements: Path) -> str:
    return hashlib.sha256(requirements.read_bytes()).hexdigest()


def install_requirements(config, root: Path, log) -> None:
    requirements = root / "requirements.txt"
    if not requirements.is_file():
        return

    digest = requirements_digest(requirements)
    stamp = private_dir(config) / "requirements.sha256"
    if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == digest:
        log.write("\nPython dependencies unchanged; reusing installed environment.\n")
        log.flush()
        return

    py = python_bin(config)
    run([py, "-m", "pip", "install", "-r", str(requirements)], root, log)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    temporary = stamp.with_suffix(".tmp")
    temporary.write_text(digest + "\n", encoding="utf-8")
    temporary.replace(stamp)


def run_builder(config, root: Path, log, *args: str) -> None:
    run([python_bin(config), str(root / "tools" / "build.py"), *args], root, log)


def remove_worktree(config, target: Path, log) -> None:
    root = site_src(config)
    run(["git", "worktree", "remove", "--force", str(target)], root, log, check=False)
    shutil.rmtree(target, ignore_errors=True)


def prepare_production_worktree(config, sha: str, log) -> Path:
    if not sha:
        raise DeployError("Production job is missing the commit SHA.")

    root = site_src(config)
    target = worktree_dir(config) / "production"
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "fetch", "origin", "main"], root, log)
    if target.exists():
        remove_worktree(config, target, log)
    run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], root, log)
    run(["git", "merge-base", "--is-ancestor", sha, "origin/main"], root, log)
    run(["git", "worktree", "add", "--force", "--detach", str(target), sha], root, log)
    return target


def deploy_production(config, job: dict[str, Any]) -> None:
    sha = str(job.get("sha") or "").strip()
    short_sha = (sha or time.strftime("%Y%m%d-%H%M%S"))[:12]
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"production-{short_sha}.log"
    check = create_check(
        config,
        "PCA Production Deploy",
        sha or None,
        production_url(config),
        "Production deploy started",
        production_summary(config, sha or None, "started"),
        f"production-{short_sha}",
    )
    root: Path | None = None
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"Production deploy job: {json.dumps(job, ensure_ascii=False)}\n")
            root = prepare_production_worktree(config, sha, log)
            install_requirements(config, root, log)
            run_builder(config, root, log, "deploy", "--root", str(root), "--to", str(public_html(config)))
    except Exception as exc:
        finish_check(config, check, "failure", production_url(config), "Production deploy failed", production_summary(config, sha or None, "failed", exc))
        raise
    finally:
        if root is not None and log_path.exists():
            with log_path.open("a", encoding="utf-8") as log:
                remove_worktree(config, root, log)
    finish_check(config, check, "success", production_url(config), "Production deployed", production_summary(config, sha, "succeeded"))


def prepare_preview_worktree(config, pr_number: int, log) -> Path:
    root = site_src(config)
    target = worktree_dir(config) / f"pr-{pr_number}"
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "fetch", "origin", f"pull/{pr_number}/head"], root, log)
    if target.exists():
        remove_worktree(config, target, log)
    run(["git", "worktree", "add", "--force", "--detach", str(target), "FETCH_HEAD"], root, log)
    return target


def publish_preview_log(config, pr_number: int, source: Path) -> None:
    dest = preview_root(config) / f"pr-{pr_number}"
    dest.mkdir(parents=True, exist_ok=True)
    log_dest = dest / "_deploy.log"
    if log_dest.is_symlink() or log_dest.is_file():
        log_dest.unlink(missing_ok=True)
    elif log_dest.exists():
        shutil.rmtree(log_dest)
    shutil.copy2(source, log_dest)


def deploy_preview(config, job: dict[str, Any]) -> None:
    job = normalize_preview_job(config, job)
    pr_number = int(job["pr_number"])
    sha = str(job.get("sha") or "") or None
    short_sha = (sha or time.strftime("%Y%m%d-%H%M%S"))[:12]
    url = preview_url(config, pr_number)
    log_url = preview_log_url(config, pr_number)
    reason = preview_reason(job)
    log_dir(config).mkdir(parents=True, exist_ok=True)
    log_path = log_dir(config) / f"preview-pr-{pr_number}-{short_sha}.log"
    check = create_check(config, "PCA Preview Deploy", sha, url, "Preview deploy started", preview_summary(pr_number, url, log_url, "started", reason), f"preview-pr-{pr_number}-{short_sha}")
    try:
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"Preview deploy job: {json.dumps(job, ensure_ascii=False)}\n")
            ack_preview_command(config, job, log)
            safe_preview_comment(config, pr_number, sha, url, log_url, "started", "Preview deploy started.", log=log)
            root = prepare_preview_worktree(config, pr_number, log)
            run_sandboxed_preview(
                config,
                site_src(config),
                root,
                preview_root(config) / f"pr-{pr_number}",
                f"pr-{pr_number}",
                log,
            )
    except Exception as exc:
        if log_path.exists():
            publish_preview_log(config, pr_number, log_path)
        finish_check(config, check, "failure", log_url, "Preview deploy failed", preview_summary(pr_number, url, log_url, "failed", reason, exc))
        safe_preview_comment(config, pr_number, sha, url, log_url, "failed", "Preview deploy failed.", exc)
        raise
    publish_preview_log(config, pr_number, log_path)
    finish_check(config, check, "success", url, "Preview deployed", preview_summary(pr_number, url, log_url, "succeeded", reason))
    safe_preview_comment(config, pr_number, sha, url, log_url, "succeeded", "Preview deploy is ready.")


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


def recovered_job_path(running: Path) -> Path:
    target = running.with_suffix(".json")
    if not target.exists():
        return target
    index = 1
    while True:
        candidate = running.with_name(f"{running.stem}.recovered-{index}.json")
        if not candidate.exists():
            return candidate
        index += 1


def recover_interrupted_jobs(directory: Path) -> int:
    recovered = 0
    for running in sorted(directory.glob("*.running")):
        running.rename(recovered_job_path(running))
        recovered += 1
    return recovered


def process_queue(config, max_jobs: int) -> int:
    directory = queue_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    recovered = recover_interrupted_jobs(directory)
    if recovered:
        print(f"Recovered {recovered} interrupted deploy job(s).")

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
