[![codecov](https://codecov.io/gh/OmenApps/django-postgresql-dag/branch/master/graph/badge.svg?token=IJRBEE6R0C)](https://codecov.io/gh/OmenApps/django-postgresql-dag) ![PyPI](https://img.shields.io/pypi/v/django-postgresql-dag?color=green) ![last commit](https://badgen.net/github/last-commit/OmenApps/django-postgresql-dag) [![Documentation Status](https://readthedocs.org/projects/django-postgresql-dag/badge/?version=latest)](http://django-postgresql-dag.readthedocs.io/) [![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)

# Django & Postgresql-based Directed Acyclic Graphs

The main distinguishing factor for this project is that it can retrieve entire sections of a graph with far
fewer queries than most other packages. The trade off is portability: it uses Postgres' Common Table
Expressions (CTE) to achieve this and is therefore not compatible with other databases.

NOTE: Not all methods which would benefit from CTEs use them yet. **This project is a work in progress. Again, this project is a work in progress.** While functional, it is not yet fully optimized.

The primary purpose of this package is to *build* and *manipulate* DAGs. If you are looking for graph *analysis* or *visualization*, this is not the right package.

Currently, django-postgresql-dag provides numerous methods for retrieving nodes, and a few for retrieving edges within the graph. In-progress are filters within the CTEs in order to limit the area of the graph to be searched, ability to easily export to NetworkX, and other improvements and utilities.

## Demo

[Quickstart example](https://django-postgresql-dag.readthedocs.io/en/latest/quickstart.html)

## Install

    pip install django-postgresql-dag

With optional dependencies for using transformations:

    pip install django-postgresql-dag[transforms]


## ToDo

See the checklists in [issues](https://github.com/OmenApps/django-postgresql-dag/issues) to understand the future goals of this project.


## Credits:

1. [This excellent blog post](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)
