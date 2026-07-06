# Poland Child Abduction static site

This repository builds and deploys the multilingual static website for Poland Child Abduction.

Public sites:

- English: <https://polandchildabduction.pl/>
- French: <https://enlevementparentalpologne.pl/>
- Croatian: <https://roditeljskaotmicapolskapolska.pl/>

## What this repo does

The site is generated from Markdown content, JSON configuration, HTML templates, and static assets. The builder app lives behind `tools/build.py` and owns local builds, previews, production deploys, checks, and maintenance utilities.

Production and pull request previews are deployed by a pull-based server worker. GitHub sends webhook events to the server, the server queues jobs, and a cron worker builds and publishes the site locally on the server.

## Important folders

| Path | Purpose |
| --- | --- |
| `content/<lang>/` | Markdown page content. |
| `locales/<lang>.json` | Translated labels, menus, cards, and shared copy. |
| `config/` | Page routing, cards, SEO, images, and site URLs. |
| `templates/` | HTML page structure and partials. |
| `assets/` | CSS, JavaScript, images, and static files copied into the site. |
| `tools/build.py` | Builder app entrypoint. |
| `tools/build/` | Builder app implementation. |
| `server/` | Files installed on the hosting server, including the webhook endpoint. |
| `docs/` | Setup and operations notes. |

Generated output is not edited by hand:

| Path | Purpose |
| --- | --- |
| `../site-dist/` | Temporary build output. Safe to delete. |
| `../public_html/` | Production web root on the server. |
| `../public_html/preview/pr-<number>/` | Pull request preview output. |
| `../public_html/preview/.private/` | Private deploy config, queues, logs, locks, and app key. |

## Local setup

From the repository root:

```sh
python -m pip install -r requirements.txt
python -m compileall -q tools/
python tools/build.py check --root .
python tools/build.py site --root .
```

The build writes to `../site-dist/`.

To inspect what the builder will use:

```sh
python tools/build.py inspect --root .
```

To run a local build without writing output:

```sh
python tools/build.py site --root . --dry
```

## Builder app commands

| Task | Command |
| --- | --- |
| Build local site output | `python tools/build.py site --root .` |
| Validate locale/config consistency | `python tools/build.py check --root .` |
| Validate without interactive autofix prompt | `python tools/build.py check --root . --no-autofix-prompt` |
| Autofix locale drift | `python tools/build.py utils autofix-locales --root .` |
| Normalize Markdown links | `python tools/build.py utils format-links --root .` |
| Check Markdown link formatting without writing | `python tools/build.py utils format-links --root . --check` |
| Convert images below a directory to WebP | `python tools/build.py utils convert-images assets` |
| Remove generated output | `python tools/build.py clean --root .` |
| Show resolved config | `python tools/build.py inspect --root .` |

When `check` fails in an interactive terminal, it asks whether to run `utils autofix-locales`.

## Production deploy command

Production deploys should use:

```sh
python tools/build.py deploy \
  --root . \
  --to ../public_html
```

This checks content/config, normalizes Markdown hyperlinks, builds the site, publishes the generated language roots, and preserves runtime deployment state such as `preview/`, `.private/`, and `github-webhook.php`.

## Preview deploy command

Pull request previews should use:

```sh
python tools/build.py preview \
  --root . \
  --to ../public_html/preview/pr-123 \
  --prefix pr-123
```

Preview mode builds pages under the preview prefix and writes a redirect index at the preview destination. Content image URLs resolve to the shared preview asset root, for example `/pr-123/assets/...`.

## Recreate the server workspace

Use [`docs/workspace.md`](docs/workspace.md) for the complete checklist to recreate the hosting workspace on a new server.

The short version is:

1. Clone this repo to `~/site-src` or another stable source directory.
2. Create a Python virtual environment and install `requirements.txt`.
3. Create `../public_html/preview/.private/` with deploy queues, logs, config, and the GitHub App key.
4. Copy `server/github-webhook.php` to `../public_html/preview/github-webhook.php`.
5. Configure the GitHub App webhook to call `https://preview.polandchildabduction.pl/github-webhook.php`.
6. Add a cron job that runs `tools/webhook_deploy_worker.py` from the repo checkout.
7. Run one production deploy and one preview deploy to confirm the paths are correct.

## Daily editing workflow

1. Edit Markdown in `content/<lang>/`.
2. Edit translated labels and shared copy in `locales/<lang>.json`.
3. Edit page routing, URLs, cards, SEO, or images in `config/`.
4. Run `python tools/build.py check --root .`.
5. Run `python tools/build.py site --root .`.
6. Open a PR and let the preview deploy verify the rendered site.

## More docs

- [`docs/workspace.md`](docs/workspace.md) — server workspace recreation and deployment checklist.
- [`docs/deployment-webhook.md`](docs/deployment-webhook.md) — webhook, GitHub App, cron worker, and preview behavior.
- [`docs/python-tools.md`](docs/python-tools.md) — builder command reference.
