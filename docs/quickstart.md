# Quickstart Example

This page walks through a complete example: defining models, creating nodes and edges, and querying the graph. If you want more explanation of *why* things work this way, see the [Tutorial](tutorial.md). If you just want to see the API, keep reading.

## models.py

```python
from django.db import models
from django_postgresql_dag.models import node_factory, edge_factory

class EdgeSet(models.Model):
    # Not required, but provides a convenient way of grouping Edges
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class NodeSet(models.Model):
    # Not required, but provides a convenient way of grouping Nodes
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class NetworkEdge(edge_factory("NetworkNode", concrete=False)):
    name = models.CharField(max_length=100, unique=True)

    edge_set = models.ForeignKey(
        EdgeSet,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="edge_set_edges",
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = f"{self.parent.name} {self.child.name}"
        super().save(*args, **kwargs)


class NetworkNode(node_factory(NetworkEdge)):
    name = models.CharField(max_length=100)

    node_set = models.ForeignKey(
        NodeSet,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="node_set_nodes",
    )

    def __str__(self):
        return self.name
```

For details on `edge_factory` and `node_factory` arguments (like `disable_circular_check`, `allow_duplicate_edges`, and `allow_redundant_edges`), see the [Configuration Reference](configuration.md).

## Add some instances via the shell (or in views, etc)

```python
>>> from myapp.models import NetworkNode, NetworkEdge

>>> root = NetworkNode.objects.create(name="root")

>>> a1 = NetworkNode.objects.create(name="a1")
>>> a2 = NetworkNode.objects.create(name="a2")
>>> a3 = NetworkNode.objects.create(name="a3")

>>> b1 = NetworkNode.objects.create(name="b1")
>>> b2 = NetworkNode.objects.create(name="b2")
>>> b3 = NetworkNode.objects.create(name="b3")
>>> b4 = NetworkNode.objects.create(name="b4")

>>> c1 = NetworkNode.objects.create(name="c1")
>>> c2 = NetworkNode.objects.create(name="c2")

>>> root.add_child(a1)
>>> root.add_child(a2)
>>> a3.add_parent(root)  # You can add from either side of the relationship

>>> b1.add_parent(a1)
>>> a1.add_child(b2)
>>> a2.add_child(b2)
>>> a3.add_child(b3)
>>> a3.add_child(b4)

>>> b3.add_child(c2)
>>> b3.add_child(c1)
>>> b4.add_child(c1)
```

## Add edges and nodes to EdgeSet and NodeSet models (FK)

```python
>>> y = EdgeSet.objects.create()
>>> y.save()

>>> c1_ancestors = c1.ancestors_edges()

>>> for ancestor in c1_ancestors:
>>>     ancestor.edge_set = y
>>>     ancestor.save()

>>> x = NodeSet.objects.create()
>>> x.save()
>>> root.node_set = x
>>> root.save()
>>> a1.node_set = x
>>> a1.save()
>>> b1.node_set = x
>>> b1.save()
>>> b2.node_set = x
>>> b2.save()
```

## Resulting database tables

### myapp_networknode

```text
 id | name
----+------
 1  | root
 2  | a1
 3  | a2
 4  | a3
 5  | b1
 6  | b2
 7  | b3
 8  | b4
 9  | c1
 10 | c2
```

### myapp_networkedge

```text
id  | child_id | parent_id | name
----+----------+-----------+---------
 1  |       2  |         1 | root a1
 2  |       3  |         1 | root a2
 3  |       4  |         1 | root a3
 4  |       5  |         2 | a1 b1
 5  |       6  |         2 | a1 b2
 6  |       6  |         3 | a2 b2
 7  |       7  |         4 | a3 b3
 8  |       8  |         4 | a3 b4
 9  |       10 |         7 | b3 c2
 10 |       9  |         7 | b3 c1
 11 |       9  |         8 | b4 c1
```

## Diagram

