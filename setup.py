# -*- coding: utf-8 -*-
"""Installer for the imio.omnia.ocr package."""

from setuptools import find_packages
from setuptools import setup


long_description = "\n\n".join(
    [
        open("README.rst").read(),
        open("CONTRIBUTORS.rst").read(),
        open("CHANGES.rst").read(),
    ]
)


setup(
    name="imio.omnia.ocr",
    version="1.0.dev0",
    description="Machine-generated text version of PDF files for Plone, from iMio's Omnia OCR API",
    long_description=long_description,
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        "Framework :: Plone :: 6.1",
        "Framework :: Plone :: 6.2",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="Python Plone CMS AI Omnia OCR PDF accessibility",
    author="Antoine Duchêne",
    author_email="antoine.duchene@imio.be",
    url="https://github.com/IMIO/imio.omnia.ocr",
    project_urls={
        "PyPI": "https://pypi.org/project/imio.omnia.ocr/",
        "Source": "https://github.com/IMIO/imio.omnia.ocr",
        "Tracker": "https://github.com/IMIO/imio.omnia.ocr/issues",
    },
    license="GPL version 2",
    packages=find_packages("src", exclude=["ez_setup"]),
    namespace_packages=["imio", "imio.omnia"],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.12",
    install_requires=[
        "setuptools",
        # -*- Extra requirements: -*-
        "plone.api>=1.8.4",
        "plone.app.dexterity",
        "plone.app.registry",
        "plone.behavior",
        "plone.indexer",
        "plone.namedfile",
        "plone.protect",
        "plone.restapi",
        "plone.rfc822",
        "Products.PortalTransforms",
        "httpx2",
        "lxml",
        "lxml_html_clean",
        "Markdown",
        "imio.omnia.core>=1.4.dev0",
    ],
    extras_require={
        "test": [
            "plone.app.testing",
            "plone.testing>=5.0.0",
            "plone.app.contenttypes",
            "plone.app.robotframework[debug]",
        ],
    },
    entry_points="""
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = imio.omnia.ocr.locales.update:update_locale
    """,
)
