# V2 migration stage 4: remove pre-v2 compatibility

Base: `refactor/seo-site-ownership`

## Scope

Remove transitional support for pre-v2 configuration forms after all existing EN/FR/HR data has been migrated.

## Changes

- Remove compatibility handling for locale `parent` fields.
- Remove compatibility handling for full-path locale slugs.
- Remove warnings that exist only to support legacy schema forms.
- Reject reintroduction of pre-v2 structural or multilingual ownership patterns during validation.
- Remove migration-only helpers that are no longer required once the repository is normalized.

## Acceptance criteria

- EN, FR and HR build and deploy without legacy compatibility behavior.
- Normal validation emits no pre-v2 migration warnings.
- Old structural forms fail validation rather than being silently normalized.
- No compatibility branch remains solely for the previous site schema.
- The resulting architecture is the baseline for additive future locale packages.
