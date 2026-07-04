# PCA webhook deployment

This document describes the pull-based deployment flow used to avoid SSH/SCP timeouts from GitHub-hosted runners to LH.pl.

## Architecture

```text
GitHub webhook
  -> public_html/github-webhook.php
  -> public_html/.private/deploy-queue/*.json
  -> cron runs tools/deploy_worker.py
  -> git fetch + local build + local publish
  -> GitHub commit status + PR comment
```

The webhook endpoint only validates the GitHub signature and queues a job. It returns quickly, so GitHub does not wait for the full build.

The worker performs the slow work from the server itself:

- `push` to `main` publishes production.
- `pull_request` `opened`, `synchronize`, and `reopened` publish preview automatically.
- `issue_comment` containing `/preview` forces a preview rebuild.
- `pull_request` `closed` removes the preview directory.

## One-time server setup

Copy the webhook endpoint into the public web root:

```bash
cd ~/site-src
cp server/github-webhook.php ../public_html/github-webhook.php
```

Create the private config file:

```bash
mkdir -p ../public_html/.private/deploy-queue ../public_html/.private/deploy-logs
cp server/pca-deploy-config.example.json ../public_html/.private/pca-deploy-config.json
chmod 600 ../public_html/.private/pca-deploy-config.json
```

Edit `../public_html/.private/pca-deploy-config.json` and set:

- `webhook_secret` to the same secret configured in GitHub webhook settings.
- `github_token` to a token that can write commit statuses and PR comments for this repository.
- paths if LH.pl uses different absolute paths.

Keep `allow_preview_from_forks` as `false` unless the server is isolated enough to build untrusted PR code.

## GitHub webhook settings

Add a repository webhook pointing to:

```text
https://polandchildabduction.pl/github-webhook.php
```

Use content type `application/json` and configure the same secret as `webhook_secret`.

Recommended events:

- `Pushes`
- `Pull requests`
- `Issue comments`

## Cron worker

Run the worker from cron, for example once per minute:

```cron
* * * * * cd /home/platne/serwer88382/site-src && tools/.venv/bin/python tools/deploy_worker.py >> /home/platne/serwer88382/public_html/.private/deploy-worker.log 2>&1
```

The worker uses a lock file, so overlapping cron runs should not process the same queue concurrently.

## Production behavior

For a push to `main`, the worker runs:

```bash
git fetch origin main
git checkout main
git reset --hard origin/main
python -m pip install -r requirements.txt
python tools/build_and_publish.py --root . --dest ../public_html
```

`tools/publish.py` preserves root-level deployment state by default:

- `preview/`
- `.private/`
- `github-webhook.php`

## Preview behavior

For PR preview jobs, the worker creates a detached Git worktree under `.deploy-worktrees/pr-<number>` and builds into:

```text
public_html/preview/pr-<number>/
```

The build command is:

```bash
python tools/build_and_publish.py \
  --root .deploy-worktrees/pr-<number> \
  --dest ../public_html/preview/pr-<number> \
  --url-prefix /pr-<number> \
  --lang-in-url \
  --write-preview-index
```

The worker publishes the build log next to the preview:

```text
https://preview.polandchildabduction.pl/pr-<number>/_deploy.log
```

## GitHub feedback

The worker sets commit statuses:

- `pca/production`
- `pca/preview`

For successful preview deploys, the status target URL points to the ready preview:

```text
https://preview.polandchildabduction.pl/pr-<number>/
```

The worker also upserts one PR comment containing both the preview URL and the build log URL.

## Manual test

After installing the config, a dry manual queue test can be done by creating a small job file:

```bash
cat > ../public_html/.private/deploy-queue/manual-preview.json <<'JSON'
{
  "type": "preview_comment",
  "repository": "jedrek0429/bansleben-pca",
  "pr_number": 9
}
JSON

tools/.venv/bin/python tools/deploy_worker.py
```

Use a current open PR number for the test.
