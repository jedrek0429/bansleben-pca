# bansleben-pca

This repository contains the source for the Poland Child Abduction static sites in English, French and Croatian.

## URLs

- `en`: <https://polandchildabduction.com/>
- `fr`: <https://enlevementparentalpologne.pl/>
- `hr`: <https://roditeljskaotmicapoljska.pl/>

## Build pipeline

The Python tooling lives in `tools/`:

- `build.py`: builds the static site from source into `../site-dist/`
- `validate_locales.py`: validates locale JSON files against the site config
- `format_hyperlinks.py`: normalizes bare links in Markdown content
- `BUILD_AND_PUBLISH.py`: runs validation, hyperlink formatting, build, and publish
- `dev_build_and_publish.py`: builds and publishes a preview/development output
- `publish.py`: publishes a built `../site-dist/` to a target directory such as `../public_html/`

## Typical workflow

Run tools from the project root unless a script says otherwise.

### Compile Python scripts

```sh
python -m compileall tools/
```

### Build the static site

```sh
python tools/build.py --root .
```

### Build and publish

```sh
python tools/BUILD_AND_PUBLISH.py --root .
```
