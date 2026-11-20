# -*- coding: utf-8 -*-
"""Turn the Markdown of the OCR into safe HTML and into plain text."""

from html import escape
from html import unescape
from imio.omnia.ocr.config import DEFAULT_HEADING_LEVEL
from lxml import html as lxml_html
from lxml_html_clean import Cleaner
from plone import api

import markdown
import re


MARKDOWN_EXTENSIONS = ("tables", "sane_lists")
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

# Tags of a text document. The OCR copies the HTML code that a document shows.
# A tag that is not in this list loses its markup and its text stays.
ALLOWED_TAGS = frozenset(
    HEADING_TAGS
    + ("p", "br", "hr", "blockquote", "pre", "code", "ul", "ol", "li", "dl", "dt", "dd")
    + ("table", "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "th", "td")
    + ("a", "strong", "em", "b", "i", "u", "s", "del", "ins", "sub", "sup", "img")
)
ALLOWED_ATTRIBUTES = frozenset(("href", "src", "alt", "colspan", "rowspan", "scope", "headers", "start"))
STRICT_CLEANER = Cleaner(
    allow_tags=ALLOWED_TAGS,
    remove_unknown_tags=False,
    safe_attrs_only=True,
    safe_attrs=ALLOWED_ATTRIBUTES,
    style=True,
)
# A link stays a link only when its target starts with one of these.
LINK_PREFIXES = ("http://", "https://", "mailto:")

# Alternative text that is a file name, for example "img-0.jpeg".
FILE_NAME_RE = re.compile(r"^[\w.\-]+\.[A-Za-z0-9]{2,5}$")

# Text between the brackets of a Markdown link or image. A backslash escapes a bracket.
MD_LABEL = r"\[((?:\\.|[^\]\\])*)\]"
# Target of a Markdown link or image. It can contain one level of parentheses.
MD_TARGET = r"\((?:[^()]|\([^()]*\))*\)"
MD_IMAGE_RE = re.compile("!" + MD_LABEL + MD_TARGET)
MD_LINK_RE = re.compile(MD_LABEL + MD_TARGET)
HTML_CODE_RE = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
# A tag starts with a letter. The text "a < b" is not a tag.
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
MD_RULE_RE = re.compile(r"^[\s|:\-=*_]+$", re.MULTILINE)
MD_MARK_RE = re.compile(r"[*`|~]+|_{2,}")
SPACES_RE = re.compile(r"\s+")


def _restrict(tree):
    """Keep only the tags and the attributes of a text document.

    The HTML filter of Plone is for the text of an editor. It accepts frames and styles.
    The text of the OCR gets this stricter filter first.
    """
    STRICT_CLEANER(tree)
    for link in list(tree.iter("a")):
        target = (link.get("href") or "").strip()
        if target.lower().startswith(LINK_PREFIXES):
            continue
        if FILE_NAME_RE.match(target) and link.text_content().strip() == target:
            # This is the mark of a table that the API did not put in the text, for example "tbl-0.html".
            link.drop_tree()
        else:
            link.drop_tag()


def _trees(pages):
    """Return one lxml tree for each page. The root of a tree is a ``div``."""
    converter = markdown.Markdown(extensions=list(MARKDOWN_EXTENSIONS))
    trees = []
    for page in pages:
        source = converter.reset().convert(page.get("markdown") or "")
        if not source.strip():
            source = ""
        tree = lxml_html.fragment_fromstring(source, create_parent="div")
        _restrict(tree)
        trees.append(tree)
    return trees


def _shift_headings(trees, heading_level):
    """Give ``heading_level`` to the highest heading and keep the steps between the levels."""
    headings = [element for tree in trees for element in tree.iter(*HEADING_TAGS)]
    if not headings:
        return
    offset = heading_level - min(int(element.tag[1]) for element in headings)
    for element in headings:
        level = int(element.tag[1]) + offset
        element.tag = "h%d" % max(1, min(6, level))


def _replace_images(tree, image_label):
    """Replace an image with its description. Remove an image that has no description.

    ``image_label`` is a format string with the ``{description}`` field.
    """
    for image in list(tree.iter("img")):
        description = (image.get("alt") or "").strip()
        parent = image.getparent()
        if not description or description == image.get("src") or FILE_NAME_RE.match(description):
            image.drop_tree()
        else:
            text = lxml_html.Element("span")
            text.set("class", "ocr-image-description")
            text.text = image_label.format(description=description)
            text.tail = image.tail
            parent.replace(image, text)
        if parent.tag == "p" and not len(parent) and not (parent.text or "").strip():
            parent.drop_tree()


def _inner_html(tree):
    parts = [escape(tree.text or "", quote=False)]
    parts.extend(lxml_html.tostring(child, encoding="unicode") for child in tree)
    return "".join(parts).strip()


def sanitize(source):
    """Return ``source`` after the HTML filter of Plone.

    The text comes from an external API, so it always goes through a filter.
    When the filter of Plone is off, the default lxml cleaner does the work.
    """
    if not source.strip():
        return ""
    if api.portal.get_registry_record("plone.disable_filtering", default=False):
        tree = lxml_html.fragment_fromstring(source, create_parent="div")
        Cleaner()(tree)
        return _inner_html(tree)
    transforms = api.portal.get_tool("portal_transforms")
    data = transforms.convertTo("text/x-html-safe", source, mimetype="text/html")
    if data is None:
        return ""
    return str(data.getData()).strip()


def convert_pages(pages, heading_level=DEFAULT_HEADING_LEVEL, image_label="Image: {description}"):
    """Return the HTML body of each page, in the order of ``pages``.

    The result has the tags of ``ALLOWED_TAGS`` only.
    It did NOT go through the HTML filter of Plone.
    ``heading_level`` is the level that the highest heading of the pages gets.
    """
    trees = _trees(pages)
    _shift_headings(trees, heading_level)
    bodies = []
    for tree in trees:
        _replace_images(tree, image_label)
        bodies.append(_inner_html(tree))
    return bodies


def render_pages(
    pages,
    heading_level=DEFAULT_HEADING_LEVEL,
    image_label="Image: {description}",
    page_label="Page {number}",
    sanitizer=sanitize,
):
    """Return the sanitised HTML of ``pages``.

    Each page is a ``section`` with a label for screen readers.
    A page without content gives no section.
    The page headers and footers are not in the result.
    ``image_label`` and ``page_label`` are format strings.
    """
    sections = []
    for number, body in enumerate(convert_pages(pages, heading_level, image_label), start=1):
        body = sanitizer(body)
        if not body:
            continue
        label = escape(page_label.format(number=number), quote=True)
        sections.append(f'<section class="ocr-page" data-ocr-page="{number}" aria-label="{label}">\n{body}\n</section>')
    return "\n".join(sections)


def plain_text(pages):
    """Return the body text of ``pages`` without markup, for a text index.

    Images, page headers and page footers are not in the result.
    """
    parts = []
    for page in pages:
        text = page.get("markdown") or ""
        text = MD_IMAGE_RE.sub(" ", text)
        text = MD_LINK_RE.sub(r"\1", text)
        text = HTML_CODE_RE.sub(" ", text)
        text = unescape(HTML_TAG_RE.sub(" ", text))
        text = MD_HEADING_RE.sub("", text)
        text = MD_RULE_RE.sub(" ", text)
        text = MD_MARK_RE.sub(" ", text)
        parts.append(text)
    return SPACES_RE.sub(" ", " ".join(parts)).strip()
