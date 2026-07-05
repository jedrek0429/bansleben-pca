# Python tools

Run commands from the repository root. Use `tools/.venv/bin/python` on the server if the virtual environment is installed there.

## Commands most people need

| Task | Command |
| --- | --- |
| Install dependencies | `python -m pip install -r requirements.txt` |
| Check Python syntax | `python -m compileall -q tools/` |
| Validate translations | `python tools/validate_locales.py --root .` |
| Build site | `python tools/build.py --root .` |
| Production publish | `python tools/build_and_publish.py --root . --dest ../public_html` |
| Preview publish | `python tools/build_and_publish.py --root . --dest ../public_html/preview/pr-123 --url-prefix /pr-123 --lang-in-url --write-preview-index` |
| Run deploy worker | `python tools/webhook_deploy_worker.py` |

## Main scripts

| Script | Purpose |
| --- | --- |
| `tools/build_and_publish.py` | Canonical build and publish wrapper. Use this for production, previews, and automation. |
| `tools/build.py` | Builds the static site into `../site-dist/`. |
| `tools/publish.py` | Publishes an existing `../site-dist/` tree to a destination and removes stale generated files. |
| `tools/validate_locales.py` | Checks locale files against the English locale and page config. |
| `tools/autofix_locales.py` | Repairs fixable locale drift and writes `.bak` backups. |
| `tools/format_hyperlinks.py` | Normalizes bare URLs and email addresses in Markdown content. |
| `tools/webhook_deploy_worker.py` | Processes queued production and preview deploy jobs on the server. |
| `tools/publish_screenshots_branch.py` | Publishes generated screenshots for PR review comments. |

## Library/helper files

These are used by the scripts above and are not usually run directly:

- `tools/common.py`
- `tools/renderer.py`
- `tools/resolve_images.py`

## Recommended checks before opening a PR

```sh
python -m compileall -q tools/
python tools/validate_locales.py --root .
python tools/build.py --root .
```

For server setup and deploy behavior, start with [`docs/workspace.md`](workspace.md).
