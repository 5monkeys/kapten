import nox

nox.options.stop_on_first_error = True
nox.options.reuse_existing_virtualenvs = True
nox.options.keywords = "test + check"

source_files = ("kapten", "tests", "setup.py", "noxfile.py")
lint_requirements = ("flake8", "black", "isort")


@nox.session(python=["3.6", "3.7", "3.8"])
def test(session):
    session.install(
        "--upgrade",
        "pytest",
        "pytest-asyncio",
        "pytest-cov",
        "asynctest",
        "respx>=0.8.1",
        "requests",  # needed by starlette test client
    )
    session.install("-e", ".[server]")

    options = session.posargs
    if "-k" in options:
        options.append("--no-cov")

    session.run("pytest", "-v", *options)


@nox.session
def check(session):
    session.install("--upgrade", "flake8-bugbear", "mypy", *lint_requirements)
    session.install("-e", ".[server]")

    session.run("black", "--check", "--diff", "--target-version=py36", *source_files)
    session.run("isort", "--check", "--diff", "--project=kapten", "-rc", *source_files)
    session.run("flake8", *source_files)
    session.run("mypy", "kapten")


@nox.session
def lint(session):
    session.install("--upgrade", "autoflake", *lint_requirements)

    session.run("autoflake", "--in-place", "--recursive", *source_files)
    session.run("isort", "--project=kapten", "--recursive", "--apply", *source_files)
    session.run("black", "--target-version=py36", *source_files)

    check(session)
