# Configuration Reference

## Installation

```bash
pip install django-postgresql-dag
```

With optional dependencies for graph export and transformation:

```bash
pip install django-postgresql-dag[transforms]
```

The `transforms` extra installs `networkx`, `rustworkx`, and `pandas`.

## Requirements

- **PostgreSQL** - required. django-postgresql-dag uses recursive CTEs (`WITH RECURSIVE`), which are PostgreSQL-specific. It is not compatible with SQLite, MySQL, or other databases.
- **Supported primary key types**: `integer`, `smallint`, `bigint`, `uuid`, `text`. The query builders handle type casting automatically based on your model's primary key field type (`AutoField`, `SmallAutoField`, `BigAutoField`, `IntegerField`, `SmallIntegerField`, `BigIntegerField`, `UUIDField`, `CharField`, `SlugField`, `TextField`).

## Django settings

**`DJANGO_POSTGRESQL_DAG_MAX_DEPTH`**

Sets the project-wide default maximum depth for all graph traversal methods (`ancestors()`, `descendants()`, `path()`, etc.). Defaults to `20`.

```python
# settings.py
DJANGO_POSTGRESQL_DAG_MAX_DEPTH = 50
```

You can override this per-call by passing `max_depth=N` to any traversal method.

**`DJANGO_POSTGRESQL_DAG_ALLOW_REDUNDANT_EDGES`**

Sets the project-wide default for whether redundant (transitively reachable) edges are allowed. Defaults to `True`. A redundant edge is one where the child is already reachable from the parent via an existing path (e.g. adding A->C when A->B->C already exists).

```python
# settings.py
DJANGO_POSTGRESQL_DAG_ALLOW_REDUNDANT_EDGES = False  # block redundant edges by default
```

You can override this per-call by passing `allow_redundant_edges=True/False` to `add_child()` or `add_parent()`.

## Factory functions

### `edge_factory(node_model, concrete=True, base_model=models.Model)`

Creates an abstract base class for your Edge model.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `node_model` | `str` or model class | *(required)* | The Node model this edge connects. Use a string name (e.g. `"MyNode"`) when the Node class hasn't been defined yet. |
| `concrete` | `bool` | `True` | If `True`, the factory returns a concrete model. If `False`, returns an abstract model - your subclass provides the database table. Almost always set to `False`. |
| `base_model` | model class | `models.Model` | Base class for the generated model. Use this to inject a custom base (e.g. a TimeStampedModel). |

The generated model provides:
- `parent` - ForeignKey to the node model (the "from" side)
- `child` - ForeignKey to the node model (the "to" side)
- Circular reference checking on save (unless disabled)
- Duplicate edge checking on save (unless disabled)
- Redundant edge checking on save (unless allowed)

### `node_factory(edge_model, children_null=True, base_model=models.Model)`

Creates an abstract base class for your Node model.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `edge_model` | model class | *(required)* | The Edge model that connects nodes. Must be the actual class (not a string). |
| `children_null` | `bool` | `True` | Whether the ManyToManyField for children allows null. |
| `base_model` | model class | `models.Model` | Base class for the generated model. |

The generated model provides:
- `children` - ManyToManyField through the edge model
- All traversal, path, predicate, and mutation methods (see [Node API Reference](node-reference.md))
- Custom manager with `roots()`, `leaves()`, `topological_sort()`, and other graph-wide methods

### Definition order

**Edge first, then Node.** The edge factory accepts a string reference to the node model, so define the Edge class before the Node class:

```python
class MyEdge(edge_factory("MyNode", concrete=False)):
    ...

class MyNode(node_factory(MyEdge)):
    ...
```

## Edge model options

These class attributes can be set on your Edge subclass to change validation behavior.

**`disable_circular_check`**
: Default: `False`. When `True`, the edge model will not check for circular paths on save. The resulting graph may no longer be acyclic.

**`allow_duplicate_edges`**
: Default: `True`. When `False`, saving an exact duplicate edge (same parent and child as an existing edge) raises `ValidationError`.

**`allow_redundant_edges`**
: Default: `True` (or the value of the `DJANGO_POSTGRESQL_DAG_ALLOW_REDUNDANT_EDGES` setting). When `False`, saving an edge where the child is already transitively reachable from the parent raises `ValidationError`. For example, adding A->C when A->B->C already exists.

```python
class MyEdge(edge_factory("MyNode", concrete=False)):
    disable_circular_check = False    # default
    allow_duplicate_edges = True      # default
    allow_redundant_edges = True      # default
```
