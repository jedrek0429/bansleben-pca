# PCA webhook deployment

This document describes the pull-based deployment flow used to avoid SSH/SCP timeouts from GitHub-hosted runners to LH.pl.

## Architecture

```text
GitHub App webhook
  -> preview.polandchildabduction.pl/github-webhook.php
  -> public_html/preview/.private/deploy-queue/*.json
  -> cron runs tools/webhook_deploy_worker.py
  -> git fetch + local build + local publish
  -> GitHub App check run + PR preview comment
```

The webhook endpoint only validates the GitHub signature and queues a job. It returns quickly, so GitHub does not wait for the full build.

The endpoint and private deployment state live under `public_html/preview/`, because that directory is preserved by production publishes and is the document root for `https://preview.polandchildabduction.pl`.

The worker performs the slow work from the server itself:

- `push` to `main` publishes production.
- `pull_request` `opened`, `synchronize`, and `reopened` publish preview automatically.
- `issue_comment` containing `/preview` forces a preview rebuild.
- `pull_request` `closed` removes the preview directory for that PR.

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

`Issues` write access is required because GitHub PR conversation comments are created through the Issues Comments API.

Configure the GitHub App webhook:

```text
Webhook URL: https://preview.polandchildabduction.pl/github-webhook.php
Webhook secret: same value as webhook_secret in pca-deploy-config.json
```

Subscribe the app webhook to these events:

- `Push`
- `Pull request`
- `Issue comment`

Generate an app key and save it on the server under the preview private directory, for example:

```text
/home/platne/serwer88382/public_html/preview/.private/github-app-key.pem
```

Do not commit the key file to the repository.

Record these values for `pca-deploy-config.json`:

- GitHub App ID
- Installation ID for the repository installation
- key path on the server

## One-time server setup

Copy the webhook endpoint into the preview web root:

```bash
cd ~/site-src
mkdir -p ../public_html/preview
cp server/github-webhook.php ../public_html/preview/github-webhook.php
```

Create the private config file and private directories under the preserved preview root:

```bash
mkdir -p ../public_html/preview/.private/deploy-queue ../public_html/preview/.private/deploy-logs
cat > ../public_html/preview/.private/.htaccess <<'EOF'
Require all denied
Deny from all
EOF
cp server/pca-deploy-config.example.json ../public_html/preview/.private/pca-deploy-config.json
chmod 600 ../public_html/preview/.private/.htaccess
chmod 600 ../public_html/preview/.private/pca-deploy-config.json
chmod 600 ../public_html/preview/.private/github-app-key.pem
```

The `.htaccess` file is important because `.private` is under the preview web root and contains deployment secrets.

Edit `../public_html/preview/.private/pca-deploy-config.json` and set:

- `webhook_secret` to the same secret configured in the GitHub App webhook settings.
- `github_app_id` to the GitHub App ID.
- `github_app_installation_id` to the repository installation ID.
- `github_app_private_key_path` to the key path on the server.
- paths if LH.pl uses different absolute paths.

Keep `allow_preview_from_forks` as `false` unless the server is isolated enough to build untrusted PR code.

The worker signs a short-lived GitHub App JWT with `openssl`, exchanges it for an installation access token, and uses that token to create/update Checks API check runs and upsert PR preview comments.

## Cron worker

Run the worker from cron, for example once per minute:

```cron
* * * * * cd /home/platne/serwer88382/site-src && tools/.venv/bin/python tools/webhook_deploy_worker.py >> /home/platne/serwer88382/public_html/preview/.private/deploy-worker.log 2>&1
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

Because the webhook endpoint and deployment state now live inside `public_html/preview/`, the whole deploy control plane is preserved by the root-level `preview/` exclusion.

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

The production check output lists all public production sites from `config/seo.json` `site_urls`, including the English, French, and Croatian domains.

For successful preview deploys, the check details URL points to the ready preview:

```text
https://preview.polandchildabduction.pl/pr-<number>/
```

If preview deployment fails, the check details URL points to the public `_deploy.log` file instead.

For PR preview deploys, the worker also creates or updates one PR conversation comment marked with `<!-- pca-preview-deploy-comment -->`. The same comment is updated when deployment starts, succeeds, or fails, so repeated pushes and `/preview` rebuilds do not create duplicate bot comments.

## Manual test

After installing the config, a dry manual queue test can be done by creating a small job file:

```bash
cat > ../public_html/preview/.private/deploy-queue/manual-preview.json <<'JSON'
{
  "type": "preview_comment",
  "repository": "jedrek0429/bansleben-pca",
  "pr_number": 9
}
JSON

tools/.venv/bin/python tools/webhook_deploy_worker.py
```

Use a current open PR number for the test.