![Diagram of Resulting Graph](https://raw.githubusercontent.com/OmenApps/django-postgresql-dag/master/docs/images/graph.png)

## Work with the graph in the shell (or in views, etc)

```python
>>> from myapp.models import NetworkNode, NetworkEdge

# Descendant methods which return a queryset

>>> root.descendants()
<QuerySet [<NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>, <NetworkNode: b1>, <NetworkNode: b2>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>, <NetworkNode: c2>]>
>>> root.descendants(max_depth=1)
<QuerySet [<NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>]>
>>> root.self_and_descendants()
<QuerySet [<NetworkNode: root>, <NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>, <NetworkNode: b1>, <NetworkNode: b2>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>, <NetworkNode: c2>]>
>>> root.descendants_and_self()
[<NetworkNode: c2>, <NetworkNode: c1>, <NetworkNode: b4>, <NetworkNode: b3>, <NetworkNode: b2>, <NetworkNode: b1>, <NetworkNode: a3>, <NetworkNode: a2>, <NetworkNode: a1>, <NetworkNode: root>]

# Ancestor methods which return a queryset

>>> c1.ancestors()
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>]>
>>> c1.ancestors(max_depth=2)
<QuerySet [<NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>]>
>>> c1.ancestors_and_self()
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>]>
>>> c1.self_and_ancestors()
[<NetworkNode: c1>, <NetworkNode: b4>, <NetworkNode: b3>, <NetworkNode: a3>, <NetworkNode: root>]

# Get the node's clan (all ancestors, self, and all descendants)

>>> b3.clan()
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>, <NetworkNode: c2>]>

# Get all roots or leaves associated with the node

>>> b3.roots()
{<NetworkNode: root>}
>>> b3.leaves()
{<NetworkNode: c1>, <NetworkNode: c2>}

# Perform path search

>>> root.path(c1)
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>]>
>>> root.path(c1, max_depth=2)  # c1 is 3 levels deep from root
Traceback (most recent call last):
  File "<input>", line 1, in <module>
    root.path(c1, max_depth=2)
  File "/home/runner/pgdagtest/pg/models.py", line 550, in path
    ids = [item.id for item in self.path_raw(target_node, **kwargs)]
  File "/home/runner/pgdagtest/pg/models.py", line 546, in path_raw
    raise NodeNotReachableException
pg.models.NodeNotReachableException
>>> root.path(c1, max_depth=3)
<QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>]>

# Reverse (upward) path search

>>> c1.path(root)  # Path defaults to top-down search, unless `directional` is set to False
Traceback (most recent call last):
  File "<input>", line 1, in <module>
    c1.path(root)
  File "/home/runner/pgdagtest/pg/models.py", line 548, in path
    ids = [item.id for item in self.path_raw(target_node, **kwargs)]
  File "/home/runner/pgdagtest/pg/models.py", line 544, in path_raw
    raise NodeNotReachableException
pg.models.NodeNotReachableException
>>> c1.path(root, directional=False)
<QuerySet [<NetworkNode: c1>, <NetworkNode: b3>, <NetworkNode: a3>, <NetworkNode: root>]>
>>> root.distance(c1)
3

# Check node properties

>>> root.is_root()
True
>>> root.is_leaf()
False
>>> root.is_island()
False
>>> c1.is_root()
False
>>> c1.is_leaf()
True
>>> c1.is_island()
False

# Get ancestors/descendants tree output

>>> a2.descendants_tree()
{<NetworkNode: b2>: {}}
>>> root.descendants_tree()
{<NetworkNode: a1>: {<NetworkNode: b1>: {}, <NetworkNode: b2>: {}}, <NetworkNode: a2>: {<NetworkNode: b2>: {}}, <NetworkNode: a3>: {<NetworkNode: b3>: {<NetworkNode: c2>: {}, <NetworkNode: c1>: {}}, <NetworkNode: b4>: <NetworkNode: c1>: {}}}}
>>> root.ancestors_tree()
{}
>>> c1.ancestors_tree()
{<NetworkNode: b3>: {<NetworkNode: a3>: {<NetworkNode: root>: {}}}, <NetworkNode: b4>: {<NetworkNode: a3>: {<NetworkNode: root>: {}}}}
>>> c2.ancestors_tree()
{<NetworkNode: b3>: {<NetworkNode: a3>: {<NetworkNode: root>: {}}}}

# Get a queryset of edges related to a particular node

>>> a1.ancestors_edges()
<QuerySet [<NetworkEdge: root a1>]>
>>> b4.descendants_edges()
<QuerySet [<NetworkEdge: b4 c1>]>
>>> b4.clan_edges()
<QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b4>, <NetworkEdge: b4 c1>]>

# Get the nodes at the start or end of an edge

>>> e1.parent
<NetworkNode: root>
>>> e1.child
<NetworkNode: a1>

>>> e2.parent
<NetworkNode: b4>
>>> e2.child
<NetworkNode: c1>

# Edge-specific Manager methods

>>> NetworkEdge.objects.descendants(b3)
<QuerySet [<NetworkEdge: b3 c2>, <NetworkEdge: b3 c1>]>
>>> NetworkEdge.objects.ancestors(b3)
<QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b3>]>
>>> NetworkEdge.objects.clan(b3)
<QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b3>, <NetworkEdge: b3 c2>, <NetworkEdge: b3 c1>]>
>>> NetworkEdge.objects.path(root, c1)
<QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b3>, <NetworkEdge: b3 c1>]>
>>> NetworkEdge.objects.path(c1, root)  # Path defaults to top-down search, unless `directional` is set to False
Traceback (most recent call last):
  File "<input>", line 1, in <module>
    NetworkEdge.objects.path(c1, root)
  File "/home/runner/pgdagtest/pg/models.py", line 677, in path
    start_node.path(end_node),
  File "/home/runner/pgdagtest/pg/models.py", line 548, in path
    ids = [item.id for item in self.path_raw(target_node, **kwargs)]
  File "/home/runner/pgdagtest/pg/models.py", line 544, in path_raw
    raise NodeNotReachableException
pg.models.NodeNotReachableException
>>> NetworkEdge.objects.path(c1, root, directional=False)
<QuerySet [<NetworkEdge: b3 c1>, <NetworkEdge: a3 b3>, <NetworkEdge: root a3>]>
```
