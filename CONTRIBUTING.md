# Contributing to django-postgresql-dag

We would love your input! We want to make contributing to the project as easy and transparent as possible. We welcome...

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## Getting the Code

```bash
git clone https://github.com/OmenApps/django-postgresql-dag.git
cd django-postgresql-dag
```

Or fork the repository on GitHub first, then clone your fork.

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — for dependency management
- **Docker** — for running PostgreSQL (or a local PostgreSQL 16+ instance)

## Installing Dependencies

```bash
uv sync --extra dev
```

To include optional NetworkX/pandas transformation support:

```bash
uv sync --extra dev --extra transforms
```

## Running PostgreSQL

The easiest way to get PostgreSQL running is with Docker Compose:

```bash
docker compose up -d
```

This starts PostgreSQL 16 on **host port 5433** (mapped from container port 5432) with default credentials `postgres`/`postgres`. The test settings default to port 5433, so no environment variables are needed when using Docker Compose.

For a custom PostgreSQL setup, configure the connection with environment variables:

| Variable      | Default     |
|---------------|-------------|
| `PG_HOST`     | `localhost` |
| `PG_PORT`     | `5433`      |
| `PG_USER`     | `postgres`  |
| `PG_PASSWORD` | `postgres`  |
| `PG_DATABASE` | `postgres`  |

## Running Tests

```bash
# Run tests with pytest
uv run pytest tests/ -vv

# Or with the Django test runner
uv run python manage.py test
```

To run the full test matrix across Python and Django versions using nox:

```bash
# All default nox sessions (pre-commit, pip-audit, tests)
nox

# A specific Django/Python combination
nox -s "tests(django='5.2', python='3.13')"
```

## Linting & Formatting

```bash
ruff check src/              # lint
ruff check --fix src/        # lint and auto-fix
ruff format src/             # format
pre-commit run --all-files   # run all pre-commit hooks
```

## Building Documentation

```bash
# Build docs with live reload (opens browser)
nox -s docs

# Build docs without serving
nox -s docs-build
```

## Nox Sessions

Running `nox` with no arguments executes the default sessions:

- **pre-commit** — runs all pre-commit hooks
- **pip-audit** — scans dependencies for known vulnerabilities
- **tests** — runs the test suite across the Python/Django version matrix

Additional sessions:

- **docs** — builds and serves docs with live reload
- **docs-build** — builds docs to `docs/_build/`
- **coverage** — combines and reports test coverage

## Code Changes Happen Through Pull Requests

Pull requests are the best way to propose changes to the codebase. We actively welcome your pull requests:

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Coding Style & Commit Messages

- Follow [Django coding conventions](https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/) with a line length of 120
- Use ruff for linting and formatting
- Git commit messages: present tense imperative, first line 72 characters or less (e.g., "Add feature" not "Added feature")
- Reference relevant issues and pull requests as needed after the first line

## Report Bugs

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/OmenApps/django-postgresql-dag/issues/new); it's that easy!

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - They are specific!
  - Give sample code if you can that can be used to easily reproduce the issue. Ideally, strip out everything that does not pertain to the problem or which is not required to allow the sample to run.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

We *love* thorough bug reports.

## Be Kind

This project is volunteer run. Please be kind in your discourse.

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](https://github.com/OmenApps/django-postgresql-dag/blob/main/LICENSE).
