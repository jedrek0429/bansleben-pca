# Webhook deployment

The site uses pull-based deployment.

GitHub sends webhook events to the hosting server. The webhook endpoint writes small JSON jobs into a private queue. A cron worker on the server reads the queue, fetches the right code, builds the static site, publishes it, and reports status back to GitHub.

## Flow

```text
GitHub App webhook
  -> https://preview.polandchildabduction.pl/github-webhook.php
  -> public_html/preview/.private/deploy-queue/*.json
  -> cron runs tools/webhook_deploy_worker.py
  -> git fetch + build + publish
  -> GitHub check run + PR preview comment
```

The webhook endpoint returns quickly. The slow work happens later in the cron worker.

## What triggers deploys

| Event | Result |
| --- | --- |
| Push to `main` | Publishes production. |
| PR opened, synchronized, or reopened | Publishes a PR preview. |
| PR comment `/preview` | Rebuilds the PR preview. |
| PR closed | Removes that PR preview directory. |

## Server paths

Default server layout:

```text
site-src/                                  # repository checkout
public_html/                              # production web root
public_html/preview/github-webhook.php    # webhook endpoint
public_html/preview/pr-<number>/          # PR previews
public_html/preview/.private/             # secrets, queue, logs, locks
```

The private directory contains:

```text
pca-deploy-config.json
github-app-key.pem
deploy-queue/
deploy-logs/
```

Do not commit anything from `.private`.

## GitHub App setup

Install the GitHub App only on `jedrek0429/bansleben-pca`.

Required repository permissions:

- Checks: read and write
- Issues: read and write
- Pull requests: read-only
- Contents: read-only
- Metadata: read-only

Required webhook events:

- Push
- Pull request
- Issue comment

Webhook URL:

```text
https://preview.polandchildabduction.pl/github-webhook.php
```

The webhook secret must match `webhook_secret` in `public_html/preview/.private/pca-deploy-config.json`.

## Private config

Start from:

```sh
cp server/pca-deploy-config.example.json ../public_html/preview/.private/pca-deploy-config.json
```

Then set the real values:

- `webhook_secret`
- `github_app_id`
- `github_app_installation_id`
- `github_app_private_key_path`
- `site_src`
- `public_html`
- `python`
- `production_base_url`
- `preview_base_url`
- `preview_root`
- `private_dir`
- `queue_dir`
- `log_dir`

Keep `allow_preview_from_forks` set to `false` unless the server can safely build untrusted code.

## Cron worker

Example:

```cron
* * * * * cd /home/platne/serwer88382/site-src && tools/.venv/bin/python tools/webhook_deploy_worker.py >> /home/platne/serwer88382/public_html/preview/.private/deploy-worker.log 2>&1
```

The worker uses a lock file so overlapping cron runs should not process the same queue twice.

## Production behavior

For a push to `main`, the worker runs the production build and publish flow:

```sh
git fetch origin main
git checkout main
git reset --hard origin/main
python -m pip install -r requirements.txt
python tools/build_and_publish.py --root . --dest ../public_html
```

Production publishes preserve root runtime state, including:

- `preview/`
- `.private/`
- `github-webhook.php`

## Preview behavior

For a PR preview, the worker creates a detached worktree and publishes to:

```text
public_html/preview/pr-<number>/
```

The preview build command is:

```sh
python tools/build_and_publish.py \
  --root .deploy-worktrees/pr-<number> \
  --dest ../public_html/preview/pr-<number> \
  --url-prefix /pr-<number> \
  --lang-in-url \
  --write-preview-index
```

Successful previews are available at:

```text
https://preview.polandchildabduction.pl/pr-<number>/
```

The public deploy log is available at:

```text
https://preview.polandchildabduction.pl/pr-<number>/_deploy.log
```

## GitHub feedback

The worker updates GitHub with:

- `PCA Production Deploy` check runs
- `PCA Preview Deploy` check runs
- one reusable PR preview comment marked with `<!-- pca-preview-deploy-comment -->`

The comment is updated instead of creating a new comment on every push.

## Recreate everything on a new server

Use [`docs/workspace.md`](workspace.md). It is the canonical checklist for rebuilding the workspace from scratch.
