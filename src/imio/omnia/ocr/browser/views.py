# -*- coding: utf-8 -*-
from html import escape
from imio.omnia.ocr import _
from imio.omnia.ocr import api
from imio.omnia.ocr.config import STATUS_DONE
from imio.omnia.ocr.config import STATUS_FAILED
from imio.omnia.ocr.config import STATUS_PENDING
from imio.omnia.ocr.interfaces import IOcrInfoView
from plone.protect import CheckAuthenticator
from plone.protect.authenticator import createToken
from plone.transformchain.interfaces import DISABLE_TRANSFORM_REQUEST_KEY
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from urllib.parse import urlencode
from zExceptions import Forbidden
from zExceptions import NotFound
from zope.component import getMultiAdapter
from zope.i18n import translate
from zope.interface import implementer

import json


class OcrBaseView(BrowserView):
    """Shared code of the views. A view works on one file field of the content."""

    # None gives the primary field.
    fieldname = None

    def for_field(self, fieldname):
        self.fieldname = fieldname or None
        return self

    @property
    def text(self):
        return api.get_text(self.context, self.fieldname)

    def _translate(self, message):
        return translate(message, context=self.request)

    def _url(self, name, **query):
        if self.fieldname:
            query["fieldname"] = self.fieldname
        url = f"{self.context.absolute_url()}/@@{name}"
        return f"{url}?{urlencode(query)}" if query else url

    def status(self):
        return self.text.status

    def available(self):
        return api.is_displayable(self.text)

    def low_confidence(self):
        return api.is_low_confidence(self.text)

    def page_count(self):
        return self.text.page_count

    def can_manage(self):
        return api.can_manage(self.context)

    def text_url(self):
        return self._url("ocr-text-fragment")

    def full_text_url(self):
        return self._url("ocr-text")

    def disclaimer(self):
        if self.low_confidence():
            return self._translate(
                _(
                    "Warning: the automatic recognition of this document is of low quality. "
                    "This text version probably contains errors. Only the PDF file is authoritative."
                )
            )
        return self._translate(
            _(
                "This text version was generated automatically from the PDF file. "
                "It can contain errors. Only the PDF file is authoritative."
            )
        )

    def _max_pages(self, max_pages=None):
        return api.get_setting("inline_max_pages") if max_pages is None else max_pages

    def html(self, max_pages=None, heading_level=None):
        if not self.available():
            return ""
        return api.render_html(self.text, self.request, self._max_pages(max_pages), heading_level)

    def truncated(self, max_pages=None):
        return self.available() and self.page_count() > self._max_pages(max_pages)

    def full_html(self, heading_level=None):
        """Return the disclaimer and all the pages. The result is empty when the text is not available."""
        if not self.available():
            return ""
        level = "warning" if self.low_confidence() else "info"
        disclaimer = escape(self.disclaimer(), quote=False)
        body = api.render_html(self.text, self.request, None, heading_level)
        return f'<p class="ocr-disclaimer alert alert-{level}" role="note">{disclaimer}</p>\n{body}'


@implementer(IOcrInfoView)
class OcrInfoView(OcrBaseView):
    """Helper view ``@@ocr-info`` for the templates of a host package."""


class OcrRequestView(OcrBaseView):
    """A view that takes the name of the file field from the ``fieldname`` parameter of the request."""

    def __init__(self, context, request):
        super().__init__(context, request)
        self.fieldname = request.form.get("fieldname") or None


class OcrTextView(OcrRequestView):
    """Page ``@@ocr-text`` with the full text version."""

    index = ViewPageTemplateFile("templates/ocr_text.pt")

    def __call__(self):
        if not self.available():
            raise NotFound(self.context, "ocr-text", self.request)
        if not api.is_indexable(self.text):
            self.request.response.setHeader("X-Robots-Tag", "noindex")
        return self.index()

    def title(self):
        return self._translate(_('Text version of "${title}"', mapping={"title": self.context.Title()}))

    def back_url(self):
        state = getMultiAdapter((self.context, self.request), name="plone_context_state")
        return state.view_url()

    def body(self):
        # The title of the page is the h1. The text starts at h2.
        return self.full_html(heading_level=2)


class OcrTextFragmentView(OcrRequestView):
    """Bare HTML fragment ``@@ocr-text-fragment`` with the full text version.

    The ``heading_level`` parameter gives the level of the highest heading. The default is 3.
    """

    def __call__(self):
        response = self.request.response
        response.setHeader("Content-Type", "text/html; charset=utf-8")
        # The output transforms of Plone must not wrap the fragment in a full page.
        response.setHeader("X-Theme-Disabled", "1")
        self.request.environ[DISABLE_TRANSFORM_REQUEST_KEY] = True
        if not self.available():
            response.setStatus(404)
            return ""
        if not api.is_indexable(self.text):
            response.setHeader("X-Robots-Tag", "noindex")
        try:
            heading_level = max(1, min(6, int(self.request.form.get("heading_level"))))
        except (TypeError, ValueError):
            heading_level = None
        return f'<div class="ocr-text">\n{self.full_html(heading_level=heading_level)}\n</div>'


