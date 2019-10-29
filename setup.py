#!/usr/bin/env python
import codecs
import sys
from os import path

from setuptools import setup

# Get version from package
version = __import__("kapten").__version__

# Get the long description from the README
long_description = None
here = path.dirname(path.abspath(__file__))
with codecs.open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

tests_require = ["responses"]
if sys.version_info[:2] >= (3, 6):
    tests_require.append("starlette>=0.12.10,<0.13")

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
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=["kapten"],
    entry_points={"console_scripts": ["kapten = kapten.cli:command"]},
    install_requires=["docker"],
    extras_require={
        "server": [
            "starlette>=0.12.10,<0.13",
            "uvloop==0.14.0rc1",
            "uvicorn>=0.9.1,<0.10",
        ]
    },
    tests_require=tests_require,
    test_suite="tests",
)
