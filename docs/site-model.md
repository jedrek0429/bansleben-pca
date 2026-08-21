# Site model and locale ownership

The builder resolves each public site from three layers. Each fact should have one owner.

## 1. Shared page model

`config/pages.json` defines structure that is common to every site:

- stable page keys;
- parent relationships;
- templates and structural rendering flags;
- shared navigation structure.

It must not contain translated titles, translated slugs, or lists of languages for which a page is enabled.

A page path is derived from the parent graph. Locale files provide only the translated slug value. During migration, legacy full-path slugs are accepted, but only the final path segment is consumed.

## 2. Site manifest

`sites/<lang>.json` defines structural differences that belong only to one public site. `extra_pages` may add pages without changing the shared model.

For example, national-law pages differ by audience. English, French, and Croatian therefore declare their national-law page sets in their own site manifests rather than adding every possible national-law page to the shared schema.

A site-only page owns its structural `parent` and `template` in the site manifest. Its translated title and slug remain in the matching locale file.

## 3. Locale

`locales/<lang>.json` owns language-dependent values:

- site and navigation strings;
- shared-page enablement;
- page titles and translated slug segments;
- card copy and image metadata;
- form and interface strings.

A future locale may also own translated SEO values under `seo`:

```json
{
  "seo": {
    "hreflang": "pl",
    "og_locale": "pl_PL",
    "social_image": "/assets/social/og-pl.jpg",
    "default_description": "...",
    "descriptions": {
      "introduction": "..."
    }
  }
}
```

Existing translated SEO maps in `config/seo.json` remain supported during migration. Locale SEO values override those maps. New locales should not add translated values to shared SEO configuration.

## Effective site

For a language `xx`, the effective page graph is:

```text
config/pages.json
+ sites/xx.json extra_pages
+ locales/xx.json page applicability and translations
= effective site xx
```

Rendering, card derivation, sitemap generation, and route resolution operate on this effective graph.

## Invariants

`python tools/build.py check --root .` validates the model before deployment. In particular:

- shared page keys are unique;
- shared and effective parent graphs contain no missing parents or cycles;
- site-only page keys cannot collide with shared keys;
- every effective page has a locale entry;
- enabled pages have translated titles and slugs;
- resolved URLs are unique within a site;
- locale files cannot enable undeclared pages;
- translated or locale-applicability fields cannot be reintroduced into shared page definitions.

The checker currently warns about two pre-v2 representations that are ignored structurally: duplicated `parent` fields in locale page entries and full-path locale slugs. `utils autofix-locales` only normalizes those representations; it does not generate or guess translations.

## Adding another site

Adding a new translation should be additive. A normal new site consists of:

```text
sites/<lang>.json
locales/<lang>.json
content/<lang>/...
```

and any locale-specific assets it needs. The site manifest may be empty if the locale uses only shared pages. Existing site manifests and shared page definitions should not need modification merely because another language is added.

A change to `config/pages.json` is reserved for an actual change to the shared information architecture.
