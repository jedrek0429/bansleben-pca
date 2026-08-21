#!/usr/bin/env python3
"""Focused regression tests for production hardening internals."""

from __future__ import annotations

import io
import json
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
        temp = Path(directory); dist = temp / "dist"; dest = temp / "public_html"
        (dist / "en").mkdir(parents=True); (dist / "en" / "index.html").write_text("new\n", encoding="utf-8"); (dist / "index.html").write_text("new-root\n", encoding="utf-8")
        (dest / "en").mkdir(parents=True); (dest / "en" / "index.html").write_text("old\n", encoding="utf-8"); (dest / "old-only.txt").write_text("keep-on-failure\n", encoding="utf-8")
        (dest / "preview").mkdir(parents=True); (dest / "preview" / "sentinel.txt").write_text("preview\n", encoding="utf-8")
        stage = publisher.stage_publish(dist, dest); real_move = publisher.move_path
        def fail_during_activation(source: Path, target: Path) -> None:
            if source.parent == stage and source.name == "index.html": raise OSError("simulated activation failure")
            real_move(source, target)
        publisher.move_path = fail_during_activation
        try:
            try: publisher.activate_staged_publish(stage, dest, {"preview"})
            except OSError: pass
            else: raise SystemExit("Simulated activation failure did not fail")
        finally: publisher.move_path = real_move
        if (dest / "en" / "index.html").read_text(encoding="utf-8") != "old\n": raise SystemExit("Activation failure did not restore the previous language root")
        if (dest / "old-only.txt").read_text(encoding="utf-8") != "keep-on-failure\n": raise SystemExit("Activation failure did not restore removed live content")
        if (dest / "preview" / "sentinel.txt").read_text(encoding="utf-8") != "preview\n": raise SystemExit("Activation failure modified a preserved root")


def assert_staging_failure_never_touches_live_tree() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-publish-stage-failure-") as directory:
        temp = Path(directory); dist = temp / "dist"; dest = temp / "public_html"; dist.mkdir(); dest.mkdir()
        (dist / "index.html").write_text("new\n", encoding="utf-8"); marker = dest / "current.txt"; marker.write_text("current\n", encoding="utf-8")
        real_copy = publisher.copy_dist_contents
        def fail_copy(source: Path, target: Path) -> None: raise OSError("simulated staging copy failure")
        publisher.copy_dist_contents = fail_copy
        try:
            try: publisher.stage_publish(dist, dest)
            except OSError: pass
            else: raise SystemExit("Simulated staging failure did not fail")
        finally: publisher.copy_dist_contents = real_copy
        if marker.read_text(encoding="utf-8") != "current\n": raise SystemExit("Staging failure touched the live destination")


def assert_queue_recovers_interrupted_jobs() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-queue-recovery-") as directory:
        queue = Path(directory); (queue / "001.running").write_text('{"type":"production"}\n', encoding="utf-8")
        if worker.recover_interrupted_jobs(queue) != 1 or not (queue / "001.json").is_file(): raise SystemExit("Interrupted queue job was not recovered")


def assert_dependencies_install_only_when_changed() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-dependency-cache-") as directory:
        temp = Path(directory); root = temp / "root"; private = temp / "private"; root.mkdir(); requirements = root / "requirements.txt"; requirements.write_text("Jinja2==3.1.6\n", encoding="utf-8")
        config = {"private_dir": str(private), "python": sys.executable}; calls = []; real_run = worker.run
        def record(command, cwd, log, check=True): calls.append(command)
        worker.run = record
        try:
            log = io.StringIO(); worker.install_requirements(config, root, log); worker.install_requirements(config, root, log)
            if len(calls) != 1: raise SystemExit("Unchanged requirements installed more than once")
            requirements.write_text("Jinja2==3.1.6\nPillow==11.3.0\n", encoding="utf-8"); worker.install_requirements(config, root, log)
            if len(calls) != 2 or any("--upgrade" in command for command in calls): raise SystemExit("Dependency cache contract failed")
        finally: worker.run = real_run


def assert_production_uses_exact_sha_without_mutating_checkout() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-exact-sha-") as directory:
        temp = Path(directory); root = temp / "site-src"; worktrees = temp / "worktrees"; root.mkdir(); sha = "0123456789abcdef0123456789abcdef01234567"; config = {"site_src": str(root), "worktree_dir": str(worktrees)}; calls = []; real_run = worker.run
        def record(command, cwd, log, check=True): calls.append(command)
        worker.run = record
        try: target = worker.prepare_production_worktree(config, sha, io.StringIO())
        finally: worker.run = real_run
        if ["git", "merge-base", "--is-ancestor", sha, "origin/main"] not in calls: raise SystemExit("Production preparation does not verify the queued SHA belongs to origin/main")
        if ["git", "worktree", "add", "--force", "--detach", str(target), sha] not in calls: raise SystemExit("Production worktree is not pinned to the queued SHA")
        if any(len(c) > 1 and c[0] == "git" and c[1] in {"checkout", "reset"} for c in calls): raise SystemExit("Production preparation mutates the canonical checkout")


def assert_production_rejects_sha_outside_main() -> None:
    with tempfile.TemporaryDirectory(prefix="pca-off-main-sha-") as directory:
        temp = Path(directory); root = temp / "site-src"; worktrees = temp / "worktrees"; root.mkdir(); sha = "fedcba9876543210fedcba9876543210fedcba98"; config = {"site_src": str(root), "worktree_dir": str(worktrees)}; calls = []; real_run = worker.run
        def reject_ancestry(command, cwd, log, check=True):
            calls.append(command)
            if command[:3] == ["git", "merge-base", "--is-ancestor"]: raise worker.DeployError("queued SHA is not contained in origin/main")
        worker.run = reject_ancestry
        try:
            try: worker.prepare_production_worktree(config, sha, io.StringIO())
            except worker.DeployError: pass
            else: raise SystemExit("Off-main production SHA was accepted")
        finally: worker.run = real_run
        if any(c[:3] == ["git", "worktree", "add"] for c in calls): raise SystemExit("Production worktree was created after the ancestry check failed")


def assert_contact_runtime_is_localized_data() -> None:
    php = (ROOT / "contact.php").read_text(encoding="utf-8")
    if "pca-contact-locale.json" not in php or "confirmation_subject(string $lang)" in php or "case 'pl':" in php:
        raise SystemExit("Contact handler still owns language-specific confirmation copy")
    for lang in ("en", "fr", "hr", "pl"):
        source = ROOT / "locales" / "contact" / f"{lang}.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        if not str(data.get("confirmation_subject", "")).strip() or "{name}" not in str(data.get("confirmation_body", "")):
            raise SystemExit(f"Contact runtime locale is incomplete: {lang}")
    pl = json.loads((ROOT / "locales" / "contact" / "pl.json").read_text(encoding="utf-8"))
    if "Otrzymaliśmy Twoją wiadomość" not in pl["confirmation_subject"] or "Dziękujemy za kontakt" not in pl["confirmation_body"]:
        raise SystemExit("Polish contact runtime copy is incomplete")


def main() -> None:
    assert_transaction_rolls_back(); assert_staging_failure_never_touches_live_tree(); assert_queue_recovers_interrupted_jobs(); assert_dependencies_install_only_when_changed(); assert_production_uses_exact_sha_without_mutating_checkout(); assert_production_rejects_sha_outside_main(); assert_contact_runtime_is_localized_data()
    print("Deployment hardening invariants passed.")


if __name__ == "__main__": main()
