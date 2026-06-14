# Edge API Reference

Complete reference for all methods available on the Edge manager. For practical examples, see [Filtering Graph Traversals](filtering.md) and [Working with Paths and Algorithms](paths-and-algorithms.md).

## Manager Methods

These are called on `MyEdge.objects`.

**from_nodes_queryset(self, nodes_queryset)**
: Given a QuerySet of nodes, returns a QuerySet of all edges where both parent and child are in the provided nodes.

Given a queryset containing root, a1, a2, b1, and b2 (green), `from_nodes_queryset()` returns only the solid edges - those where both parent and child are in the queryset. Dashed edges are excluded:

```{mermaid}
flowchart TD
    root --> a1 & a2
    root -.-> a3
    a1 --> b1 & b2
    a2 --> b2
    a3 -.-> b3 & b4
    b3 -.-> c1 & c2
    b4 -.-> c1
    style root fill:#4CAF50,color:#fff
    style a1 fill:#4CAF50,color:#fff
    style a2 fill:#4CAF50,color:#fff
    style b1 fill:#4CAF50,color:#fff
    style b2 fill:#4CAF50,color:#fff
```

**descendants(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges descended from the given node.

**ancestors(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges which are ancestors of the given node.

`MyEdge.objects.ancestors(b3)` returns the edges (green) on paths from b3 upward toward roots:

```{mermaid}
flowchart TD
    root -->|returned| a3
    a3 -->|returned| b3
    b3 --> c1 & c2
    b4 --> c1
    linkStyle 0 stroke:#4CAF50,stroke-width:3px
    linkStyle 1 stroke:#4CAF50,stroke-width:3px
```

**clan(self, node, \*\*kwargs)**
: Returns a QuerySet of all edges for ancestors, self, and descendants of the given node.

**path(self, start_node, end_node, \*\*kwargs)**
: Returns a QuerySet of edges forming the shortest path from `start_node` to `end_node`. Accepts `directional` (default `True`).

**redundant_edges(self)**
: Returns a QuerySet of redundant edges - those removable by transitive reduction. An edge A→C is redundant if C is reachable from A via a path of length >= 2.

An edge A - C is redundant if C is reachable from A through a longer path. `redundant_edges()` returns these edges; `transitive_reduction(delete=True)` removes them:

```{mermaid}
flowchart TD
    A --> B --> C
    A -.->|redundant| C
    linkStyle 2 stroke:#F44336,stroke-width:2px
```

**transitive_reduction(self, delete=False)**
: Identifies redundant edges. With `delete=True`, removes them and returns the count. See also `NodeManager.transitive_reduction()`.

**validate_route(self, edges, \*\*kwargs)**
: Given an ordered list of edge instances, returns `True` if they form a contiguous route (each edge's child matches the next edge's parent). A single edge or empty list is always valid.

**sort(self, edges, \*\*kwargs)**
: Given a list or set of edge instances, sorts them from root-side to leaf-side using `node_depth()`.

## Inserting a Node into an Edge

**insert_node(self, edge, node, clone_to_rootside=False, clone_to_leafside=False, pre_save=None, post_save=None)**

Inserts a node into an existing edge, splitting it into two new edges. Returns a tuple of `(rootside_edge, leafside_edge)`.

The process:

1. Creates a new edge from the original edge's parent to the inserted node
2. Creates a new edge from the inserted node to the original edge's child
3. Deletes the original edge

After deletion, the original edge instance still exists in memory but not in the database. Run `del edge_instance` to clean up.

### Cloning edge properties

`clone_to_rootside=True` copies the original edge's field values to the new parent-to-inserted-node edge. `clone_to_leafside=True` does the same for the inserted-node-to-child edge.

Cloning fails if a field has `unique=True`. Use `pre_save` to clear or modify unique fields before saving:

```python
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge
```

A `post_save` function can be used to rebuild relationships after the new edges are created.

### Example

Insert node `n2` into the edge between `n1` and `n3`, cloning the original edge's properties to the rootside edge:

Inserting n2 (green) into the edge between n1 and n3 splits it into two new edges:

**Before:**

```{mermaid}
flowchart TD
    n1 -->|original edge| n3
```

**After:**

```{mermaid}
flowchart TD
    n1 -->|rootside edge| n2
    n2 -->|leafside edge| n3
    style n2 fill:#4CAF50,color:#fff
```

```python
from myapp.models import NetworkEdge, NetworkNode

n1 = NetworkNode.objects.create(name="n1")
n2 = NetworkNode.objects.create(name="n2")
n3 = NetworkNode.objects.create(name="n3")

# Connect n3 to n1
n1.add_child(n3)

e1 = NetworkEdge.objects.last()

# Clear the auto-generated `name` field (it's unique)
def pre_save(new_edge):
    new_edge.name = ""
    return new_edge

NetworkEdge.objects.insert_node(e1, n2, clone_to_rootside=True, pre_save=pre_save)
```

## Edge table indexes

`edge_factory` declares two composite (covering) indexes on the abstract Edge model:
`(parent, child)` and `(child, parent)`. These let the recursive ancestor/descendant
CTEs satisfy their self-joins from the index (the join key *and* the column read on
each recursion step are both in the index), and `(parent, child)` is also an exact
covering match for the `filter(parent=X, child=Y)` lookup the duplicate-edge check
(`duplicate_edge_checker`) runs when an edge is saved with `allow_duplicate_edges=False`.
(The redundant-edge check is a
descendant traversal, not an exact-pair lookup, so it benefits via the CTE path, not
this index.) Whether Postgres performs a true index-only scan depends on the visibility
map and the planner; measure on your own data with `EXPLAIN (ANALYZE, BUFFERS)` rather
than assuming a fixed speedup.

### Required: subclass the factory Meta if you define your own

Django only propagates an abstract model's `Meta.indexes` to a concrete child when the
child either declares **no** `Meta`, or declares a `Meta` that **subclasses** the
abstract one. If your concrete Edge model defines its own `Meta` (for `app_label`,
`db_table`, `ordering`, constraints, etc.) you **must** subclass the factory's `Meta`,
or the indexes are **silently dropped** (no error, and no migration is generated):

```python
EdgeBase = edge_factory("MyNode", concrete=False)

class MyEdge(EdgeBase):
    # ... your fields ...

    class Meta(EdgeBase.Meta):   # <-- subclass, or you lose the indexes
        app_label = "myapp"
```

If your Edge model has no `Meta` at all, the indexes are inherited automatically.

If your `Meta` already declares its own `indexes`, subclassing **overrides** rather than
merges - keep both explicitly:

```python
    class Meta(EdgeBase.Meta):
        indexes = [*EdgeBase.Meta.indexes, *my_own_indexes]
```

Verify the indexes actually landed on your model:

```python
assert {tuple(i.fields) for i in MyEdge._meta.indexes} >= {("parent", "child"), ("child", "parent")}
```

### Write cost and the single-column index redundancy

These two composites are added **on top of** Django's default single-column FK indexes
on `parent_id` and `child_id`. A composite `(parent, child)` already serves `parent_id`
lookups as a left-prefix, and `(child, parent)` serves `child_id` lookups - so the
standalone FK indexes become redundant. Adding the composites therefore increases the
number of indexes maintained on every edge insert (`add_child`) and the storage used.
(The one non-obvious lookup site is the `connected_graph` traversal, which joins on
`parent_id OR child_id`; that disjunction is served by a BitmapOr over the two composites
- coverage is preserved, but as a different plan shape, so verify it with `EXPLAIN` on
representative data before relying on it.)

**Advanced opt-in (write-heavy graphs).** You can drop the redundant single-column
indexes by setting `db_index=False` on the `parent`/`child` FKs. These FKs are declared
*inside* `edge_factory`, so this requires re-declaring both on your concrete Edge model -
and you **must** replicate the factory's exact `related_name` and `on_delete`, or you
will silently rewire your reverse accessors and break the node relations. Read the
generated values first:

```python
for fname in ("parent", "child"):
    f = MyEdge._meta.get_field(fname)
    print(fname, f.remote_field.related_name, f.remote_field.on_delete)
```

then re-declare both FKs on your model with those exact values plus `db_index=False`.
This changes the generated migration (an `AlterField` per FK in addition to the two
`AddIndex` ops), so update your migration-inspection expectations accordingly. If you are
unsure, leave the FKs as-is: the redundant single-column indexes are cheap relative to
the cost of getting the reverse-accessor wiring wrong. A first-class
`edge_factory(..., fk_db_index=False)` option would make this clean and is tracked as
future work.

### Migrating an existing project

Upgrading adds two indexes, so every concrete Edge model needs a new migration
(`python manage.py makemigrations`). The library ships the index *declaration*; it
cannot generate your migration for you - each project runs `makemigrations` locally,
and the auto-generated index names are derived from your table name and are **not**
portable (don't hand-copy a name from another project).

On a large existing edge table, a plain `CREATE INDEX` takes a lock that blocks writes
for the build. For zero-downtime deploys, hand-edit the generated migration to build the
indexes concurrently (this is your project's migration, not something the library does):

```python
from django.contrib.postgres.operations import AddIndexConcurrently

class Migration(migrations.Migration):
    atomic = False   # required for CONCURRENTLY; cannot run inside a transactional TestCase
    operations = [
        AddIndexConcurrently(model_name="myedge", index=models.Index(fields=["parent", "child"], name="...")),
        AddIndexConcurrently(model_name="myedge", index=models.Index(fields=["child", "parent"], name="...")),
    ]
```

Use the exact index `name` Django generated for your model (read it from the
autogenerated migration) so migration state and the database stay in sync.
