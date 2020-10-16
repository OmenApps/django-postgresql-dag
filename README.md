# Django & Postgresql-based Directed Acyclic Graphs

The main distinghishing factor for this project is that it can retrieve entire
sections of a graph in a single query. The trade off is portability: it uses
Postgres Common Table Expressions (CTE) to achieve this and is therefore not
compatible with other databases.

## Example:


## Credits:

1. [This excellent blog post](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)

