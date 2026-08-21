# V2 migration stage 2: locale page metadata

Base: `refactor/site-model-ssot`

## Scope

Normalize the existing EN/FR/HR locale page metadata so locale packages contain only locale-owned page data.

This stage removes pre-v2 duplicated structure from `locales/*.json` while preserving all effective routes and rendered output.

## Changes

- Remove locale `parent` fields. Page hierarchy is owned by the resolved site model.
- Replace full hierarchical page slugs with local slug segments.
- Remove disabled national-law stubs for pages that do not belong to a site.
- Remove any other page-structure fields already owned by `config/pages.json` or `sites/<lang>.json`.
- Keep titles, local slugs, enablement where still required by the v2 model, and all other translated content unchanged.

## Acceptance criteria

- EN, FR and HR resolve to the same public routes as stage 1.
- Existing page content and translations are unchanged.
- Preview and production builds remain deployable.
- Legacy locale-structure warnings are eliminated rather than suppressed.
- No new compatibility logic is introduced.
