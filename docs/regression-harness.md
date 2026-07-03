# Site regression harness

This harness protects the static PCA site while legacy WordPress/Divi CSS and JavaScript are removed.

The rule for cleanup work is simple: AI or humans may propose smaller CSS/JS, but the automated checks decide whether the change is safe.

## What PR 1 adds

- Playwright smoke tests for core page structure and key behavior.
- Opt-in Playwright visual regression tests for page screenshots and UI states.
- Lighthouse CI configuration for collecting performance reports and warning-level budgets.
- A GitHub Actions workflow that builds the static site, uploads a website preview artifact, and runs smoke checks on pull requests.

No generated site output, templates, content, locale data, or legacy assets are changed by this harness.

## Install locally

```sh
npm install
npx playwright install chromium
python -m pip install markdown pymdown-extensions imagesize
```

## Build the site

```sh
npm run build:site
```

The current Python build writes output to `../site-dist/`.

## Preview from GitHub Actions

Every workflow run uploads the built static site as a `site-preview` artifact. Download and unzip it, then serve it locally:

```sh
unzip site-preview.zip -d site-preview
python -m http.server 8080 --directory site-preview
```

Then open one of the localized roots:

- `http://127.0.0.1:8080/en/`
- `http://127.0.0.1:8080/fr/`
- `http://127.0.0.1:8080/hr/`

The artifact is a downloadable preview bundle, not a public live deployment. A hosted preview URL can be added later with GitHub Pages, Cloudflare Pages, Netlify, or another deployment target.

## Run smoke checks

```sh
npm run test:smoke
```

These checks verify that key localized pages load, the header/footer/content shell exists, the contact form still posts to the static PHP endpoint, the mobile menu opens/closes, and the sticky header activates after scroll.

## Create visual baselines

Visual regression is opt-in until baseline screenshots are intentionally committed.

```sh
npm run snapshots:update
```

Review the generated files under `tests/**/__screenshots__/`. Commit only baselines that represent the approved current look.

## Run visual regression

```sh
npm run test:visual
```

For stricter pixel-for-pixel comparisons, run:

```sh
PCA_STRICT_PIXELS=1 npm run test:visual
```

Keep screenshot generation and comparison in the same OS/browser environment whenever possible. Browser screenshots can vary across machines because of font rendering, graphics drivers, headless mode, and browser version.

## Collect Lighthouse reports

```sh
npm run lhci:collect
```

To run the warning-level budget assertions locally:

```sh
npm run lhci:assert
```

The initial budgets are intentionally warning-level so this harness can land before the legacy Divi cleanup. Later PRs should tighten these budgets as unused CSS/JS is removed.

## Recommended cleanup workflow

1. Build the current site.
2. Generate and commit visual baselines from the approved current look.
3. Let AI propose the smallest CSS/JS cleanup patch.
4. Run smoke tests, visual tests, and Lighthouse.
5. Accept the patch only if visual and behavior checks pass.
