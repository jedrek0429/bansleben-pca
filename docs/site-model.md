# Site model and locale ownership

The builder resolves each public site from three layers. Each fact should have one owner.

## 1. Shared page model

`config/pages.json` defines structure that is common to every site:

- stable page keys;
- parent relationships;
- templates and structural rendering flags;
- shared navigation structure.

It must not contain translated titles, translated slugs, or lists of languages for which a page is enabled.

A page path is derived from the parent graph. Locale files provide only the translated slug value. Strict validation rejects legacy full-path slugs; `utils autofix-locales` can reduce migration input to its final path segment.

## 2. Site manifest

`sites/<lang>.json` defines the deployment identity and structural differences that belong only to one public site. It owns the site's production URL, hreflang identifier, Open Graph locale and social image. `extra_pages` may add pages without changing the shared model.

For example, national-law pages differ by audience. English, French, and Croatian therefore declare their national-law page sets in their own site manifests rather than adding every possible national-law page to the shared schema.

A site-only page owns its structural `parent` and `template` in the site manifest. Its translated title and slug remain in the matching locale file.

`organization_url_language_override` is optional. It is used only when the external organisation profile linked from structured data uses a different language suffix from the site itself.

## 3. Locale

`locales/<lang>.json` owns language-dependent values:

- site and navigation strings;
- shared-page enablement;
- page titles and translated slug segments;
- card copy and image metadata;
- form and interface strings.

A locale owns translated SEO descriptions under `seo`:

```json
{
  "seo": {
    "default_description": "...",
    "descriptions": {
      "introduction": "..."
    }
  }
}
```

Site identity belongs in the site manifest, translated descriptions belong in the locale, and neither is duplicated in `config/seo.json`.

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

Strict validation rejects pre-v2 duplicated `parent` fields and full-path locale slugs. `utils autofix-locales` can normalize those structural forms without inventing translations. Language-keyed SEO registries are no longer supported.

## Adding another site

Adding a new translation should be additive. A normal new site consists of:

```text
sites/<lang>.json
locales/<lang>.json
content/<lang>/...
```

and any locale-specific assets it needs. The site manifest still supplies deployment identity when the locale uses only shared pages. Existing site manifests and shared page definitions should not need modification merely because another language is added.

A change to `config/pages.json` is reserved for an actual change to the shared information architecture.
