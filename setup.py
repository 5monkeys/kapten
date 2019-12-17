#!/usr/bin/env python
from pathlib import Path

from setuptools import setup

exec(Path("kapten", "__version__.py").read_text())  # Load __version__ into locals

setup(
    name="kapten",
    version=locals()["__version__"],
    license="MIT",
    author="Jonas Lundberg",
    author_email="jonas@5monkeys.se",
    url="https://github.com/5monkeys/kapten",
    keywords=["docker", "swarm", "stack", "service", "auto", "deploy"],
    description="Auto deploy of Docker Swarm services",
    long_description=Path("README.md").read_text("utf-8"),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=["kapten"],
    package_data={"httpx": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
    entry_points={"console_scripts": ["kapten = kapten.cli:command"]},
    python_requires=">=3.6",
    install_requires=["requests", "httpx>=0.9.3,<0.9.4"],
    extras_require={"server": ["uvicorn>=0.10.3,<0.11", "starlette>=0.12.13,<0.13"]},
)
