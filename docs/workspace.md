# Workspace setup

This guide explains how to recreate the project workspace on a new server.

The goal is to end with this layout:

```text
/home/platne/serwer88382/
  site-src/                    # Git checkout of this repository
  site-dist/                   # temporary build output
  public_html/                 # production web root
    en/
    fr/
    hr/
    preview/                   # preview web root
      github-webhook.php
      .private/                # deploy config, queues, logs, key, locks
        pca-deploy-config.json
        github-app-key.pem
        deploy-queue/
        deploy-logs/
```

The absolute base path can change on a new server. If it changes, update every path in `public_html/preview/.private/pca-deploy-config.json`.

## 1. Clone the repository

```sh
cd /home/platne/serwer88382
git clone https://github.com/jedrek0429/bansleben-pca.git site-src
cd site-src
```

## 2. Install Python dependencies

```sh
python -m venv tools/.venv
tools/.venv/bin/python -m pip install -r requirements.txt
```

For a quick local check:

```sh
tools/.venv/bin/python -m compileall -q tools/
tools/.venv/bin/python tools/validate_locales.py --root .
tools/.venv/bin/python tools/build.py --root .
```

The build writes generated files to `../site-dist/`.

## 3. Create the preview and private deploy folders

```sh
mkdir -p ../public_html/preview/.private/deploy-queue
mkdir -p ../public_html/preview/.private/deploy-logs
```

Block direct web access to `.private`:

```sh
cat > ../public_html/preview/.private/.htaccess <<'EOF'
Require all denied
Deny from all
EOF
chmod 600 ../public_html/preview/.private/.htaccess
```

## 4. Install the webhook endpoint

```sh
cp server/github-webhook.php ../public_html/preview/github-webhook.php
```

The public webhook URL should be:

```text
https://preview.polandchildabduction.pl/github-webhook.php
```

## 5. Create the private deploy config

```sh
cp server/pca-deploy-config.example.json ../public_html/preview/.private/pca-deploy-config.json
chmod 600 ../public_html/preview/.private/pca-deploy-config.json
```

Edit `pca-deploy-config.json` and set:

- `webhook_secret`
- `github_app_id`
- `github_app_installation_id`
- `github_app_private_key_path`
- `site_src`
- `public_html`
- `python`
- `preview_root`
- `private_dir`
- `queue_dir`
- `log_dir`

Keep `allow_preview_from_forks` as `false` unless the server is isolated enough to build untrusted code.

## 6. Add the GitHub App key

Save the GitHub App private key here, or update the config if you use a different path:

```text
../public_html/preview/.private/github-app-key.pem
```

Then lock down the file:

```sh
chmod 600 ../public_html/preview/.private/github-app-key.pem
```

Do not commit the private key or real deploy config.

## 7. Configure the GitHub App

Create or update the GitHub App used for deploys.

Repository permissions:

- Checks: read and write
- Issues: read and write
- Pull requests: read-only
- Contents: read-only
- Metadata: read-only

Webhook settings:

```text
Webhook URL: https://preview.polandchildabduction.pl/github-webhook.php
Webhook secret: same value as webhook_secret in pca-deploy-config.json
```

Subscribed events:

- Push
- Pull request
- Issue comment

Install the app only on `jedrek0429/bansleben-pca`.

## 8. Add the cron worker

Example cron entry:

```cron
* * * * * cd /home/platne/serwer88382/site-src && tools/.venv/bin/python tools/webhook_deploy_worker.py >> /home/platne/serwer88382/public_html/preview/.private/deploy-worker.log 2>&1
```

The worker uses a lock file, so overlapping cron runs should exit safely.

## 9. Verify production publish

From `site-src`:

```sh
tools/.venv/bin/python tools/build_and_publish.py --root . --dest ../public_html
```

Confirm the public sites load:

- <https://polandchildabduction.pl/>
- <https://enlevementparentalpologne.pl/>
- <https://roditeljskaotmicapoljska.pl/>

## 10. Verify preview publish

Run a manual preview-style publish:

```sh
tools/.venv/bin/python tools/build_and_publish.py \
  --root . \
  --dest ../public_html/preview/pr-123 \
  --url-prefix /pr-123 \
  --lang-in-url \
  --write-preview-index
```

Confirm this loads:

```text
https://preview.polandchildabduction.pl/pr-123/
```

Delete the test preview when finished:

```sh
rm -rf ../public_html/preview/pr-123
```

## 11. Verify webhook worker

Create a small test job:

```sh
cat > ../public_html/preview/.private/deploy-queue/manual-preview.json <<'JSON'
{
  "type": "preview_comment",
  "repository": "jedrek0429/bansleben-pca",
  "pr_number": 1
}
JSON

tools/.venv/bin/python tools/webhook_deploy_worker.py
```

Use a current open PR number for a real test.

## Safety notes

- Do not edit generated files in `../site-dist/` or `../public_html/<lang>/`.
- Do not commit files from `public_html/preview/.private/`.
- Production publishing preserves `preview/`, `.private/`, and `github-webhook.php`.
- Preview builds from forks are disabled by default for safety.
