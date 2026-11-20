# -*- coding: utf-8 -*-
from imio.omnia.core.testing import IMIO_OMNIA_CORE_FIXTURE
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import imio.omnia.ocr


class ImioOmniaOcrLayer(PloneSandboxLayer):
    defaultBases = (IMIO_OMNIA_CORE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=imio.omnia.ocr)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "imio.omnia.ocr:default")


IMIO_OMNIA_OCR_FIXTURE = ImioOmniaOcrLayer()


IMIO_OMNIA_OCR_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_OMNIA_OCR_FIXTURE,),
    name="ImioOmniaOcrLayer:IntegrationTesting",
)


IMIO_OMNIA_OCR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_OMNIA_OCR_FIXTURE,),
    name="ImioOmniaOcrLayer:FunctionalTesting",
)


IMIO_OMNIA_OCR_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        IMIO_OMNIA_OCR_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE,
    ),
    name="ImioOmniaOcrLayer:AcceptanceTesting",
)
