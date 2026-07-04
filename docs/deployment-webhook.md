# PCA webhook deployment

This document describes the pull-based deployment flow used to avoid SSH/SCP timeouts from GitHub-hosted runners to LH.pl.

## Architecture

```text
GitHub webhook
  -> public_html/github-webhook.php
  -> public_html/.private/deploy-queue/*.json
  -> cron runs tools/webhook_deploy_worker.py
  -> git fetch + local build + local publish
  -> GitHub App check run + bot PR comment
```

The webhook endpoint only validates the GitHub signature and queues a job. It returns quickly, so GitHub does not wait for the full build.

The worker performs the slow work from the server itself:

- `push` to `main` publishes production.
- `pull_request` `opened`, `synchronize`, and `reopened` publish preview automatically.
- `issue_comment` containing `/preview` forces a preview rebuild.
- `pull_request` `closed` removes the preview directory.

## GitHub App setup

Create a GitHub App for the repository and install it only on `jedrek0429/bansleben-pca`.

Suggested app name:

```text
PCA Deploy Bot
```

Repository permissions:

- `Checks`: read and write
- `Issues`: read and write
- `Pull requests`: read-only
- `Contents`: read-only
- `Metadata`: read-only

`Issues` write access is needed because pull request comments are created through the issue comments API. Comments will be authored by the GitHub App bot instead of a personal user account.

Generate a private key for the app and save it on the server, for example:

```text
/home/platne/serwer88382/public_html/.private/pca-deploy-bot.private-key.pem
```

Do not commit the private key to the repository.

Record these values for `pca-deploy-config.json`:

- GitHub App ID
- Installation ID for the repository installation
- private key path on the server

## One-time server setup

Copy the webhook endpoint into the public web root:

```bash
cd ~/site-src
cp server/github-webhook.php ../public_html/github-webhook.php
```

Create the private config file and private directories:

```bash
mkdir -p ../public_html/.private/deploy-queue ../public_html/.private/deploy-logs
cp server/pca-deploy-config.example.json ../public_html/.private/pca-deploy-config.json
chmod 600 ../public_html/.private/pca-deploy-config.json
chmod 600 ../public_html/.private/pca-deploy-bot.private-key.pem
```

Edit `../public_html/.private/pca-deploy-config.json` and set:

- `webhook_secret` to the same secret configured in GitHub webhook settings.
- `github_app_id` to the GitHub App ID.
- `github_app_installation_id` to the repository installation ID.
- `github_app_private_key_path` to the private key path on the server.
- paths if LH.pl uses different absolute paths.

Keep `allow_preview_from_forks` as `false` unless the server is isolated enough to build untrusted PR code.

The worker signs a short-lived GitHub App JWT with `openssl`, exchanges it for an installation access token, and uses that token to create/update Checks API check runs and PR comments.

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
* * * * * cd /home/platne/serwer88382/site-src && tools/.venv/bin/python tools/webhook_deploy_worker.py >> /home/platne/serwer88382/public_html/.private/deploy-worker.log 2>&1
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

The worker creates GitHub App check runs:

- `PCA Production Deploy`
- `PCA Preview Deploy`

For successful preview deploys, the check details URL points to the ready preview:

```text
https://preview.polandchildabduction.pl/pr-<number>/
```

If preview deployment fails, the check details URL points to the public `_deploy.log` file instead.

The worker also upserts one PR comment with the marker `<!-- pca-webhook-preview -->`. That comment contains both the preview URL and the build log URL, and is authored by the GitHub App bot.

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

tools/.venv/bin/python tools/webhook_deploy_worker.py
```

Use a current open PR number for the test.
