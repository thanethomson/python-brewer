# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import six

import hashlib

import requests

from pythonbrewer.deplist import *
from pythonbrewer.pypi import *
from pythonbrewer.errors import *

import logging
logger = logging.getLogger(__name__)

__all__ = [
    "generate_homebrew_formula"
]


HOMEBREW_FORMULA_TEMPLATE = """class {formula_name} < Formula
  include Language::Python::Virtualenv

  desc "{description}"
  homepage "{homepage}"
  url "{package_url}"
  sha256 "{package_sha256}"
  head "{git_repo_url}"

  # TODO: If you're submitting an existing package, make sure you include your
  #       bottle block here.

  {python_dep}{dependencies}

  def install
    virtualenv_install_with_resources
  end

  # TODO: Add your package's tests here
end"""


def calculate_dep_params(dep):
    logger.info(
        " - Calculating SHA256 hash of dependency: %s, version: %s" % (
            dep['package_name'],
            dep['installed_version']
        )
    )
    package_files = fetch_pypi_package_files(
        dep['package_name'],
        dep['installed_version'],
        required_suffix=".tar.gz"
    )
    if len(package_files) == 0:
        raise PackageNotFoundError(dep['package_name'])

    sha256 = get_pypi_sha256(package_files[0])
    return dep['package_name'], package_files[0].split("#md5=")[0], sha256


def get_release_file_sha256(url):
    logger.info(" - Calculating SHA256 hash of release file: %s" % url)
    response = requests.get(url)
    if response.status_code >= 300:
        raise PackageFetchError(url)

    return hashlib.sha256(response.content).hexdigest()


def generate_homebrew_formula(python_package_name, formula_name, description, homepage, git_repo_url,
                              release_url=None):
    """Attempts to generate a Homebrew formula template from the given information.

    Args:
        python_package_name: The name of the Python package for which we're generating the template.
        formula_name: The desired name of the Homebrew formula.
        description: The full text description of the formula.
        homepage: The homepage URL for the package.
        git_repo_url: The Git repo URL for the package.
        release_url: A custom release URL for the Python package, which will override getting the release
            from PyPI.

    Returns:
        A string containing the generated template.
    """
    deps = build_dep_list(python_package_name)
    logger.info("Found %d unique dependencies for Python package %s:" % (len(deps), python_package_name))
    for dep in deps:
        logger.info(" - %s %s" % (dep["package_name"], dep["installed_version"]))

    logger.info("")
    logger.info("Downloading packages and calculating SHA256 hashes:")

    dep_string = ""
    for dep in deps[:-1]:
        package_name, url, sha256 = calculate_dep_params(dep)
        dep_string += ('\n\n  resource "{package_name}" do\n'
                       '    url "{url}"\n'
                       '    sha256 "{sha256}"\n'
                       '  end').format(
            package_name=package_name,
            url=url,
            sha256=sha256
        )

    logger.info("")
    logger.info("Downloading release package:")
    if release_url is None:
        # fetch the details for our python package (should be the last dependency in the ordered dependency list)
        package_name, url, sha256 = calculate_dep_params(deps[-1])
    else:
        package_name, url, sha256 = python_package_name, release_url, get_release_file_sha256(release_url)

    logger.info("")

    return HOMEBREW_FORMULA_TEMPLATE.format(
        formula_name=formula_name,
        description=description,
        homepage=homepage,
        package_url=url,
        package_sha256=sha256,
        git_repo_url=git_repo_url,
        python_dep="depends_on :python if MacOS.version <= :snow_leopard" if six.PY2 else "depends_on :python3",
        dependencies=dep_string
    )
