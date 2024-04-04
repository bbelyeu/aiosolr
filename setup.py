#!/usr/bin/env python

"""Lightweight AsyncIO Python client for Apache Solr."""

# pylint: disable=consider-using-with

import sys

from setuptools import setup

import aiosolr

if sys.version_info < (3, 7):
    sys.exit("Sorry, Python < 3.7 is not supported")

setup(
    name="aiosolr",
    version=aiosolr.__version__,
    description=__doc__,
    author="Brad Belyeu",
    author_email="bradley.belyeu@youversion.com",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Programming Language :: Python :: 3",
    ],
    download_url=f"https://github.com/bbelyeu/aiosolr/archive/{aiosolr.__version__}.zip",
    install_requires=["aiohttp", "bleach"],
    keywords=["solr", "asyncio", "aiohttp", "search"],
    license="MIT",
    long_description=open("README.md", encoding="utf8", mode="r").read(),
    long_description_content_type="text/markdown",
    platforms="any",
    py_modules=["aiosolr"],
    python_requires=">=3.7.0",
    test_suite="tests",
    url="https://github.com/bbelyeu/aiosolr/",
)
