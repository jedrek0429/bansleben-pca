# Webhook deployment

The site uses pull-based deployment.

GitHub sends webhook events to the hosting server. The webhook endpoint writes small JSON jobs into a private queue. A cron worker on the server reads the queue, fetches the exact requested code, runs the builder app, and reports the result back to GitHub.

## Flow

```text
GitHub App webhook
  -> https://preview.polandchildabduction.pl/github-webhook.php
  -> public_html/preview/.private/deploy-queue/*.json
  -> cron runs tools/webhook_deploy_worker.py
  -> isolated Git worktree at the queued revision
  -> python tools/build.py deploy or python tools/build.py preview
  -> staged/transactional publish
  -> GitHub check run and PR comment update
```

The webhook endpoint returns quickly. The slow work happens later in the cron worker.

## Deployment compatibility contract

Hardening must preserve the deployment behaviour visible to users and maintainers:

- a push to `main` still queues and publishes production automatically;
- PR previews still use `https://preview.polandchildabduction.pl/pr-<number>/`;
- production domains still point directly at their existing language webroots;
- the webhook, queue and GitHub check-run flow stays the same;
- `preview/`, `ochronapacjenta.pl/`, and `autoinstalator/` survive production publishes unchanged;
- a source/build/staging failure cannot modify the currently served production tree;
- an activation failure restores the previous production content;
- a production job deploys the exact commit SHA stored in that queued job;
- interrupted `.running` queue jobs are returned to the pending queue on the next worker run.

These invariants are covered by `tools/test_production_language_webroots.py`, `tools/test_production_deployment_contract.py`, `tools/test_deployment_hardening.py`, and `tools/test_preview_social_metadata.py` in the `Production webroot contract` workflow.

## What triggers deploys

| Event | Result |
| --- | --- |
| Push to `main` | Publishes production and updates a production deploy check run. |
| PR opened, synchronized, or reopened | Publishes a PR preview, updates a preview deploy check run, and comments with the preview URL. |
| PR comment `/preview` | Rebuilds the PR preview, reacts to the command comment, removes the command comment, and updates the reusable preview comment. |
| PR closed | Removes that PR preview directory. |

## Server paths

Default server layout:

```text
site-src/                                  # canonical repository checkout
site-src/.deploy-worktrees/                # temporary detached deploy worktrees
public_html/                               # production web root
public_html/preview/github-webhook.php    # webhook endpoint
public_html/preview/pr-<number>/          # PR previews
public_html/preview/.private/             # secrets, queue, logs, locks, dependency stamp
```

The private directory contains runtime state such as:

```text
pca-deploy-config.json
github-app-key.pem
deploy-queue/
deploy-logs/
requirements.sha256
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

The worker uses a lock file so overlapping cron runs cannot process the same queue concurrently. At the start of a locked run it recovers any `*.running` job left behind by an interrupted worker and makes that job pending again. Reprocessing is intentionally safe because builds and publishes are idempotent for a given revision.

## Production behavior

For a push to `main`, the webhook records the push commit SHA in the production job. The worker leaves the canonical `site-src` checkout alone and uses it only as the Git repository from which an isolated detached worktree is created:

```sh
git fetch origin main
git cat-file -e <queued-sha>^{commit}
git worktree add --force --detach .deploy-worktrees/production <queued-sha>
python -m pip install -r requirements.txt   # only when requirements.txt changed
python tools/build.py deploy --root .deploy-worktrees/production --to ../public_html
git worktree remove --force .deploy-worktrees/production
```

The queued SHA is authoritative. A later push arriving while an older job waits in the queue therefore cannot silently change which revision the older job deploys.

The worker does not upgrade pip during a deployment. It records the SHA-256 digest of the installed `requirements.txt` in `preview/.private/requirements.sha256`; unchanged dependency specifications reuse the existing server Python environment. If the requirements file changes, dependencies are installed before the builder runs and the stamp is updated only after installation succeeds.

### Transactional publishing

The builder validates and generates the complete distribution before publication. Publishing then follows this sequence on the same filesystem:

```text
validated dist
  -> copy complete dist into a temporary staging directory
  -> move current replaceable production items into a temporary backup
  -> move staged items into public_html
  -> on any activation error: remove partial new items and restore the backup
  -> remove temporary stage/backup directories
```

Nothing in `public_html` is removed while the staging copy is being prepared. Preserved roots are never moved during activation:

- `preview/`
- `ochronapacjenta.pl/`
- `autoinstalator/`

This deliberately keeps the existing webroot and hosting model. It does not introduce release symlinks, change domain document roots, or replace the webhook deployment architecture.

The worker creates a GitHub check run for the production deploy and marks it success or failure when the job finishes.

## Preview behavior

For a PR preview, the worker creates a detached worktree and publishes to:

```text
public_html/preview/pr-<number>/
```

The preview build command remains:

```sh
python tools/build.py preview \
  --root .deploy-worktrees/pr-<number> \
  --to ../public_html/preview/pr-<number> \
  --prefix pr-<number>
```

Successful previews are available at:

```text
https://preview.polandchildabduction.pl/pr-<number>/
```

The public deploy log is available at:

```text
https://preview.polandchildabduction.pl/pr-<number>/_deploy.log
```

The worker creates a GitHub check run for the preview deploy and updates a reusable PR comment with the preview URL and deploy log link.

## Contact runtime

Every generated production language root contains the same contact handler. The handler accepts all configured production languages currently shipped by PCA (`en`, `fr`, `hr`, and `pl`) and sends the automatic confirmation in the submitted language. Unknown language codes fall back to English.

SMTP configuration remains private and is copied into the generated language webroots by the existing build/publish flow.

## Recreate everything on a new server

Use [`docs/workspace.md`](workspace.md). It is the canonical checklist for rebuilding the workspace from scratch.
