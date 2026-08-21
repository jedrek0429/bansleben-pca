# Additive translation migration

This stack completes the additive locale contract established by the site-model v2 work.

## Stage 1: discovery and contributor contract

Make site discovery depend on site packages rather than a hard-coded language registry, remove stale language-list constants, and document the supported translation workflow in `docs/adding-a-translation.md`.

Acceptance criterion: the builder can discover a new site package without adding its language code to Python source.

## Stage 2: site and SEO metadata ownership

Move per-site deployment identity and per-locale SEO metadata out of shared multilingual maps. Shared SEO configuration retains only language-independent behaviour/schema.

Acceptance criterion: a new site does not require edits to shared SEO language maps.

## Stage 3: enforce the additive contract

Remove the remaining compatibility paths that permit shared language registries, validate translation completeness from the effective site model, and add a regression check proving that a representative additional site can be introduced using new package files only.

Acceptance criterion: adding a normal production-ready translation requires only `sites/<lang>.json`, `locales/<lang>.json`, `content/<lang>/` and any language-specific source assets.

Every stage must leave the existing EN, FR and HR sites buildable and deployable.
