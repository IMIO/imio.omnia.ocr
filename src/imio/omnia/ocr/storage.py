# -*- coding: utf-8 -*-
"""Persistent objects that hold the text versions.

The database stores the path of these classes. Do not move or rename them.
"""

from persistent import Persistent
from persistent.list import PersistentList


class OcrRecord(Persistent):
    """Text version of one file field.

    The pages are in their own persistent object.
    A read of the status does not load the text.
    """

    status = None
    page_count = 0
    confidence = None
    model = None
    generated = None
    source_hash = None
    error = None
    attempts = 0
    hidden = False

    def __init__(self):
        self.pages = PersistentList()
