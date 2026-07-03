# bansleben-pca

This workspace contains the source and deployed output for the Poland Child Abduction static sites in English, French and Croatian.

## URLs

- `en`: <https://polandchildabduction.com/>
- `fr`: <https://enlevementparentalpologne.pl/>
- `hr`: <https://roditeljskaotmicapoljska.pl/>

## Build pipeline

The main scripts live in `tools/`:

- `build.py`: builds the site from source into `../site-dist/`
- `validate_locales.py`: validates locale JSON files against the site config
- `autofix_locales.py`: applies safe locale fixes
- `BUILD_AND_PUBLISH.py`: runs validation, then build, then publish for the v2 flow
- `publish.py`: publishes a built `../site-dist/` to a target directory (`../public_html/`)

## Typical workflow

Run tools from project root unless a script says otherwise.

### Compile all python scripts
```sh
./tools/.venv/bin/python -m compileall tools/
```

### Publish editor
```sh
./tools/.venv/bin/python ./tools/dev_publish_editor.py --dest ../public_html/en/editor
```

### Build and publish
```sh
./tools/.venv/bin/python ./tools/BUILD_AND_PUBLISH.py
```
