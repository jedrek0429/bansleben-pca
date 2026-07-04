# Poland Child Abduction static site

This repository contains the source for the multilingual Poland Child Abduction static site.

## Public sites

- English: <https://polandchildabduction.pl/>
- French: <https://enlevementparentalpologne.pl/>
- Croatian: <https://roditeljskaotmicapoljska.pl/>

## What lives where

- `content/<lang>/` — Markdown page content.
- `locales/<lang>.json` — translated labels, page titles, card text, menu labels, and shared copy.
- `config/` — page routing, cards, SEO, and image configuration.
- `templates/` — HTML shell, page templates, and partials.
- `assets/` — first-party CSS, JavaScript, images, and copied static files.
- `tools/` — validators, static-site build scripts, publish scripts, and deploy worker tooling.
- `server/` — installable server-side helpers such as the GitHub webhook endpoint.
- `docs/` — operational documentation for local work, deployment, and hosting behavior.

Generated output is written outside the repository by default:

- `../site-dist/` — temporary build output.
- `../public_html/` — production publish target on the hosting server.
- `../public_html/preview/pr-<number>/` — pull request preview output.

## Common commands

Install Python dependencies:

```sh
python -m pip install -r requirements.txt
```

Validate Python syntax:

```sh
python -m compileall -q tools/
```

Build the static site into `../site-dist/`:

```sh
python tools/build.py --root .
```

Build and publish production output:

```sh
python tools/build_and_publish.py --root . --dest ../public_html
```

Build and publish a local preview-style output:

```sh
python tools/build_and_publish.py \
  --root . \
  --dest ../public_html/preview/pr-123 \
  --url-prefix /pr-123 \
  --lang-in-url \
  --write-preview-index
```

Legacy entry points are kept for compatibility with existing workflows:

- `tools/BUILD_AND_PUBLISH.py`
- `tools/dev_build_and_publish.py`

## Documentation

Start here:

- [`docs/workspace.md`](docs/workspace.md) — repository layout, build outputs, local workflow, and safety notes.
- [`docs/deployment-webhook.md`](docs/deployment-webhook.md) — pull-based webhook deployment and PR preview setup.

## Deployment model

The current direction is pull-based deployment: GitHub sends webhook events to the hosting server, the server queues jobs, and a cron-run worker performs `git fetch`, build, publish, commit status updates, and PR preview comments.

This avoids relying on GitHub-hosted runners being able to open SSH/SCP connections to the hosting provider.
