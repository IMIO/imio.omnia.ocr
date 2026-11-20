# -*- coding: utf-8 -*-
"""Constants of the package."""

# Key of the annotation that holds the OCR records of a content object.
ANNOTATION_KEY = "imio.omnia.ocr"

# Prefix of the registry records of the settings.
SETTINGS_PREFIX = "imio.omnia.ocr.interfaces.IOmniaOcrSettings"

# Title of the permission to generate, regenerate, hide and show a text version.
MANAGE_PERMISSION = "imio.omnia.ocr: Manage text version"

STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

MODE_WARN = "warn"
MODE_HIDE = "hide"
MODE_NOINDEX = "noindex"

# Content types of the files that the package sends to the OCR.
SUPPORTED_CONTENT_TYPES = ("application/pdf",)

# Name of the runner that does the OCR in the current request.
DEFAULT_RUNNER = "sync"

# Catalog indexes that depend on the OCR record.
REINDEX_IDXS = ("SearchableText", "ocr_status")

# Level of the highest heading in the HTML of a text version.
DEFAULT_HEADING_LEVEL = 3

# Maximum length of a stored error message.
ERROR_MAX_LENGTH = 300
