# Django & Postgresql-based Directed Acyclic Graphs

The main distinguishing factor for this project is that it can retrieve entire
sections of a graph in a single query. The trade off is portability: it uses
Postgres Common Table Expressions (CTE) to achieve this and is therefore not
compatible with other databases.

NOTE: Not all methods which would benefit from CTEs use them yet.
NOTE: This project is a work in progress. While functional, it is not optimized.

Currently provides numerous methods for retrieving nodes, and a few for retrieving edges within the graph.

## Example:

### models.py

    from django.db import models
    from django_postgresql_dag.models import node_factory, edge_factory

    class GroupedEdgeSet(models.Model):
        """Set of NetworkEdges belonging to a specific Groupe
        Serves as the primary 'Grouped' object
        This can be thought of as a "complex edge"
        """

        name = models.CharField(max_length=100)

        class GroupedType(models.TextChoices):
            GROUPED_TYPE_A = "A", _("A")
            GROUPED_TYPE_B = "B", _("B")
            GROUPED_TYPE_C = "C", _("C")

        grouped_type = models.CharField(
            _("Grouped Type"),
            choices=GroupedType.choices,
            default=GroupedType.GROUPED_TYPE_A,
            max_length=20,
            help_text=_("What type of grouping is this?"),
        )


    class NetworkEdge(edge_factory("NetworkNode", concrete=False)):

        name = models.CharField(max_length=100)

        grouped_edge_set = models.ForeignKey(
            GroupedEdgeSet,
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name="grouped_network_edges",
        )

        def __str__(self):
            return self.name

        def save(self, *args, **kwargs):
            self.name = f"{self.parent.name} {self.child.name}"
            super().save(*args, **kwargs)


    class NetworkNode(node_factory(NetworkEdge)):

        name = models.CharField(max_length=100)

        def __str__(self):
            return self.name
            
### Shell

    from myapp.models import GroupedEdgeSet, NetworkNode, NetworkEdge

    root = NetworkNode.objects.create(name="root")

    a1 = NetworkNode.objects.create(name="a1")
    a2 = NetworkNode.objects.create(name="a2")
    a3 = NetworkNode.objects.create(name="a3")

    b1 = NetworkNode.objects.create(name="b1")
    b2 = NetworkNode.objects.create(name="b2")
    b3 = NetworkNode.objects.create(name="b3")
    b4 = NetworkNode.objects.create(name="b4")

    c1 = NetworkNode.objects.create(name="c1")
    c2 = NetworkNode.objects.create(name="c2")

    root.add_child(a1)
    root.add_child(a2)
    a3.add_parent(root)  # Nodes can be added in either direction

    b1.add_parent(a1)
    a1.add_child(b2)
    a2.add_child(b2)
    a3.add_child(b3)
    a3.add_child(b4)

    b3.add_child(c2)
    b3.add_child(c1)
    b4.add_child(c1)


    # Get a couple of the automatically generated edges to work with below
    e1 = NetworkEdge.objects.first()
    e2 = NetworkEdge.objects.last()

    # Work with the graph

    # Descendant methods which return ids
    root.descendant_ids()
    root.self_and_descendant_ids()
    root.descendants_and_self_ids()

    # Descendant methods which return a queryset
    root.descendants()
    root.self_and_descendants()
    root.descendants_and_self()

    # Ancestor methods which return ids
    c1.ancestor_ids()
    c1.ancestor_and_self_ids()
    c1.self_and_ancestor_ids()

    # Ancestor methods which return a queryset
    c1.ancestors()
    c1.ancestors_and_self()
    c1.self_and_ancestors()

    # Get the node's clan (all ancestors, self, and all descendants)
    b3.clan_ids()
    b3.clan()

    # Get all roots or leaves associated with the node
    b3.get_roots()
    b3.get_leaves()

    # Get the nodes at the start or end of an edge
    e1.parent
    e1.child

    e2.parent
    e2.child

    # Edge-specific Manager methods
    NetworkEdge.objects.descendants(b3)
    NetworkEdge.objects.ancestors(b3)
    NetworkEdge.objects.clan(b3)
    NetworkEdge.objects.path(root, c1)


## Credits:

1. [This excellent blog post](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)
2. [django-dag](https://pypi.org/project/django-dag/)
3. [django-dag-postgresql](https://github.com/worsht/django-dag-postgresql)
4. [django-treebeard-dag](https://pypi.org/project/django-treebeard-dag/)

