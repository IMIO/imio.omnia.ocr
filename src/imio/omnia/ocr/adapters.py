# -*- coding: utf-8 -*-
from Acquisition import aq_base
from datetime import datetime
from datetime import timezone
from imio.omnia.ocr.config import ANNOTATION_KEY
from imio.omnia.ocr.config import ERROR_MAX_LENGTH
from imio.omnia.ocr.config import STATUS_DONE
from imio.omnia.ocr.config import STATUS_FAILED
from imio.omnia.ocr.config import STATUS_PENDING
from imio.omnia.ocr.config import SUPPORTED_CONTENT_TYPES
from imio.omnia.ocr.interfaces import IOcrEnabled
from imio.omnia.ocr.interfaces import IOcrText
from imio.omnia.ocr.storage import OcrRecord
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone.namedfile.interfaces import INamed
from plone.rfc822.interfaces import IPrimaryFieldInfo
from zope.annotation.interfaces import IAnnotations
from zope.component import adapter
from zope.i18nmessageid import Message
from zope.interface import implementer

import hashlib


PAGE_KEYS = ("index", "markdown", "header", "footer", "confidence")
HASH_CHUNK_SIZE = 1 << 20


def _number(value):
    """Return ``value`` as a float. Return None when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _page(position, page):
    """Return a page of the API as a plain dict with the known keys only."""
    return {
        "index": page.get("index", position),
        "markdown": page.get("markdown") or "",
        "header": page.get("header") or "",
        "footer": page.get("footer") or "",
        "confidence": _number(page.get("confidence")),
    }


@implementer(IOcrText)
@adapter(IOcrEnabled)
class OcrText:
    """Store the text versions in an annotation of the content.

    The annotation maps a field name to an ``OcrRecord``.
    """

    def __init__(self, context, fieldname=None):
        self.context = context
        self._fieldname = fieldname

    def for_field(self, fieldname):
        return self.__class__(self.context, fieldname=fieldname)

    @property
    def fieldname(self):
        if self._fieldname is None:
            try:
                self._fieldname = IPrimaryFieldInfo(self.context).fieldname
            except TypeError:
                # The content has no primary field.
                self._fieldname = ""
        return self._fieldname

    def fieldnames(self):
        names = [self.fieldname] if self.fieldname else []
        names.extend(name for name in self._records() or () if name not in names)
        return names

    # Storage

    def _records(self, create=False):
        annotations = IAnnotations(self.context)
        records = annotations.get(ANNOTATION_KEY)
        if records is None and create:
            records = annotations[ANNOTATION_KEY] = PersistentMapping()
        return records

    def _record(self, create=False):
        records = self._records(create=create)
        if records is None:
            return None
        record = records.get(self.fieldname)
        if record is None and create:
            record = records[self.fieldname] = OcrRecord()
        return record

    def _get(self, name):
        record = self._record()
        # A missing record gives the default value of the class.
        return getattr(OcrRecord if record is None else record, name)

    def exists(self):
        return self._record() is not None

    @property
    def status(self):
        return self._get("status")

    @property
    def pages(self):
        record = self._record()
        return [dict(page) for page in record.pages] if record is not None else []

    @property
    def page_count(self):
        return self._get("page_count")

    @property
    def confidence(self):
        return self._get("confidence")

    @property
    def model(self):
        return self._get("model")

    @property
    def generated(self):
        return self._get("generated")

    @property
    def source_hash(self):
        return self._get("source_hash")

    @property
    def error(self):
        return self._get("error")

    @property
    def attempts(self):
        return self._get("attempts")

    @property
    def hidden(self):
        return self._get("hidden")

    # File

    def get_file(self):
        if not self.fieldname:
            return None
        value = getattr(aq_base(self.context), self.fieldname, None)
        if not INamed.providedBy(value) or not value.getSize():
            return None
        return value

    def is_supported(self):
        value = self.get_file()
        return value is not None and value.contentType in SUPPORTED_CONTENT_TYPES

    def file_hash(self):
        value = self.get_file()
        if value is None:
            return None
        digest = hashlib.sha256()
        if hasattr(value, "open"):
            with value.open("r") as handle:
                for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
                    digest.update(chunk)
        else:
            digest.update(value.data)
        return digest.hexdigest()

    def is_stale(self):
        if not self.is_supported():
            return self.exists()
        return not self.exists() or self.source_hash != self.file_hash()

    def refresh(self):
        if not self.is_supported():
            if not self.exists():
                return False
            self.clear()
            return True
        source_hash = self.file_hash()
        if self.exists() and self.source_hash == source_hash:
            return False
        self.set_pending(source_hash)
        return True

    # Changes

    def _reset(self, record):
        """Drop the text and the data that describe it."""
        record.pages = PersistentList()
        record.page_count = 0
        record.confidence = None
        record.model = None
        record.generated = None
        record.error = None

    def _start(self, source_hash):
        """Return the record, without text, for the file with this digest."""
        if source_hash is None:
            source_hash = self.file_hash()
        record = self._record(create=True)
        if record.source_hash != source_hash:
            record.attempts = 0
        self._reset(record)
        record.source_hash = source_hash
        return record

    def set_pending(self, source_hash=None):
        record = self._start(source_hash)
        record.status = STATUS_PENDING

    def store_result(self, result, source_hash):
        pages = [_page(position, page) for position, page in enumerate(result.get("pages") or ())]
        scores = [page["confidence"] for page in pages if page["confidence"] is not None]
        record = self._start(source_hash)
        record.pages = PersistentList(pages)
        record.page_count = len(pages)
        record.confidence = min(scores) if scores else None
        record.model = result.get("model")
        record.generated = datetime.now(timezone.utc)
        record.attempts += 1
        record.status = STATUS_DONE

    def set_failed(self, error, source_hash=None):
        if not isinstance(error, Message):
            error = str(error)[:ERROR_MAX_LENGTH]
        record = self._start(source_hash)
        record.error = error
        record.attempts += 1
        record.status = STATUS_FAILED

    def set_hidden(self, hidden):
        record = self._record()
        if record is not None and record.hidden != bool(hidden):
            record.hidden = bool(hidden)

    def clear(self):
        records = self._records()
        if records is None or self.fieldname not in records:
            return
        del records[self.fieldname]
        if not records:
            del IAnnotations(self.context)[ANNOTATION_KEY]
