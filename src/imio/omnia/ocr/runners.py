# -*- coding: utf-8 -*-
from imio.omnia.ocr import _
from imio.omnia.ocr.api import process
from imio.omnia.ocr.interfaces import IOcrRunner
from zope.component import getUtilitiesFor
from zope.interface import implementer
from zope.interface import provider
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


@implementer(IOcrRunner)
class SyncRunner:
    """Do the OCR in the current request."""

    title = _("In the request (synchronous)")

    def run(self, obj, fieldname=None):
        return process(obj, fieldname=fieldname)


@provider(IVocabularyFactory)
def runners_vocabulary(context):
    """Vocabulary of the registered ``IOcrRunner`` utilities."""
    terms = [
        SimpleTerm(name, name, getattr(runner, "title", None) or name)
        for name, runner in sorted(getUtilitiesFor(IOcrRunner))
    ]
    return SimpleVocabulary(terms)