class OcrManagePanelView(OcrBaseView):
    """Snippet ``@@ocr-manage-panel`` with the status and the buttons, for the managers."""

    index = ViewPageTemplateFile("templates/ocr_manage_panel.pt")

    def __call__(self):
        if not self.visible():
            return ""
        return self.index()

    def visible(self):
        """Return True when the user can manage and the content has a PDF file or a record."""
        text = self.text
        return text is not None and self.can_manage() and (text.is_supported() or text.exists())

    def enabled(self):
        return bool(api.get_setting("enabled"))

    def can_generate(self):
        return self.enabled() and self.text.is_supported()

    def auto_start(self):
        """Return True when the script of the page must start the generation."""
        return self.status() == STATUS_PENDING and self.can_generate()

    def is_done(self):
        return self.status() == STATUS_DONE

    def hidden(self):
        return self.text.hidden

    def process_url(self):
        return self._url("ocr-process")

    def manage_url(self):
        return self._url("ocr-manage")

    def token(self):
        return createToken()

    def working_label(self):
        return self._translate(_("The text version is being generated. This can take several minutes."))

    def status_label(self):
        text = self.text
        status = text.status
        if status == STATUS_PENDING:
            if not self.enabled():
                message = _("The text version is not generated. Generation is disabled.")
            else:
                message = _("The text version is waiting to be generated.")
        elif status == STATUS_FAILED:
            message = _(
                "The generation of the text version failed: ${error}",
                mapping={"error": self._translate(text.error or "")},
            )
        elif status == STATUS_DONE:
            toLocalizedTime = self.context.restrictedTraverse("@@plone").toLocalizedTime
            message = _(
                "Text version generated on ${date}. Pages: ${pages}.",
                mapping={
                    "date": toLocalizedTime(text.generated.astimezone(), long_format=True),
                    "pages": str(text.page_count),
                },
            )
        else:
            message = _("This document has no text version.")
        return self._translate(message)

    def generate_label(self):
        status = self.status()
        if status is None:
            message = _("Generate the text version")
        elif status == STATUS_FAILED:
            message = _("Try again")
        else:
            message = _("Generate again")
        return self._translate(message)


class OcrActionView(OcrRequestView):
    """Shared code of the views that change the text version. They accept POST requests only."""

    def _json(self, data, status=200):
        response = self.request.response
        response.setStatus(status)
        response.setHeader("Content-Type", "application/json")
        return json.dumps(data)

    def _check(self):
        """Return an error answer when the request is not a POST with a valid CSRF token."""
        if self.request.method != "POST":
            self.request.response.setHeader("Allow", "POST")
            return self._json({"error": "Method not allowed"}, 405)
        try:
            CheckAuthenticator(self.request)
        except Forbidden:
            return self._json({"error": "Invalid CSRF token"}, 403)
        if self.text is None or not (self.text.is_supported() or self.text.exists()):
            return self._json({"error": "No file to convert"}, 404)
        return None

    def _state(self):
        """Return the state of the text version, for the script of the page."""
        text = self.text
        panel = getMultiAdapter((self.context, self.request), name="ocr-manage-panel").for_field(self.fieldname)
        return {
            "status": text.status,
            "fieldname": text.fieldname,
            "hidden": text.hidden,
            "page_count": text.page_count,
            "low_confidence": api.is_low_confidence(text),
            "error": self._translate(text.error) if text.error else None,
            "panel": panel(),
        }


class OcrProcessView(OcrActionView):
    """Endpoint ``@@ocr-process``. It runs the active runner and answers with JSON."""

    def __call__(self):
        error = self._check()
        if error is not None:
            return error
        api.get_runner().run(self.context, fieldname=self.fieldname)
        return self._json(self._state())


class OcrManageView(OcrActionView):
    """Endpoint ``@@ocr-manage``. The ``action`` parameter is ``regenerate``, ``hide`` or ``show``.

    The answer is JSON when the request accepts JSON.
    If not, the answer is a redirect to the content.
    """

    def __call__(self):
        error = self._check()
        if error is not None:
            return error
        action = self.request.form.get("action")
        handler = {"regenerate": self.regenerate, "hide": self.hide, "show": self.show}.get(action)
        if handler is None:
            return self._json({"error": "Unknown action"}, 400)
        message = handler()
        api.reindex(self.context)
        if "application/json" in (self.request.getHeader("Accept") or ""):
            return self._json(self._state())
        IStatusMessage(self.request).addStatusMessage(message, type="info")
        state = getMultiAdapter((self.context, self.request), name="plone_context_state")
        return self.request.response.redirect(state.view_url())

    def regenerate(self):
        if not api.get_setting("enabled"):
            return _("Generation is disabled.")
        text = self.text
        if text.source_hash:
            api.forget_result(text.source_hash)
        # The script of the page starts the generation when it sees the pending status.
        if not text.refresh():
            text.set_pending()
        return _("The text version is waiting to be generated.")

    def hide(self):
        self.text.set_hidden(True)
        return _("The text version is hidden.")

    def show(self):
        self.text.set_hidden(False)
        return _("The text version is visible.")
