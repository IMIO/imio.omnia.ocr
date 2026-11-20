# -*- coding: utf-8 -*-
"""Functions for the views of the package and for the code of a host package."""

from Acquisition import aq_get
from contextlib import contextmanager
from imio.omnia.core.interfaces import IOmniaCoreAPIService
from imio.omnia.ocr import _
from imio.omnia.ocr.cache import BoundedCache
from imio.omnia.ocr.config import DEFAULT_HEADING_LEVEL
from imio.omnia.ocr.config import DEFAULT_RUNNER
from imio.omnia.ocr.config import MANAGE_PERMISSION
from imio.omnia.ocr.config import MODE_HIDE
from imio.omnia.ocr.config import MODE_NOINDEX
from imio.omnia.ocr.config import REINDEX_IDXS
from imio.omnia.ocr.config import SETTINGS_PREFIX
from imio.omnia.ocr.config import STATUS_DONE
from imio.omnia.ocr.config import STATUS_PENDING
from imio.omnia.ocr.interfaces import IOcrRunner
from imio.omnia.ocr.interfaces import IOcrText
from imio.omnia.ocr.interfaces import IOmniaOcrSettings
from imio.omnia.ocr.render import convert_pages
from imio.omnia.ocr.render import plain_text
from imio.omnia.ocr.render import render_pages
from plone import api
from plone.registry.interfaces import IRegistry
from Testing.makerequest import makerequest
from transaction.interfaces import TransientError
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.component import queryUtility
from zope.globalrequest import getRequest
from zope.globalrequest import setRequest
from zope.i18n import translate
from zope.publisher.interfaces.browser import IBrowserRequest

import httpx2
import logging


logger = logging.getLogger(__name__)

# Results of the last OCR calls of this process.
# A replay of a request after a write conflict takes its result here.
_replay_cache = BoundedCache(8)

# HTML of the last rendered text versions.
_render_cache = BoundedCache(32)


def get_setting(name):
    """Return the value of a field of ``IOmniaOcrSettings``.

    A missing or empty record gives the default value of the field.
    """
    default = IOmniaOcrSettings[name].default
    registry = queryUtility(IRegistry)
    if registry is None:
        return default
    value = registry.get(f"{SETTINGS_PREFIX}.{name}", default)
    return default if value is None else value


def get_text(obj, fieldname=None):
    """Return the ``IOcrText`` adapter of a file field of ``obj``.

    The default field is the primary field.
    Return None when ``obj`` does not have the behavior.
    """
    text = IOcrText(obj, None)
    if text is not None and fieldname:
        text = text.for_field(fieldname)
    return text


def get_runner():
    """Return the active ``IOcrRunner`` utility."""
    runner = queryUtility(IOcrRunner, name=get_setting("runner") or DEFAULT_RUNNER)
    if runner is None:
        runner = getUtility(IOcrRunner, name=DEFAULT_RUNNER)
    return runner


def can_manage(obj):
    """Return True when the current user can manage the text versions of ``obj``."""
    return bool(api.user.has_permission(MANAGE_PERMISSION, obj=obj))


def reindex(obj):
    """Update the catalog indexes that depend on the text version.

    This sends no event and it does not change the modification date.
    """
    obj.reindexObject(idxs=list(REINDEX_IDXS))


# Rules for the display and for the search


def is_low_confidence(text):
    """Return True when the confidence of the text is below the threshold."""
    confidence = text.confidence
    return confidence is not None and confidence < get_setting("low_confidence_threshold")


def is_displayable(text):
    """Return True when the text can be shown to a user who can view the content."""
    if text is None or text.status != STATUS_DONE or text.hidden:
        return False
    return not (get_setting("low_confidence_mode") == MODE_HIDE and is_low_confidence(text))


def is_indexable(text):
    """Return True when the text can be in the search index."""
    if not is_displayable(text):
        return False
    return not (get_setting("low_confidence_mode") == MODE_NOINDEX and is_low_confidence(text))


def searchable_text(obj, fieldname=None):
    """Return the plain text of the text version, for a ``SearchableText`` indexer.

    The result is empty when the text is hidden, when it is not generated,
    and when the low confidence mode keeps it out of the search.
    """
    text = get_text(obj, fieldname)
    if not is_indexable(text):
        return ""
    return plain_text(text.pages)


