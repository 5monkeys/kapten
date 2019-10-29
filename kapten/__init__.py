import sys

VERSION = (1, 3, 0, "final", 0)


def get_version(version=None):
    """Derives a PEP386-compliant version number from VERSION."""
    if version is None:
        version = VERSION  # pragma: nocover
    assert len(version) == 5
    assert version[3] in ("alpha", "beta", "rc", "final")

    # Now build the two parts of the version number:
    # main = X.Y[.Z]
    # sub = .devN - for pre-alpha releases
    #     | {a|b|c}N - for alpha, beta and rc releases

    parts = 2 if version[2] == 0 else 3
    main = ".".join(str(x) for x in version[:parts])

    sub = ""
    if version[3] != "final":  # pragma: no cover
        mapping = {"alpha": "a", "beta": "b", "rc": "c"}
        sub = mapping[version[3]] + str(version[4])

    return main + sub


def supports_feature(name):
    return name == "server" and sys.version_info[:2] >= (3, 6)


def has_feature(name):
    if name == "server" and supports_feature(name):  # pragma: nocover
        try:
            import uvicorn  # noqa
        except ImportError:
            return False
        else:
            return True


__version__ = get_version()
