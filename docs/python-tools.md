# Builder app

Run commands from the repository root. On the server, use the project virtual environment when available, for example `tools/.venv/bin/python`.

The canonical entrypoint is:

```sh
python tools/build.py <command>
```

## Main commands

| Task | Command |
| --- | --- |
| Install dependencies | `python -m pip install -r requirements.txt` |
| Check Python syntax | `python -m compileall -q tools/` |
| Validate translations/config | `python tools/build.py check --root .` |
| Build local site output | `python tools/build.py site --root .` |
| Build local site without writing output | `python tools/build.py site --root . --dry` |
| Show resolved config | `python tools/build.py inspect --root .` |
| Remove generated output | `python tools/build.py clean --root .` |
| Run deploy worker | `python tools/webhook_deploy_worker.py` |

## Deployment commands

Production:

```sh
python tools/build.py deploy \
  --root . \
  --to ../public_html
```

Preview:

```sh
python tools/build.py preview \
  --root . \
  --to ../public_html/preview/pr-123 \
  --prefix pr-123
```

`preview` owns preview-specific URL rewriting. It does not expose production-only options. Content images resolve to `/pr-123/assets/...` in preview output.

## Utilities

Utilities live under `utils` because they maintain content or assets rather than define deployment modes.

| Task | Command |
| --- | --- |
| Autofix locale drift | `python tools/build.py utils fix-locales --root .` |
| Normalize Markdown hyperlinks | `python tools/build.py utils format-links --root .` |
| Check hyperlink formatting without writing | `python tools/build.py utils format-links --root . --check` |
| Run hyperlink formatter self-test | `python tools/build.py utils format-links --self-test` |
| Convert images below a directory to WebP | `python tools/build.py utils convert-images assets` |

`utils fix-locales` creates `.bak` backups before writing locale JSON files. It restores missing enabled page entries, titles, slugs, parent references, card entries, and card image sources from `config/pages.json` and `locales/en.json`.

## Builder implementation

| Path | Purpose |
| --- | --- |
| `tools/build.py` | Small app launcher. |
| `tools/build/runner.py` | Command-line parser and command dispatch. |
| `tools/build/builder.py` | Site build orchestration. |
| `tools/build/workflow.py` | Preview and production workflows. |
| `tools/build/publisher.py` | Safe publish/copy checks. |
| `tools/build/validation.py` | Locale and config validation. |
| `tools/build/autofix.py` | Locale autofix utility. |
| `tools/build/hyperlinks.py` | Markdown hyperlink normalization utility. |
| `tools/build/images.py` | Markdown and HTML content image URL resolution. |

## Recommended checks before opening a PR

```sh
python -m compileall -q tools/
python tools/build.py check --root .
python tools/build.py site --root . --dry
python tools/build.py site --root .
```

For server setup and deploy behavior, start with [`docs/workspace.md`](workspace.md).
