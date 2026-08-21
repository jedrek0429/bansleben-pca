# Adding a translation

PCA treats each deployed language as a site package implementing the shared site model. A normal translation must be additive: introducing a new language must not require editing the definitions of existing languages or adding the language code to builder source.

## Ownership

`config/pages.json` owns language-independent page structure: stable page keys, parent relationships, templates, navigation participation and shared structural flags.

`config/seo.json` owns only language-independent SEO behaviour and shared schema configuration.

`sites/<lang>.json` owns deployment and structural facts for one site. This includes the production URL, language/locale identifiers and any pages or structural overrides that genuinely exist only for that audience.

`locales/<lang>.json` owns linguistic choices for that language: page titles, local slug segments, navigation and interface copy, SEO descriptions, site name and other translated metadata.

`content/<lang>/` owns translated page bodies. Content does not silently fall back to another language for a production-ready site.

`assets/` contains source-controlled assets. A translation may add source assets where required; responsive image derivatives remain generated build output and must not be committed as part of the translation.

## Adding a language

For a new language code such as `pl`:

1. Add `sites/pl.json` with the site's deployment identity and any site-specific structural extensions.
2. Add `locales/pl.json` implementing the required translated fields for every page in the effective Polish site model.
3. Add `content/pl/` and the required Markdown content for content-backed pages.
4. Add only genuinely language-specific source assets that the Polish site references.
5. Run the site checks and a preview build. Missing required translations, duplicate routes, missing content and invalid site-model references must fail validation rather than fall back silently.

A normal new translation must not require changes to `config/pages.json`, `config/seo.json`, builder language lists, or existing `sites/`, `locales/` and `content/` packages. Shared files should change only when the new site requires a genuinely new application capability or shared structural feature.

## Site-specific pages

Languages do not have to expose identical page graphs. Pages shared by all sites belong in `config/pages.json`. A page that exists only for one audience, such as a national-law page, belongs in that site's `extra_pages` definition in `sites/<lang>.json` and receives its title, slug, SEO metadata and content from the corresponding locale/content package.

Do not add disabled placeholders for another site's pages to a locale file.

## Slugs and routes

Locale files store only the translated slug segment for a page. Full routes are derived from the structural parent graph. Do not duplicate parent relationships or full hierarchical paths in locale data.

## Translation completeness

A production-ready site package is complete only when the builder can resolve its effective page graph and validate every required language-owned field and content file. Missing data must be reported for that language. English or another existing locale must not be used as an implicit production fallback.

## Acceptance test for the architecture

The additive contract is satisfied when a representative new site can be introduced by adding only its new `sites/<lang>.json`, `locales/<lang>.json`, `content/<lang>/` files and any language-specific source assets, with no edits to existing tracked configuration or builder source.
