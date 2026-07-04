# Django & PostgreSQL-based Directed Acyclic Graphs

[![PyPI](https://img.shields.io/pypi/v/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Django versions](https://img.shields.io/pypi/djversions/django-postgresql-dag)](https://pypi.org/project/django-postgresql-dag/)
[![Documentation](https://readthedocs.org/projects/django-postgresql-dag/badge/?version=latest)](https://django-postgresql-dag.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Model directed acyclic graphs in Django without paying for the traversal one query at a time.

A lot of graph libraries walk a hierarchy level by level, firing a query for each generation. This one pushes the whole traversal down into PostgreSQL with recursive Common Table Expressions (CTEs), so reading every descendant of a node, every ancestor, or the path between two nodes is a single query regardless of how deep the graph runs.

The catch is portability. That speed comes from Postgres-specific SQL, so this library runs on PostgreSQL only. SQLite, MySQL, and the rest are not supported, and that is unlikely to change.

## Is this the right package?

It is a good fit if you want to **build and manipulate** DAGs that live in your database: add and remove edges, walk ancestors and descendants, find paths, and run the usual DAG algorithms directly against your tables.

It is the wrong fit if you mainly want graph **analysis or visualization**. If your graph fits in memory and you just want to run algorithms over it, NetworkX or rustworkx will serve you better. When you do need them, the `transforms` extra hands your data straight to either one.

## A quick taste

Define an edge model first, then the node model that connects through it:

```python
from django.db import models
from django_postgresql_dag.models import node_factory, edge_factory


class Edge(edge_factory("Node")):
    pass


class Node(node_factory(Edge)):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
```

Then wire up a graph and ask it questions:

```python
root = Node.objects.create(name="root")
a = Node.objects.create(name="a")
b = Node.objects.create(name="b")
c = Node.objects.create(name="c")

root.add_child(a)
root.add_child(b)
a.add_child(c)
b.add_child(c)        # c has two parents; that is what makes this a DAG and not a tree

root.descendants()    # every node below root, one query deep or fifty deep
c.ancestors()         # everything above c
root.path(c)          # a route from root down to c
c.is_leaf()           # True
```

Adding an edge that would close a loop raises an error by default, so the graph stays acyclic without you policing it. You can relax that (and the duplicate/redundant-edge checks) per model if you have a reason to.

## Install

```
pip install django-postgresql-dag
```

For NetworkX, rustworkx, and JSON export:

```
pip install django-postgresql-dag[transforms]
```

## Configuration

Graph traversals stop at a maximum depth so a runaway query cannot wander forever. The default is 20. To change it project-wide:

```python
# settings.py
DJANGO_POSTGRESQL_DAG_MAX_DEPTH = 50
```

You can still override it on any individual call with `max_depth=N`.

## What you can do with a node

Traversal and paths: `ancestors()`, `descendants()`, `clan()`, `path(target)`, `connected_graph()`, plus the matching edge queries (`ancestors_edges()`, `descendants_edges()`, `clan_edges()`).

Structure and relationships: `roots()`, `leaves()`, `siblings()`, `partners()`, `ancestors_tree()`, `descendants_tree()`.

Mutations: `add_child()`, `remove_child()`, `add_parent()`, `remove_parent()`.

Predicates: `is_root()`, `is_leaf()`, `is_island()`, `is_ancestor_of()`, `is_descendant_of()`.

Heavier algorithms: depth annotation, topological sort, all-paths enumeration, lowest common ancestor, weighted shortest path, critical (longest) path, transitive reduction, and graph hashing (Weisfeiler-Lehman, via NetworkX).

You can also narrow the part of the graph a traversal searches with `disallow_nodes`, `allow_nodes`, `disallow_edges`, `allow_edges`, and `limiting_edges_set_fk` (with `edge_type` as a shorthand). Manager methods `connected_components()` and `graph_stats()` work across the whole graph.

The [node reference](https://django-postgresql-dag.readthedocs.io/en/latest/node-reference.html) and [edge reference](https://django-postgresql-dag.readthedocs.io/en/latest/edge-reference.html) cover every method in detail.

## Documentation

[Quickstart](https://django-postgresql-dag.readthedocs.io/en/latest/quickstart.html) walks through a full example. The [Tutorial](https://django-postgresql-dag.readthedocs.io/en/latest/tutorial.html) explains why the pieces fit together the way they do. Everything else lives in the [full documentation](https://django-postgresql-dag.readthedocs.io/en/latest/).

## Roadmap

The [issue tracker](https://github.com/OmenApps/django-postgresql-dag/issues) holds the running checklists of where this is headed.

## Credits

Earlier projects and writing this one borrows from:

1. [This blog post on recursive CTEs and topological sort in Postgres](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)
