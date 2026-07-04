# Python tools reference

This repository uses small Python scripts instead of a large framework. Most commands should be run from the repository root and accept `--root .` when they need the site source directory.

## Main build and publish tools

| Tool | Purpose | Typical command |
| --- | --- | --- |
| `tools/build_and_publish.py` | Canonical pipeline wrapper. Runs validation, hyperlink formatting, static build, and publish. Use this for new automation. | `python tools/build_and_publish.py --root . --dest ../public_html` |
| `tools/build.py` | Builds the static site into `../site-dist/` from `content/`, `locales/`, `config/`, `templates/`, and `assets/`. | `python tools/build.py --root .` |
| `tools/publish.py` | Publishes an existing `../site-dist/` tree to a destination directory, deleting stale generated files while preserving configured runtime folders. | `python tools/publish.py --dist ../site-dist --dest ../public_html` |
| `tools/BUILD_AND_PUBLISH.py` | Backward-compatible production entry point. Prefer `build_and_publish.py` for new scripts. | `python tools/BUILD_AND_PUBLISH.py --root .` |
| `tools/dev_build_and_publish.py` | Backward-compatible preview/development entry point. Prefer `build_and_publish.py` for new scripts. | `python tools/dev_build_and_publish.py --root . --url-prefix /pr-123 --dest ../public_html/preview/pr-123 --write-preview-index` |

## Content and locale tools

| Tool | Purpose | Typical command |
| --- | --- | --- |
| `tools/validate_locales.py` | Validates `locales/*.json` against `config/pages.json` and `locales/en.json`. It checks enabled pages, required fields, slug/title consistency, parent coverage, and card item structure. | `python tools/validate_locales.py --root .` |
| `tools/autofix_locales.py` | Repairs fixable locale drift, such as missing page entries, enabled flags, slugs, titles, and card image metadata. It writes `.bak` backups before modifying locale files. | `python tools/autofix_locales.py --root .` |
| `tools/format_hyperlinks.py` | Normalizes bare URLs and email addresses in Markdown content while preserving code blocks, existing Markdown links, images, and HTML. | `python tools/format_hyperlinks.py --root .` |

Use `autofix_locales.py` carefully: review the diff after running it because it edits JSON files in place.

## Markdown, image, and rendering helpers

| Tool | Purpose | Notes |
| --- | --- | --- |
| `tools/renderer.py` | Converts Markdown to HTML with Python-Markdown and PyMdown extensions. Used by `build.py`. | Not usually run directly. |
| `tools/resolve_images.py` | Helper for rewriting relative Markdown/HTML image paths against a base path. | Library-style helper; currently not part of the main build path. |
| `tools/common.py` | Shared console formatting, JSON loading, path display, and report helpers used by the other tools. | Library-style helper. |

## Preview and screenshot helpers

| Tool | Purpose | Typical command |
| --- | --- | --- |
| `tools/pages_preview_finalize.py` | Finalizes a PR preview directory served under a URL prefix. It exposes root assets, rewrites root-relative asset URLs, adds `noindex`, and writes a preview root redirect. | `python tools/pages_preview_finalize.py --preview-dir pages-preview/pr-123 --url-prefix /pr-123` |
| `tools/pages_preview_root_assets.py` | Copies shared assets from a language directory to a preview root for local/GitHub Pages screenshot runs. | `python tools/pages_preview_root_assets.py --preview-dir ../site-dist` |
| `tools/publish_screenshots_branch.py` | Publishes generated `desktop.png` and `mobile.png` screenshots to the persistent `site-screenshots` branch so PR comments can embed stable image URLs. | `python tools/publish_screenshots_branch.py --pr-number 123` |

## Server and deployment helpers

| Tool | Purpose | Typical command |
| --- | --- | --- |
| `tools/webhook_deploy_worker.py` | Processes queued webhook deployment jobs on the hosting server. It runs production deploys, PR preview deploys, preview cleanup, commit status updates, and PR comments. | `python tools/webhook_deploy_worker.py` |
| `tools/dev_publish_editor.py` | Publishes the editor directory to a destination directory after verifying required editor files exist. This is separate from the static site pipeline. | `python tools/dev_publish_editor.py --dest ../public_html/en/editor` |

The webhook worker expects private server config in `../public_html/.private/pca-deploy-config.json` by default. See `docs/deployment-webhook.md` for setup details.

## Recommended command sequences

### Local build check

```sh
python -m pip install -r requirements.txt
python -m compileall -q tools/
python tools/validate_locales.py --root .
python tools/build.py --root .
```

### Full production-style publish to a disposable directory

```sh
python tools/build_and_publish.py --root . --dest ../public_html-test
```

### Preview-style publish to a disposable PR directory

```sh
python tools/build_and_publish.py \
  --root . \
  --dest ../public_html/preview/pr-123 \
  --url-prefix /pr-123 \
  --lang-in-url \
  --write-preview-index
```

## Adding a new tool

When adding a new Python script under `tools/`:

1. Prefer `argparse` with clear `--root`, `--dest`, or explicit path arguments.
2. Keep generated output outside the repository unless there is a good reason to commit it.
3. Reuse helpers from `tools/common.py` for readable output and JSON loading.
4. Make destructive operations explicit and document what paths they can delete or overwrite.
5. Add the tool to this document if it is meant to be run by humans or automation.
