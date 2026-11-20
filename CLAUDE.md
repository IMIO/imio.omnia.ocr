# imio.omnia.ocr

Plone 6 add-on that gives Dexterity content a machine-generated text version of its PDF file. The text comes from the Omnia Core OCR API (`IOmniaCoreAPIService.ocr_markdown` in `imio.omnia.core`). The package is generic: a host package enables the behavior on a type, shows the text in its templates and adds it to its `SearchableText` indexer.

## Hard rule

A host can clear important data (for example a qualified timestamp) on any `ObjectModifiedEvent`. So this package:

- never sends a modified event,
- never stores the text in a schema field or in a child object (annotation only),
- never calls `reindexObject()` without `idxs` (that changes the modification date). Use `api.reindex(obj)`.

## Project layout

```
src/imio/omnia/ocr/
├── browser/
│   ├── controlpanel.py          # @@omnia-ocr-settings, a tab of the Omnia control panel
│   ├── views.py                 # @@ocr-info, @@ocr-text, @@ocr-text-fragment, @@ocr-manage-panel, @@ocr-process, @@ocr-manage
│   ├── templates/               # ocr_text.pt, ocr_manage_panel.pt
│   ├── static/omnia-ocr.js      # Script of the manage panel (no build step)
│   └── configure.zcml
├── profiles/
│   ├── default/                 # Settings, bundle, ocr_status index, permission roles, control panel tab
│   └── uninstall/
├── locales/                     # i18n (en, fr), written by hand
├── adapters.py                  # OcrText: IOcrText adapter over the annotation
├── storage.py                   # OcrRecord persistent class (do not move: the ZODB stores its path)
├── api.py                       # process, searchable_text, render_html, get_text, get_runner, get_setting
├── render.py                    # Markdown -> safe HTML, Markdown -> plain text
├── cache.py                     # BoundedCache (replay cache, render cache)
├── runners.py                   # SyncRunner (IOcrRunner "sync") + runners vocabulary
├── subscribers.py               # refresh_text on added/modified events
├── indexers.py                  # ocr_status
├── restapi.py                   # GET @ocr-text
├── config.py                    # Constants (annotation key, statuses, modes, permission title)
├── interfaces.py                # Browser layer, IOcrEnabled, IOcrText, IOcrRunner, IOcrInfoView, IOmniaOcrSettings
├── testing.py                   # IMIO_OMNIA_OCR_*_TESTING fixtures (on IMIO_OMNIA_CORE_FIXTURE)
├── configure.zcml               # Profiles, behavior, adapter, runner, indexer, subscribers, REST service
└── permissions.zcml             # imio.omnia.ocr.ManageTextVersion
```

## How it works

1. A host enables the marker behavior `imio.omnia.ocr` (`IOcrEnabled`) on a type.
2. `subscribers.refresh_text` runs on added/modified events. It compares the SHA-256 of the file with the stored `source_hash`. A new or changed PDF drops the old text and sets `pending`. A removed or non-PDF file removes the record. The handler only writes the annotation.
3. A user who can manage the text opens the page. `@@ocr-manage-panel` carries `data-ocr-process-url` when the status is `pending`. `omnia-ocr.js` sends one POST to `@@ocr-process`.
4. `@@ocr-process` runs the active `IOcrRunner`. The `sync` runner calls `api.process`, which calls the API, stores the result or the failure and reindexes `SearchableText` and `ocr_status`. A result that renders to nothing (the API answers 200 with empty pages for a damaged file) is a failure.
5. Nothing retries a failure. A manager uses the button of the panel (`@@ocr-manage`, action `regenerate`).

### Storage

`IAnnotations(obj)["imio.omnia.ocr"]` is a `PersistentMapping` of field name to `OcrRecord`. A record holds `status`, `pages` (a `PersistentList` of dicts with `index`, `markdown`, `header`, `footer`, `confidence`), `page_count`, `confidence` (lowest page score), `model`, `generated`, `source_hash`, `error`, `attempts` and `hidden`. Read and write through `IOcrText(obj)` (or `api.get_text(obj, fieldname)`), not directly.

### Replay cache

Zope replays a request after a write conflict. `api._replay_cache` keeps the last 8 API results of the process, keyed by `(source_hash, options)`, so that a replay does not call (and bill) the API again. A lock per key makes a second thread with the same file wait and reuse the result. The `regenerate` action removes the cached result of the file. `process(force=True)` skips the cache, except in a replayed request (`request.retry_count`).

### Rendering

`render.render_pages` converts each page with Python-Markdown (`tables`, `sane_lists`), then works on the lxml tree: it keeps only `ALLOWED_TAGS` and `ALLOWED_ATTRIBUTES` (the OCR copies HTML code that a document shows, and the filter of Plone accepts `iframe` and `style`), it keeps a link only when its target is `http(s)` or `mailto`, it shifts the headings (the highest becomes h3 by default, never below h6), replaces a described image with a text and removes an image without description. Each page body goes through the `safe_html` transform of Plone. The trusted `<section>` wrapper is added after the filter. If the HTML filter of Plone is off, the default lxml cleaner is used instead: OCR output is never shown without a filter. `api.render_html` adds the translated labels and a small cache.

## Development

This package is developed inside a parent buildout as an mr.developer checkout. From the buildout root:

```bash
bin/test -s imio.omnia.ocr
```

## Code style

- Formatter: **Black** (line length 120, see `pyproject.toml`)
- Import sorting: **isort** with `profile = plone`
- Linter: **flake8** (see `setup.cfg`)
- i18n domain: `imio.omnia.ocr` — use `from imio.omnia.ocr import _`
- Comments and docstrings: Simplified Technical English, short, no history
- French translations follow the iMio typography rules: `’`, non-breaking space before `: ; ! ?`, `« »` with non-breaking spaces

## i18n

Edit `locales/imio.omnia.ocr.pot` and the `.po` files by hand. The `.mo` files are not in git (`*.mo` is ignored), as in the sibling packages. The instance compiles them at startup when `zope_i18n_compile_mo_files` is set.

## Registry settings

Stored under `imio.omnia.ocr.interfaces.IOmniaOcrSettings`: `enabled`, `runner`, `timeout`, `extract_header_footer`, `html_tables`, `image_descriptions`, `confidence`, `low_confidence_threshold`, `low_confidence_mode` (`warn` / `hide` / `noindex`), `inline_max_pages`. Read them with `api.get_setting(name)`: it gives the schema default when a record is missing.

## Architecture notes

- Auto-included in Plone via `z3c.autoinclude.plugin` (target: `plone`).
- Browser layer `IImioOmniaOcrLayer` gates the views and the REST service.
- The views are registered for `IOcrEnabled`. Text views use the `View` permission of the content. `@@ocr-process` and `@@ocr-manage` need `imio.omnia.ocr: Manage text version`, accept POST only and check the plone.protect token.
- `@@ocr-manage-panel` uses the `View` permission and renders nothing for a user who cannot manage, so a host template can include it for everybody.
- `enabled` off stops the generation only. Existing text versions stay visible.
- Namespace packages: `imio`, `imio.omnia` (pkg_resources style, shared with the sibling packages).
