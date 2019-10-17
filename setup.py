#!/usr/bin/env python
import codecs
from os import path

from setuptools import setup

# Get version from package
version = __import__("kapten").__version__

# Get the long description from the README
long_description = None
here = path.dirname(path.abspath(__file__))
with codecs.open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="kapten",
    version=version,
    author="Jonas Lundberg",
    author_email="jonas@5monkeys.se",
    url="https://github.com/5monkeys/kapten",
    license="MIT",
    keywords=["docker", "swarm", "stack", "service", "auto", "deploy"],
    description="Auto deploy of Docker Swarm services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["kapten"],
    entry_points={"console_scripts": ["kapten = kapten.cli:command"]},
    install_requires=["docker"],
    tests_require=["responses"],
    test_suite="tests",
)