def render_html(text, request=None, max_pages=None, heading_level=None):
    """Return the sanitised HTML of the first ``max_pages`` pages of a text version.

    ``max_pages`` None gives all the pages.
    The labels are in the language of ``request``.
    This function does not look at the status or at the permissions.
    """
    request = request or getRequest()
    heading_level = heading_level or DEFAULT_HEADING_LEVEL
    image_label = translate(_("Image: ${description}", mapping={"description": "{description}"}), context=request)
    page_label = translate(_("Page ${number}", mapping={"number": "{number}"}), context=request)
    key = (text.source_hash, text.generated, max_pages, heading_level, image_label, page_label)
    html = _render_cache.get(key)
    if html is None:
        pages = text.pages if max_pages is None else text.pages[:max_pages]
        html = render_pages(pages, heading_level=heading_level, image_label=image_label, page_label=page_label)
        _render_cache.set(key, html)
    return html


# Generation


def _ocr_options():
    """Return the options of the OCR call, from the settings."""
    return {
        "extract_header_footer": bool(get_setting("extract_header_footer")),
        "table_format": "html" if get_setting("html_tables") else "markdown",
        "image_descriptions": bool(get_setting("image_descriptions")),
        "confidence": bool(get_setting("confidence")),
    }


@contextmanager
def _api_request(obj, request=None):
    """Give a request for the API call.

    A script has no request. The API client and its audit log need one.
    """
    current = getRequest()
    if request is None:
        request = current
    if request is None:
        request = aq_get(obj, "REQUEST", None)
    if not IBrowserRequest.providedBy(request):
        request = makerequest(obj.getPhysicalRoot()).REQUEST
    if current is None:
        setRequest(request)
    try:
        yield request
    finally:
        if current is None:
            setRequest(None)


def _call_ocr(obj, text, source_hash, use_cache, request):
    """Return the result of the OCR API for the file of ``text``."""
    options = _ocr_options()
    key = (source_hash, tuple(sorted(options.items())))
    # A second thread with the same file waits here and then takes the cached result.
    with _replay_cache.locked(key):
        result = _replay_cache.get(key) if use_cache else None
        if result is None:
            value = text.get_file()
            with _api_request(obj, request) as request:
                service = getMultiAdapter((obj, request), IOmniaCoreAPIService)
                result = service.ocr_markdown(
                    file=(value.filename or "document.pdf", value.data, value.contentType),
                    pages=None,
                    timeout=get_setting("timeout"),
                    **options,
                )
            _replay_cache.set(key, result)
    return result


class EmptyResult(Exception):
    """The API answered without an error, but its result has nothing to show."""


def _error_message(exc):
    """Return a short message for the managers. The log has the details."""
    if isinstance(exc, EmptyResult):
        return _("The OCR found no text in the document.")
    if isinstance(exc, httpx2.TimeoutException):
        return _("The Omnia API did not answer in time.")
    if isinstance(exc, httpx2.HTTPStatusError):
        return _(
            "The Omnia API answered with HTTP status ${status}.",
            mapping={"status": str(exc.response.status_code)},
        )
    return _("The generation stopped on an error (${error}).", mapping={"error": type(exc).__name__})


def forget_result(source_hash):
    """Remove the cached OCR results of a file, so that the next call asks the API again."""
    _replay_cache.discard(lambda key: key[0] == source_hash)


def process(obj, fieldname=None, force=False, request=None):
    """Generate the text version of a file field of ``obj`` and return the status.

    The function calls the Omnia OCR API. It does not return before the answer.
    It stores the result or the failure, then it reindexes ``SearchableText`` and ``ocr_status``.
    It sends no event and it does not commit the transaction.

    Without ``force``, the function calls the API only when the text of the current file is missing or ``pending``.
    A failure stays a failure. With ``force``, the function calls the API again for a file that has a text
    or a failure.
    The function does not call the API when the ``enabled`` setting is off and when the file is not a PDF.
    ``request`` is optional. A script can call the function without a request.
    """
    text = get_text(obj, fieldname)
    if text is None:
        return None
    if not text.is_supported():
        # The record of a file that is not there any more goes away.
        if text.refresh():
            reindex(obj)
        return text.status
    if not get_setting("enabled"):
        return text.status
    source_hash = text.file_hash()
    up_to_date = text.exists() and text.source_hash == source_hash
    if up_to_date and text.status != STATUS_PENDING and not force:
        return text.status
    # A replay of the request must not call the API again, even with ``force``.
    is_replay = bool(getattr(request or getRequest(), "retry_count", 0))
    try:
        result = _call_ocr(obj, text, source_hash, use_cache=is_replay or not force, request=request)
        if not any(convert_pages(result.get("pages") or ())):
            # The API gives empty pages for a damaged file and for a file without text.
            raise EmptyResult()
        text.store_result(result, source_hash)
    except TransientError:
        # The publisher replays the request.
        raise
    except Exception as exc:
        logger.warning("OCR of %s (%s) failed", "/".join(obj.getPhysicalPath()), text.fieldname, exc_info=True)
        text.set_failed(_error_message(exc), source_hash)
    reindex(obj)
    return text.status
