# Poland Child Abduction static site

This repository builds and deploys the multilingual static website for Poland Child Abduction.

Public sites:

- English: <https://polandchildabduction.pl/>
- French: <https://enlevementparentalpologne.pl/>
- Croatian: <https://roditeljskaotmicapoljska.pl/>

## What this repo does

The site is generated from Markdown content, JSON configuration, HTML templates, and static assets. The build output is copied to the hosting server's `public_html` directory.

Production and pull request previews are deployed by a pull-based server worker. GitHub sends webhook events to the server, the server queues jobs, and a cron worker builds and publishes the site locally on the server.

## Important folders

| Path | Purpose |
| --- | --- |
| `content/<lang>/` | Markdown page content. |
| `locales/<lang>.json` | Translated labels, menus, cards, and shared copy. |
| `config/` | Page routing, cards, SEO, images, and site URLs. |
| `templates/` | HTML page structure and partials. |
| `assets/` | CSS, JavaScript, images, and static files copied into the site. |
| `tools/` | Build, validation, publish, and deploy scripts. |
| `server/` | Files installed on the hosting server, including the webhook endpoint. |
| `docs/` | Short setup and operations notes. |

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
python tools/validate_locales.py --root .
python tools/build.py --root .
```

The build writes to `../site-dist/`.

To test a full publish without touching production:

```sh
python tools/build_and_publish.py --root . --dest ../public_html-test
```

## Production publish command

Production deploys use:

```sh
python tools/build_and_publish.py --root . --dest ../public_html
```

This builds the site and publishes the generated language roots while preserving runtime deployment state such as `preview/`, `.private/`, and `github-webhook.php`.

## Preview publish command

Pull request previews use:

```sh
python tools/build_and_publish.py \
  --root . \
  --dest ../public_html/preview/pr-123 \
  --url-prefix /pr-123 \
  --lang-in-url \
  --write-preview-index
```

## Recreate the server workspace

Use [`docs/workspace.md`](docs/workspace.md) for the complete checklist to recreate the hosting workspace on a new server.

The short version is:

1. Clone this repo to `~/site-src` or another stable source directory.
2. Create a Python virtual environment and install `requirements.txt`.
3. Create `../public_html/preview/.private/` with deploy queues, logs, config, and the GitHub App key.
4. Copy `server/github-webhook.php` to `../public_html/preview/github-webhook.php`.
5. Configure the GitHub App webhook to call `https://preview.polandchildabduction.pl/github-webhook.php`.
6. Add a cron job that runs `tools/webhook_deploy_worker.py` from the repo checkout.
7. Run one production build and one preview build to confirm the paths are correct.

## Daily editing workflow

1. Edit Markdown in `content/<lang>/`.
2. Edit translated labels and shared copy in `locales/<lang>.json`.
3. Edit page routing, URLs, cards, SEO, or images in `config/`.
4. Run `python tools/validate_locales.py --root .`.
5. Run `python tools/build.py --root .`.
6. Open a PR and let the preview deploy verify the rendered site.

## More docs

- [`docs/workspace.md`](docs/workspace.md) — server workspace recreation and deployment checklist.
- [`docs/deployment-webhook.md`](docs/deployment-webhook.md) — webhook, GitHub App, cron worker, and preview behavior.
- [`docs/python-tools.md`](docs/python-tools.md) — short reference for scripts under `tools/`.
