# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from imio.omnia.ocr import _
from imio.omnia.ocr.config import DEFAULT_RUNNER
from imio.omnia.ocr.config import MODE_HIDE
from imio.omnia.ocr.config import MODE_NOINDEX
from imio.omnia.ocr.config import MODE_WARN
from zope import schema
from zope.interface import Attribute
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


class IImioOmniaOcrLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IOcrEnabled(Interface):
    """Marker of the content that gets a text version of its PDF file.

    The ``imio.omnia.ocr`` behavior gives this marker.
    The behavior has no schema field.
    """


class IOcrText(Interface):
    """Text version of one file field of a content object.

    The adapter reads and writes an annotation.
    It does not send an event and it does not reindex the content.
    A read does not write to the database.
    """

    fieldname = Attribute("Name of the file field. The default is the primary field of the content.")
    status = Attribute("``pending``, ``done`` or ``failed``. None when the field has no record.")
    pages = Attribute(
        "List of the pages. Each page is a dict with the keys "
        "``index``, ``markdown``, ``header``, ``footer`` and ``confidence``."
    )
    page_count = Attribute("Number of pages.")
    confidence = Attribute("Lowest confidence of the pages, from 0 to 1. None when it is not known.")
    model = Attribute("Name of the OCR model.")
    generated = Attribute("Date of the generation, as a datetime in UTC. None when there is no text.")
    source_hash = Attribute("SHA-256 hex digest of the file that the record is about.")
    error = Attribute("Short message of the last failure. None when the status is not ``failed``.")
    attempts = Attribute("Number of OCR attempts for the current file.")
    hidden = Attribute("True when a manager hid the text version.")

    def for_field(fieldname):
        """Return the same adapter for a different file field."""

    def fieldnames():
        """Return the names of the fields to keep up to date.

        These are the primary field and each field that has a record.
        """

    def exists():
        """Return True when the field has a record."""

    def get_file():
        """Return the file of the field. Return None when the field is empty or is not a file."""

    def is_supported():
        """Return True when the field holds a file that the OCR accepts."""

    def file_hash():
        """Return the SHA-256 hex digest of the file. Return None when there is no file."""

    def is_stale():
        """Return True when the record does not agree with the file.

        This is the case when the file changed after the generation,
        when a supported file has no record,
        and when a record has no supported file.
        """

    def refresh():
        """Make the record agree with the file. Return True when the record changed.

        A new or changed file drops the old text and sets the status to ``pending``.
        A removed or unsupported file removes the record.
        """

    def set_pending(source_hash=None):
        """Drop the text and set the status to ``pending``.

        ``source_hash`` is the digest of the file to convert.
        The default is the digest of the current file.
        """

    def store_result(result, source_hash):
        """Store the result of the OCR and set the status to ``done``.

        ``result`` is the dict that ``IOmniaCoreAPIService.ocr_markdown`` returns.
        ``source_hash`` is the digest of the file that the text came from.
        """

    def set_failed(error, source_hash=None):
        """Drop the text, store the error message and set the status to ``failed``.

        ``source_hash`` is the digest of the file that the OCR did not convert.
        The default is the digest of the current file.
        """

    def set_hidden(hidden):
        """Hide or show the text version. A field without a record does not change."""

    def clear():
        """Remove the record of the field."""


class IOcrRunner(Interface):
    """Named utility that runs the OCR of a file field.

    The ``runner`` setting holds the name of the active runner.
    The ``sync`` runner does the work in the current request.
    """

    title = Attribute("Title of the runner in the control panel.")

    def run(obj, fieldname=None):
        """Run the OCR of the field and return the status that results.

        A runner that works later returns ``pending``.
        """


class IOcrInfoView(Interface):
    """Helper view for the templates of a host package."""

    def for_field(fieldname):
        """Bind the view to a different file field and return the view."""

    def status():
        """Return ``pending``, ``done``, ``failed`` or None."""

    def available():
        """Return True when the current user can see the text now."""

    def low_confidence():
        """Return True when the confidence of the text is below the threshold."""

    def page_count():
        """Return the number of pages of the text."""

    def html(max_pages=None, heading_level=None):
        """Return the sanitised HTML of the text.

        ``max_pages`` limits the number of pages. The default is the ``inline_max_pages`` setting.
        ``heading_level`` is the level of the highest heading. The default is 3.
        The result is empty when the text is not available.
        """

    def truncated(max_pages=None):
        """Return True when ``html`` does not give all the pages."""

    def text_url():
        """Return the URL of the bare HTML fragment with the full text."""

    def full_text_url():
        """Return the URL of the page with the full text."""

    def can_manage():
        """Return True when the current user can manage the text version."""

    def disclaimer():
        """Return the translated disclaimer. It is stronger when the confidence is low."""


LOW_CONFIDENCE_MODES = SimpleVocabulary(
    [
        SimpleTerm(MODE_WARN, MODE_WARN, _("Show the text with a stronger warning")),
        SimpleTerm(MODE_HIDE, MODE_HIDE, _("Do not show the text and keep it out of the search")),
        SimpleTerm(
            MODE_NOINDEX, MODE_NOINDEX, _("Show the text with a stronger warning and keep it out of the search")
        ),
    ]
)


class IOmniaOcrSettings(Interface):
    enabled = schema.Bool(
        title=_("Enabled"),
        description=_(
            "Generate the text version of PDF files with optical character recognition (OCR). "
            "When this is off, no file is sent to the OCR. The existing text versions stay visible."
        ),
        required=False,
        default=True,
    )

    runner = schema.Choice(
        title=_("Runner"),
        description=_("How the generation runs."),
        vocabulary="imio.omnia.ocr.runners",
        required=True,
        default=DEFAULT_RUNNER,
    )

    timeout = schema.Int(
        title=_("OCR timeout (seconds)"),
        description=_("Maximum time to wait for the answer of the Omnia API."),
        required=True,
        # The Omnia API stops an OCR call after 300 seconds. The margin lets the client receive that answer.
        default=330,
        min=1,
    )

    extract_header_footer = schema.Bool(
        title=_("Separate the page headers and footers"),
        description=_("The page headers and footers are stored but they are not part of the text version."),
        required=False,
        default=True,
    )

    html_tables = schema.Bool(
        title=_("Tables in HTML"),
        description=_("Ask for HTML tables. They keep the merged cells. When this is off, tables are in Markdown."),
        required=False,
        default=True,
    )

    image_descriptions = schema.Bool(
        title=_("Describe the images"),
        description=_("Ask for a short description of each image of the document."),
        required=False,
        default=False,
    )

    confidence = schema.Bool(
        title=_("Confidence scores"),
        description=_("Ask for a confidence score for each page."),
        required=False,
        default=True,
    )

    low_confidence_threshold = schema.Float(
        title=_("Low confidence threshold"),
        description=_("A text version with a confidence score below this value has a low confidence. From 0 to 1."),
        required=True,
        default=0.7,
        min=0.0,
        max=1.0,
    )

    low_confidence_mode = schema.Choice(
        title=_("Text versions with a low confidence"),
        description=_("After a change of this setting, reindex the content to update the search."),
        vocabulary=LOW_CONFIDENCE_MODES,
        required=True,
        default=MODE_WARN,
    )

    inline_max_pages = schema.Int(
        title=_("Pages shown on the content page"),
        description=_("Maximum number of pages of the text version shown on the page of the content."),
        required=True,
        default=50,
        min=1,
    )
