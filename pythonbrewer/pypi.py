# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import re
import hashlib

import requests
import html5lib

from pythonbrewer.errors import *

import logging
logger = logging.getLogger(__name__)

__all__ = [
    "fetch_pypi_package_files",
    "get_pypi_sha256"
]


def get_html_namespace(tree):
    p = re.compile(r"\{(?P<namespace>[^\}]+)\}.+")
    m = p.match(tree[0].tag)
    return m.group('namespace') if m is not None else None


def html_findall(tree, namespace, xpath):
    return tree.findall(xpath.format(ns="{%s}" % namespace))


def fetch_pypi_package_files(package_name, package_version, required_suffix=None):
    """Attempts to fetch a list of files for the given package/version from PyPI.

    Args:
        package_name: The name of the package for which to fetch files.
        package_version: The version of the package for which to fetch files.
        required_suffix: The required suffix for the package files we want. Set to None if you want all files for
            the particular version.

    Returns:
        A list of URLs to different distributions for the specified package.
    """
    response = requests.get("https://pypi.python.org/simple/%s" % package_name)
    if response.status_code >= 300:
        raise PackageNotFoundError(package_name)

    expected_prefix = ("%s-%s" % (package_name, package_version)).lower()
    expected_prefix_underscore = ("%s-%s" % (package_name.replace("-", "_"), package_version)).lower()

    logger.debug("Expecting PyPI filename prefixes: %s or %s" % (expected_prefix, expected_prefix_underscore))

    # parse the incoming HTML
    tree = html5lib.parse(response.text)
    namespace = get_html_namespace(tree)
    links = html_findall(tree, namespace, "./{ns}body/{ns}a")

    urls = []
    for link in links:
        filename = re.sub(r"\.[0]+(\d+)", r".\1", link.text.strip().lower())
        url = "https://pypi.python.org/%s" % link.attrib["href"].replace("../../", "")

        if filename.startswith(expected_prefix) or filename.startswith(expected_prefix_underscore):
            if required_suffix is not None:
                if filename.endswith(required_suffix):
                    urls.append(url)
            else:
                urls.append(url)

    return urls


def get_pypi_sha256(url):
    """Downloads the given file from the specified URL, optionally validating the MD5 hash (if one is supplied in
    the URL itself). Returns the SHA-256 hash of the given file."""
    url_parts = url.split("#md5=")

    response = requests.get(url_parts[0])
    if response.status_code >= 300:
        raise PackageFetchError(url)

    if len(url_parts) > 1:
        md5 = hashlib.md5(response.content).hexdigest().lower()
        if md5 != url_parts[1]:
            raise HashValidationFailedError(url, url_parts[1], md5)

    return hashlib.sha256(response.content).hexdigest()
