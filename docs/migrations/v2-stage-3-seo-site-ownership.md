# V2 migration stage 3: SEO and site metadata ownership

Base: `refactor/locale-metadata-v2`

## Scope

Move locale-owned SEO values and deployment/site identity out of shared multilingual maps so each fact has one owner.

## Changes

- Keep language-independent SEO behavior and schema in shared configuration.
- Move translated default and per-page descriptions to locale/site-owned data.
- Move locale-specific Open Graph locale and social image selection to the owning site package where appropriate.
- Separate domain/site deployment facts from SEO behavior.
- Preserve canonical URLs, hreflang output, metadata text, and structured-data behavior for EN/FR/HR.

## Acceptance criteria

- Adding a future locale does not require extending shared language-keyed SEO maps.
- Existing EN/FR/HR rendered metadata remains equivalent.
- Shared SEO configuration contains no translated page copy.
- Site/domain facts have a single declared owner.
- Preview and production builds remain deployable.
