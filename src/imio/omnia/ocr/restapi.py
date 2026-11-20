# -*- coding: utf-8 -*-
from imio.omnia.ocr import api
from plone.restapi.services import Service


class OcrTextGet(Service):
    """Give the text version of the primary file field as JSON."""

    def reply(self):
        text = api.get_text(self.context)
        available = api.is_displayable(text)
        pages = text.pages if available else []
        return {
            "@id": f"{self.context.absolute_url()}/@ocr-text",
            "status": text.status,
            "available": available,
            "page_count": len(pages),
            "confidence": text.confidence if available else None,
            "pages": [
                {"index": page["index"], "markdown": page["markdown"], "confidence": page["confidence"]}
                for page in pages
            ],
        }
