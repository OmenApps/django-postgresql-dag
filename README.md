# Django & Postgresql-based Directed Acyclic Graphs

[![PyPI](https://img.shields.io/pypi/v/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Django versions](https://img.shields.io/pypi/djversions/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Documentation](https://readthedocs.org/projects/django-postgresql-dag/badge/?version=latest)](https://django-postgresql-dag.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

The main distinguishing factor for this project is that it can retrieve entire sections of a graph with far
fewer queries than most other packages. The trade off is portability: it uses Postgres' Common Table
Expressions (CTE) to achieve this and is therefore not compatible with other databases.

The primary purpose of this package is to *build* and *manipulate* DAGs within a Django project. If you are looking for graph *analysis* or *visualization*, this may not be the right package.

All core traversal methods (`ancestors()`, `descendants()`, `path()`, `connected_graph()`, tree methods, `roots()`, `leaves()`, edge queries, etc.) use CTE-based queries.

The package also supports CTE filters (`disallow_nodes`, `allow_nodes`, `disallow_edges`, `allow_edges`, `limiting_edges_set_fk`) to limit the area of the graph searched, and optional NetworkX/RustworkX/JSON export via the `transforms` extra. Manager-level methods `connected_components()` and `graph_stats()` provide whole-graph analytics. All traversal and predicate methods accept a convenient `edge_type` parameter as shorthand for `limiting_edges_set_fk`.

Additional graph algorithms include: topological sort, depth annotation, all-paths enumeration, lowest common ancestor (LCA), weighted shortest path, critical path (longest path), transitive reduction, and graph hashing (via NetworkX Weisfeiler-Lehman).

## Demo

[Quickstart example](https://django-postgresql-dag.readthedocs.io/en/latest/quickstart.html) | [Tutorial](https://django-postgresql-dag.readthedocs.io/en/latest/tutorial.html) | [Full documentation](https://django-postgresql-dag.readthedocs.io/en/latest/)

## Install

    pip install django-postgresql-dag

With optional dependencies for using transformations:

    pip install django-postgresql-dag[transforms]


## Configuration

You can optionally configure the default maximum traversal depth for all graph queries by adding this to your Django settings:

```python
# settings.py
DJANGO_POSTGRESQL_DAG_MAX_DEPTH = 50  # default is 20
```

This sets the project-wide default for all graph traversal methods (`ancestors()`, `descendants()`, `path()`, etc.). You can still override it per-call by passing `max_depth=N` to any method.

## ToDo

See the checklists in [issues](https://github.com/OmenApps/django-postgresql-dag/issues) to understand the future goals of this project.


## Credits:

1. [This excellent blog post](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)
