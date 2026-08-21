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
| Validate site/config packages | `python tools/build.py check --root .` |
| Validate without interactive autofix prompt | `python tools/build.py check --root . --no-autofix-prompt` |
| Build local site output | `python tools/build.py site --root .` |
| Build local site without writing output | `python tools/build.py site --root . --dry` |
| Show resolved config | `python tools/build.py inspect --root .` |
| Remove generated output | `python tools/build.py clean --root .` |
| Run deploy worker | `python tools/webhook_deploy_worker.py` |

When `check` fails in an interactive terminal, it asks whether to run `utils autofix-locales`:

```text
Run utils autofix-locales now? [Y/n]
```

Deploy and preview workflows disable that prompt so automation never waits for input.

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

`preview` owns preview-specific URL rewriting. It does not expose production-only options.

## Generated image pipeline

Files under `assets/` are source-controlled inputs. The build does not create, replace, or delete image files there.

Before rendering HTML, the builder discovers local raster images referenced by locale/configuration data and content, then uses Pillow to create responsive WebP renditions. Generated files live only in disposable build output under `_generated/images/` and use content-derived names. The builder stores the generated renditions in an in-memory manifest; cards, heroes, logos, and supported content images consume that manifest instead of predicting derivative filenames.

Generated HTML is validated after rendering. Every local `img`/`source` `src` and `srcset` candidate must resolve to a file in the build output or the build fails.

Production places `_generated/` under each language output directory, matching the existing per-language asset layout. Preview builds place one shared `_generated/` directory at the preview root.

## Utilities

Utilities live under `utils` because they maintain source content or locale metadata rather than define deployment modes.

| Task | Command |
| --- | --- |
| Normalize legacy locale structure | `python tools/build.py utils autofix-locales --root .` |
| Normalize Markdown hyperlinks | `python tools/build.py utils format-links --root .` |
| Check hyperlink formatting without writing | `python tools/build.py utils format-links --root . --check` |
| Run hyperlink formatter self-test | `python tools/build.py utils format-links --self-test` |

`utils autofix-locales` is deliberately conservative. It removes duplicated legacy structural fields and reduces legacy full-path slugs to their local segment. It does not create translation text.

Image conversion is no longer a source-tree maintenance utility. Responsive derivatives are generated automatically as disposable build output.

## Builder implementation

| Path | Purpose |
| --- | --- |
| `tools/build.py` | Small app launcher. |
| `tools/build/runner.py` | Command-line parser and command dispatch. |
| `tools/build/builder.py` | Site build orchestration. |
| `tools/build/workflow.py` | Preview and production workflows. |
| `tools/build/publisher.py` | Safe publish/copy checks. |
| `tools/build/validation.py` | Site model and locale-package validation. |
| `tools/build/output_validation.py` | Validation of image references in rendered output. |
| `tools/build/image_pipeline.py` | Discovery and deterministic responsive WebP generation. |
| `tools/build/autofix.py` | Conservative locale normalization utility. |
| `tools/build/hyperlinks.py` | Markdown hyperlink normalization utility. |
| `tools/build/images.py` | Markdown and HTML content image URL/rendering helpers. |

## Recommended checks before opening a PR

```sh
python -m compileall -q tools/
python tools/build.py check --root .
python tools/build.py site --root . --dry
python tools/build.py site --root .
```

For server setup and deploy behavior, start with [`docs/workspace.md`](workspace.md).
