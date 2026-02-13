"""Sphinx configuration for django-postgresql-dag documentation."""

from datetime import datetime

project = "django-postgresql-dag"
author = "Jack Linke"
copyright = f"{datetime.now().year}, {author}"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_togglebutton",
    "sphinxcontrib.mermaid",
    "sphinx.ext.intersphinx",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
    "smartquotes",
    "replacements",
    "substitution",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": ("https://docs.djangoproject.com/en/5.2/", None),
}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
