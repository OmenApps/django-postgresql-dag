
# Django & Postgresql-based Directed Acyclic Graphs

The main distinguishing factor for this project is that it can retrieve entire
sections of a graph in a single query. The trade off is portability: it uses
Postgres Common Table Expressions (CTE) to achieve this and is therefore not
compatible with other databases.

NOTE: Not all methods which would benefit from CTEs use them yet.

NOTE: This project is a work in progress. While functional, it is not optimized. Currently, it provides numerous methods for retrieving nodes, and a few for retrieving edges within the graph.

## Most Simple Example:

### models.py

    from django.db import models
    from django_postgresql_dag.models import node_factory, edge_factory

    class NetworkEdge(edge_factory("NetworkNode", concrete=False)):
        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name

        def save(self, *args, **kwargs):
            self.name = f"{self.parent.name} {self.child.name}"
            super().save(*args, **kwargs)


    class NetworkNode(node_factory(NetworkEdge)):
        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name

### Add some Instances via the Shell (or in views, etc)

    ~/myapp$ python manage.py shell
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

### Resulting Database Tables

#### myapp_networknode

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

#### myapp_networkedge

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

### Diagramatic View

![Diagram of Resulting Graph](https://raw.githubusercontent.com/OmenApps/django-postgresql-dag/master/docs/images/graph.png)

### Work with the Graph in the Shell (or in views, etc)

    ~/myapp$ python manage.py shell
    >>> from myapp.models import NetworkNode, NetworkEdge
    
    # Descendant methods which return ids
    
    >>> root.descendants_ids()
    [2, 3, 4, 5, 6, 7, 8, 9, 10]
    >>> root.self_and_descendants_ids()
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    >>> root.descendants_and_self_ids()
    [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    
    # Descendant methods which return a queryset
    
    >>> root.descendants()
    <QuerySet [<NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>, <NetworkNode: b1>, <NetworkNode: b2>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>, <NetworkNode: c2>]>
    >>> root.self_and_descendants()
    <QuerySet [<NetworkNode: root>, <NetworkNode: a1>, <NetworkNode: a2>, <NetworkNode: a3>, <NetworkNode: b1>, <NetworkNode: b2>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>, <NetworkNode: c2>]>
    >>> root.descendants_and_self()
    [<NetworkNode: c2>, <NetworkNode: c1>, <NetworkNode: b4>, <NetworkNode: b3>, <NetworkNode: b2>, <NetworkNode: b1>, <NetworkNode: a3>, <NetworkNode: a2>, <NetworkNode: a1>, <NetworkNode: root>]
    
    # Ancestor methods which return ids
    
    >>> c1.ancestors_ids()
    [1, 4, 7, 8]
    >>> c1.ancestors_and_self_ids()
    [1, 4, 7, 8, 9]
    >>> c1.self_and_ancestors_ids()
    [9, 8, 7, 4, 1]
    
    # Ancestor methods which return a queryset
    
    >>> c1.ancestors()
    <QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>]>
    >>> c1.ancestors_and_self()
    <QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: b4>, <NetworkNode: c1>]>
    >>> c1.self_and_ancestors()
    [<NetworkNode: c1>, <NetworkNode: b4>, <NetworkNode: b3>, <NetworkNode: a3>, <NetworkNode: root>]
    
    # Get the node's clan (all ancestors, self, and all descendants)
    
    >>> b3.clan_ids()
    [1, 4, 7, 9, 10]
    >>> b3.clan()
    <QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>, <NetworkNode: c2>]>
    
    # Get all roots or leaves associated with the node
    
    >>> b3.get_roots()
    {<NetworkNode: root>}
    >>> b3.get_leaves()
    {<NetworkNode: c1>, <NetworkNode: c2>}

    # Perform path search

    >>> root.path_ids_list(c1)
    [[1, 4, 7, 9]]
    >>> c1.path_ids_list(root)
    Traceback (most recent call last):
      File "<input>", line 1, in <module>
        c1.path_ids_list(root)
      File "/home/runner/pgdagtest/pg/models.py", line 313, in path_ids_list
        raise NodeNotReachableException
    pg.models.NodeNotReachableException
    >>> c1.path_ids_list(root, directional=False)
    [[1, 4, 7, 9]]
    >>> root.path_ids_list(c1, max_paths=2)
    [[1, 4, 7, 9], [1, 4, 8, 9]]
    >>> root.shortest_path(c1)
    <QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b3>, <NetworkNode: c1>]>
    >>> c1.shortest_path(root)
    Traceback (most recent call last):
      File "<input>", line 1, in <module>
        c1.shortest_path(root)
      File "/home/runner/pgdagtest/pg/models.py", line 323, in shortest_path
        return self.filter_order_ids(self.path_ids_list(target_node, directional=directional)[0])
      File "/home/runner/pgdagtest/pg/models.py", line 313, in path_ids_list
        raise NodeNotReachableException
    pg.models.NodeNotReachableException
    >>> c1.shortest_path(root, directional=False)
    <QuerySet [<NetworkNode: root>, <NetworkNode: a3>, <NetworkNode: b4>, <NetworkNode: c1>]>

    # Get a queryset of edges relatd to a particular node

    >>> a1.ancestors_edges()
    <QuerySet [<NetworkEdge: root a1>]>
    >>> b4.descendants_edges()
    <QuerySet [<NetworkEdge: b4 c1>]>
    >>> b4.clan_edges()
    {<NetworkEdge: b4 c1>, <NetworkEdge: root a3>, <NetworkEdge: a3 b4>}
    
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
    <QuerySet [<NetworkEdge: a3 b3>, <NetworkEdge: root a3>]>
    >>> NetworkEdge.objects.clan(b3)
    <QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b3>, <NetworkEdge: b3 c2>, <NetworkEdge: b3 c1>]>
    >>> NetworkEdge.objects.shortest_path(root, c1)
    <QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b3>, <NetworkEdge: b3 c1>]>
    >>> NetworkEdge.objects.shortest_path(c1, root)
    Traceback (most recent call last):
      File "<input>", line 1, in <module>
        NetworkEdge.objects.shortest_path(c1, root)
      File "/home/runner/pgdagtest/pg/models.py", line 425, in shortest_path
        self.model.objects, ["parent_id", "child_id"], start_node.path_ids_list(end_node)[0]
      File "/home/runner/pgdagtest/pg/models.py", line 313, in path_ids_list
        raise NodeNotReachableException
    pg.models.NodeNotReachableException
    >>> NetworkEdge.objects.shortest_path(c1, root, directional=False)
    <QuerySet [<NetworkEdge: root a3>, <NetworkEdge: a3 b4>, <NetworkEdge: b4 c1>]>



## Credits:

1. [This excellent blog post](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)

