# -*- coding: utf-8 -*-
from imio.omnia.ocr.interfaces import IOcrEnabled
from imio.omnia.ocr.interfaces import IOcrText
from plone.indexer import indexer


@indexer(IOcrEnabled)
def ocr_status(obj):
    """Index the status of the text version of the primary field."""
    status = IOcrText(obj).status
    if status is None:
        # The catalog does not index the content in ``ocr_status``.
        raise AttributeError("ocr_status")
    return status
