"""Nox sessions for django-postgresql-dag."""

import sys

import nox

DJANGO_STABLE_VERSION = "5.2"
DJANGO_VERSIONS = ["4.2", "5.1", "5.2", "6.0"]
PYTHON_STABLE_VERSION = "3.13"
PYTHON_VERSIONS = ["3.11", "3.12", "3.13"]
PACKAGE = "django_postgresql_dag"

nox.options.default_venv_backend = "uv"
nox.options.sessions = ["pre-commit", "pip-audit", "tests"]


@nox.session(name="pre-commit", python=PYTHON_STABLE_VERSION)
def precommit(session: nox.Session) -> None:
    """Run pre-commit hooks on all files."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files")


@nox.session(python=PYTHON_STABLE_VERSION)
def pip_audit(session: nox.Session) -> None:
    """Scan dependencies for known vulnerabilities."""
    session.install(".[dev]")
    session.install("pip-audit")
    session.run("pip-audit")


@nox.session(
    python=PYTHON_VERSIONS,
    tags=["tests"],
)
@nox.parametrize("django", DJANGO_VERSIONS)
def tests(session: nox.Session, django: str) -> None:
    """Run the test suite across Python and Django versions."""
    # Django 6.0 requires Python 3.12+
    if django == "6.0" and session.python == "3.11":
        session.skip("Django 6.0 requires Python 3.12+")

    session.install(".[dev]")
    session.install(f"django~={django}.0")
    session.run(
        "coverage",
        "run",
        "-m",
        "pytest",
        "-vv",
        *session.posargs,
    )

    if sys.stdin.isatty():
        session.notify("coverage")


@nox.session(python=PYTHON_STABLE_VERSION)
def coverage(session: nox.Session) -> None:
    """Combine and report coverage."""
    session.install("coverage[toml]")
    session.run("coverage", "combine", success_codes=[0, 1])
    session.run("coverage", "report")
