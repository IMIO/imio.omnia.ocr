# -*- coding: utf-8 -*-
from imio.omnia.ocr.interfaces import IOcrText
from zope.container.interfaces import IContainerModifiedEvent


def refresh_text(obj, event):
    """Make the OCR records agree with the files after the content was added or modified.

    A new or changed PDF file drops the old text at once and waits for a new generation.
    The handler writes the annotation only. It sends no event and it does not reindex.
    """
    if IContainerModifiedEvent.providedBy(event):
        # The files of a container do not change when its children change.
        return
    text = IOcrText(obj, None)
    if text is None:
        return
    for fieldname in text.fieldnames():
        text.for_field(fieldname).refresh()
