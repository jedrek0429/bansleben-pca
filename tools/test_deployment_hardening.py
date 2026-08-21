#!/usr/bin/env python3
"""Focused regression tests for production hardening internals."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "build"))

import webhook_deploy_worker as worker  # noqa: E402
import publisher  # noqa: E402


def assert_transaction_rolls_back() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-publish-rollback-") as directory:
        temp = Path(directory)
        dist = temp / "dist"
        dest = temp / "public_html"
        (dist / "en").mkdir(parents=True)
        (dist / "en" / "index.html").write_text("new\n", encoding="utf-8")
        (dist / "index.html").write_text("new-root\n", encoding="utf-8")
        (dest / "en").mkdir(parents=True)
        (dest / "en" / "index.html").write_text("old\n", encoding="utf-8")
        (dest / "old-only.txt").write_text("keep-on-failure\n", encoding="utf-8")
        (dest / "preview").mkdir(parents=True)
        (dest / "preview" / "sentinel.txt").write_text("preview\n", encoding="utf-8")

        stage = publisher.stage_publish(dist, dest)
        real_move = publisher.move_path

        def fail_during_activation(source: Path, target: Path) -> None:
            if source.parent == stage and source.name == "index.html":
                raise OSError("simulated activation failure")
            real_move(source, target)

        publisher.move_path = fail_during_activation
        try:
            try:
                publisher.activate_staged_publish(stage, dest, {"preview"})
            except OSError:
                pass
            else:
                raise SystemExit("Simulated activation failure did not fail")
        finally:
            publisher.move_path = real_move

        if (dest / "en" / "index.html").read_text(encoding="utf-8") != "old\n":
            raise SystemExit("Activation failure did not restore the previous language root")
        if (dest / "old-only.txt").read_text(encoding="utf-8") != "keep-on-failure\n":
            raise SystemExit("Activation failure did not restore removed live content")
        if (dest / "preview" / "sentinel.txt").read_text(encoding="utf-8") != "preview\n":
            raise SystemExit("Activation failure modified a preserved root")


def assert_staging_failure_never_touches_live_tree() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-publish-stage-failure-") as directory:
        temp = Path(directory)
        dist = temp / "dist"
        dest = temp / "public_html"
        dist.mkdir()
        dest.mkdir()
        (dist / "index.html").write_text("new\n", encoding="utf-8")
        marker = dest / "current.txt"
        marker.write_text("current\n", encoding="utf-8")

        real_copy = publisher.copy_dist_contents

        def fail_copy(source: Path, target: Path) -> None:
            raise OSError("simulated staging copy failure")

        publisher.copy_dist_contents = fail_copy
        try:
            try:
                publisher.stage_publish(dist, dest)
            except OSError:
                pass
            else:
                raise SystemExit("Simulated staging failure did not fail")
        finally:
            publisher.copy_dist_contents = real_copy

        if marker.read_text(encoding="utf-8") != "current\n":
            raise SystemExit("Staging failure touched the live destination")


def assert_queue_recovers_interrupted_jobs() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-queue-recovery-") as directory:
        queue = Path(directory)
        (queue / "001.running").write_text('{"type":"production"}\n', encoding="utf-8")
        if worker.recover_interrupted_jobs(queue) != 1:
            raise SystemExit("Interrupted queue job was not recovered")
        if not (queue / "001.json").is_file():
            raise SystemExit("Recovered queue job was not returned to pending state")


def assert_dependencies_install_only_when_changed() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-dependency-cache-") as directory:
        temp = Path(directory)
        root = temp / "root"
        private = temp / "private"
        root.mkdir()
        requirements = root / "requirements.txt"
        requirements.write_text("Jinja2==3.1.6\n", encoding="utf-8")
        config = {"private_dir": str(private), "python": sys.executable}
        calls: list[list[str]] = []
        real_run = worker.run

        def record(command: list[str], cwd: Path, log, check: bool = True) -> None:
            calls.append(command)

        worker.run = record
        try:
            log = io.StringIO()
            worker.install_requirements(config, root, log)
            worker.install_requirements(config, root, log)
            if len(calls) != 1:
                raise SystemExit(f"Unchanged requirements installed {len(calls)} times instead of once")
            requirements.write_text("Jinja2==3.1.6\nPillow==11.3.0\n", encoding="utf-8")
            worker.install_requirements(config, root, log)
            if len(calls) != 2:
                raise SystemExit("Changed requirements did not trigger dependency installation")
            if any("--upgrade" in command for command in calls):
                raise SystemExit("Deploy worker still upgrades pip during deploy")
        finally:
            worker.run = real_run


def assert_production_uses_exact_sha_without_mutating_checkout() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-exact-sha-") as directory:
        temp = Path(directory)
        root = temp / "site-src"
        worktrees = temp / "worktrees"
        root.mkdir()
        sha = "0123456789abcdef0123456789abcdef01234567"
        config = {"site_src": str(root), "worktree_dir": str(worktrees)}
        calls: list[list[str]] = []
        real_run = worker.run

        def record(command: list[str], cwd: Path, log, check: bool = True) -> None:
            calls.append(command)

        worker.run = record
        try:
            target = worker.prepare_production_worktree(config, sha, io.StringIO())
        finally:
            worker.run = real_run

        expected_add = ["git", "worktree", "add", "--force", "--detach", str(target), sha]
        if expected_add not in calls:
            raise SystemExit("Production worktree is not pinned to the queued SHA")
        forbidden = {"checkout", "reset"}
        if any(len(command) > 1 and command[0] == "git" and command[1] in forbidden for command in calls):
            raise SystemExit("Production preparation mutates the canonical checkout")


def assert_polish_contact_runtime_is_supported() -> None:
    source = (ROOT / "contact.php").read_text(encoding="utf-8")
    required = [
        "['en', 'fr', 'hr', 'pl']",
        "case 'pl':",
        "Otrzymaliśmy Twoją wiadomość",
        "Dziękujemy za kontakt",
    ]
    missing = [item for item in required if item not in source]
    if missing:
        raise SystemExit(f"Polish contact runtime support is incomplete: {missing}")


def main() -> None:
    assert_transaction_rolls_back()
    assert_staging_failure_never_touches_live_tree()
    assert_queue_recovers_interrupted_jobs()
    assert_dependencies_install_only_when_changed()
    assert_production_uses_exact_sha_without_mutating_checkout()
    assert_polish_contact_runtime_is_supported()
    print("Deployment hardening invariants passed.")


if __name__ == "__main__":
    main()
