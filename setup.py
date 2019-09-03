#!/usr/bin/env python

from setuptools import setup


setup(
    name="aiosolr",
    version='0.0.6',
    description="Lightweight Python client for Apache Solr",

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
    download_url='https://github.com/bbelyeu/aiosolr/archive/0.0.6.zip',
    install_requires=["aiohttp"],
    keywords=['solr', 'asyncio', 'aiohttp', 'search'],
    license="MIT",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    platforms='any',
    py_modules=["aiosolr"],
    test_suite='tests',
    url="https://github.com/bbelyeu/aiosolr/",
)
