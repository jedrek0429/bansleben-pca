# Continuous integration

PCA CI is split into focused quality gates. Each visible GitHub check should answer one useful question about the proposed change rather than expose workflow plumbing as a merge signal.

## Site model

Runs `build.py check --strict` against the real repository state. The additive-translation synthetic test also runs here as an architecture regression test; it is intentionally not a separate permanent GitHub check.

## Preview build

Builds one real PR-prefixed preview and uploads that generated site as an artifact. All downstream checks consume this exact build rather than rebuilding the site with different URL settings.

## Generated-site integrity

Checks the generated HTML for broken local links and asset references and rejects duplicate canonical URLs. This validates the emitted site rather than only its source configuration.

## Accessibility

Serves the same prefixed preview artifact and scans every generated page with Playwright and axe-core. CI blocks on automatically detectable serious or critical WCAG A/AA violations. Automated scanning is a regression guard, not a substitute for manual accessibility review.

## Screenshots

Serves the same prefixed preview artifact and captures desktop and mobile screenshots with Playwright. Screenshot failures are ordinary CI failures and are not hidden behind `continue-on-error`.

## Screenshot publication

Screenshot publication is not a PR quality gate. A separate `workflow_run` workflow runs after successful PCA CI, downloads only the screenshot artifact, publishes the `site-screenshots` branch and updates the PR comment. This keeps write permissions out of the untrusted pull-request CI workflow.

The publisher workflow must already exist on the default branch before GitHub will trigger it through `workflow_run`, so publication cannot be demonstrated end-to-end by the PR that first introduces the workflow.

## Dependency order

```text
Site model
    |
    v
Preview build
    |-------------------|-------------------|
    v                   v                   v
Generated-site       Accessibility       Screenshots
integrity                                   |
                                            v
                              workflow_run publisher
                              (outside PR quality gates)
```

Only the quality concerns above should appear as merge checks. Helper steps and publication infrastructure should remain implementation details unless their failure represents a defect in the proposed site.
