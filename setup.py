#!/usr/bin/env python
"""Lightweight Python client for Apache Solr."""
import sys

from setuptools import setup

if sys.version_info < (3, 6):
    sys.exit("Sorry, Python < 3.6 is not supported")

__version__ = "3.4.7"

setup(
    name="aiosolr",
    version=__version__,
    description=__doc__,
    author="Brad Belyeu",
    author_email="bradley.belyeu@life.church",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Programming Language :: Python :: 3",
    ],
    download_url=f"https://github.com/bbelyeu/aiosolr/archive/{__version__}.zip",
    install_requires=["aiohttp", "bleach"],
    keywords=["solr", "asyncio", "aiohttp", "search"],
    license="MIT",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    platforms="any",
    py_modules=["aiosolr"],
    python_requires=">3.6.0",
    test_suite="tests",
    url="https://github.com/bbelyeu/aiosolr/",
)
