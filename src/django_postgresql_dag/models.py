"""A set of model classes to model hierarchies of objects following Directed Acyclic Graph structure.

The graph traversal queries use Postgresql's recursive CTEs to fetch an entire tree of related node ids in a single
query. These queries also topologically sort the ids by generation.
"""

from collections import defaultdict
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import models

from .exceptions import NodeNotReachableException
from .query_builders import AncestorQuery, ConnectedGraphQuery, DescendantQuery, DownwardPathQuery, UpwardPathQuery
from .utils import _ordered_filter


class NodeManager(models.Manager):
    def roots(self, node=None):
        """Return a Queryset of all root nodes (nodes with no parents) in the Node model.

        If a node instance is specified, returns only the roots for that node.
        """
        if node is not None:
            return node.roots()
        return self.filter(parents__isnull=True)

    def leaves(self, node=None):
        """Return a Queryset of all leaf nodes (nodes with no children) in the Node model.

        If a node instance is specified, returns only the leaves for that node.
        """
        if node is not None:
            return node.leaves()
        return self.filter(children__isnull=True)

    def connected_components(self):
        """Return a list of QuerySets, one per disconnected subgraph."""
        all_pks = set(self.values_list("pk", flat=True))
        components = []
        while all_pks:
            start_pk = next(iter(all_pks))
            start_node = self.get(pk=start_pk)
            component_qs = start_node.connected_graph()
            component_pks = set(component_qs.values_list("pk", flat=True))
            # Include the start node itself (islands may not appear in connected_graph)
            component_pks.add(start_pk)
            components.append(self.filter(pk__in=component_pks))
            all_pks -= component_pks
        return components

def node_factory(edge_model, children_null=True, base_model=models.Model):
    class Node(base_model):
        children = models.ManyToManyField(
            "self",
            blank=children_null,
            symmetrical=False,
            through=edge_model,
            related_name="parents",
        )

        objects = NodeManager()

        class Meta:
            abstract = True

        def get_foreign_key_field(self, fk_instance=None):
            """Provided a model instance, checks if the edge model has a ForeignKey field to the model class.

            Returns the associated field name if found, else None.
            """
            if fk_instance is not None:
                for field in edge_model._meta.get_fields():
                    if field.related_model is fk_instance._meta.model:
                        # Return the first field that matches
                        return field.name
            return None

        def get_pk_name(self):
            """Sometimes we set a field other than 'pk' for the primary key.

            This method is used to get the correct primary key field name for the
            model so that raw queries return the correct information.
            """
            return self._meta.pk.attname

        def get_pk_type(self):
            """The pkid class may be set to a non-default type per-model or across the project.

            This method is used to return the postgres type name for the primary key field so
            that raw queries return the correct information.
            """
            django_pk_type = type(self._meta.pk).__name__

            if django_pk_type == "BigAutoField":
                return "bigint"
            elif django_pk_type == "UUIDField":
                return "uuid"
            else:
                return "integer"

        def _pks_from_raw(self, raw_queryset):
            """Extract primary keys from a raw queryset, preserving order."""
            return [item.pk for item in raw_queryset]

        def ordered_queryset_from_pks(self, pks):
            """Generate a queryset, based on the current class and ordered by the provided pks."""
            return _ordered_filter(type(self).objects, "pk", pks)

        def add_child(self, child, **kwargs):
            """Provided with a Node instance, attaches that instance as a child to the current Node instance."""
            kwargs.update({"parent": self, "child": child})

            disable_circular_check = kwargs.pop("disable_circular_check", False)
            allow_duplicate_edges = kwargs.pop("allow_duplicate_edges", True)

            cls = self.children.through(**kwargs)
            return cls.save(disable_circular_check=disable_circular_check, allow_duplicate_edges=allow_duplicate_edges)

        def remove_child(self, child=None, delete_node=False):
            """Remove the edge connecting this node to child if a child Node instance is provided.

            Otherwise removes the edges connecting to all children. Optionally deletes the child(ren) node(s) as well.
            """
            if child is not None and child in self.children.all():
                self.children.through.objects.filter(parent=self, child=child).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    child.delete()
            else:
                for child in self.children.all():
                    self.children.through.objects.filter(parent=self, child=child).delete()
                    if delete_node:
                        # Note: Per django docs:
                        # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                        # This only deletes the object in the database; the Python instance will still
                        # exist and will still have data in its fields.
                        child.delete()

        def add_parent(self, parent, *args, **kwargs):
            """Provided with a Node instance, attaches the current instance as a child to the provided Node instance."""
            return parent.add_child(self, **kwargs)

        def remove_parent(self, parent=None, delete_node=False):
            """Remove the edge connecting this node to parent if a parent Node instance is provided.

            Otherwise removes the edges connecting to all parents. Optionally deletes the parent node(s) as well.
            """
            if parent is not None and parent in self.parents.all():
                parent.children.through.objects.filter(parent=parent, child=self).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    parent.delete()
            else:
                for parent in self.parents.all():
                    parent.children.through.objects.filter(parent=parent, child=self).delete()
                    if delete_node:
                        # Note: Per django docs:
                        # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                        # This only deletes the object in the database; the Python instance will still
                        # exist and will still have data in its fields.
                        parent.delete()

        def ancestors_raw(self, **kwargs):
            """Return a raw QuerySet of all nodes in connected paths in a rootward direction."""
            return AncestorQuery(instance=self, **kwargs).raw_queryset()

        def ancestors(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a rootward direction."""
            pks = self._pks_from_raw(self.ancestors_raw(**kwargs))
            return self.ordered_queryset_from_pks(pks)

        def ancestors_count(self):
            """Return an integer number representing the total number of ancestor nodes."""
            return self.ancestors().count()

        def self_and_ancestors(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a rootward direction, prepending with self."""
            ancestor_pks = self._pks_from_raw(self.ancestors_raw(**kwargs))
            pks = [self.pk] + ancestor_pks[::-1]
            return self.ordered_queryset_from_pks(pks)

        def ancestors_and_self(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a rootward direction, appending with self."""
            ancestor_pks = self._pks_from_raw(self.ancestors_raw(**kwargs))
            pks = ancestor_pks + [self.pk]
            return self.ordered_queryset_from_pks(pks)

        def descendants_raw(self, **kwargs):
            """Return a raw QuerySet of all nodes in connected paths in a leafward direction."""
            return DescendantQuery(instance=self, **kwargs).raw_queryset()

        def descendants(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a leafward direction."""
            pks = self._pks_from_raw(self.descendants_raw(**kwargs))
            return self.ordered_queryset_from_pks(pks)

        def descendants_count(self):
            """Return an integer number representing the total number of descendant nodes."""
            return self.descendants().count()

        def self_and_descendants(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a leafward direction, prepending with self."""
            descendant_pks = self._pks_from_raw(self.descendants_raw(**kwargs))
            pks = [self.pk] + descendant_pks
            return self.ordered_queryset_from_pks(pks)

        def descendants_and_self(self, **kwargs):
            """Return a QuerySet of all nodes in connected paths in a leafward direction, appending with self."""
            descendant_pks = self._pks_from_raw(self.descendants_raw(**kwargs))
            pks = descendant_pks + [self.pk]
            return self.ordered_queryset_from_pks(pks)

        def clan(self, **kwargs):
            """Return a QuerySet with all ancestors nodes, self, and all descendant nodes."""
            ancestor_pks = self._pks_from_raw(self.ancestors_raw(**kwargs))
            descendant_pks = self._pks_from_raw(self.descendants_raw(**kwargs))
            pks = ancestor_pks + [self.pk] + descendant_pks
            return self.ordered_queryset_from_pks(pks)

        def clan_count(self):
            """Return an integer number representing the total number of clan nodes."""
            return self.clan().count()

        def siblings(self):
            """Return a QuerySet of all nodes that share a parent with this node, excluding self."""
            return self.siblings_with_self().exclude(pk=self.pk)

        def siblings_count(self):
            """Return count of all nodes that share a parent with this node."""
            return self.siblings().count()

        def siblings_with_self(self):
            """Return a QuerySet of all nodes that share a parent with this node and self."""
            return type(self).objects.filter(parents__in=self.parents.all()).distinct()

        def partners(self):
            """Return a QuerySet of all nodes that share a child with this node."""
            return self.partners_with_self().exclude(pk=self.pk)

        def partners_count(self):
            """Return count of all nodes that share a child with this node."""
            return self.partners().count()

        def partners_with_self(self):
            """Return all nodes that share a child with this node and self."""
            return type(self).objects.filter(children__in=self.children.all()).distinct()

        def path_raw(self, ending_node, directional=True, **kwargs):
            """Return shortest path from self to ending node, optionally in either direction.

            The resulting RawQueryset is sorted from root-side, toward
            leaf-side, regardless of the relative position of starting and ending nodes.
            """

            if self == ending_node:
                return [[self.pk]]

            path = DownwardPathQuery(starting_node=self, ending_node=ending_node, **kwargs).raw_queryset()

            if len(list(path)) == 0 and not directional:
                path = UpwardPathQuery(starting_node=self, ending_node=ending_node, **kwargs).raw_queryset()

            if len(list(path)) == 0:
                raise NodeNotReachableException

            return path

        def path_exists(self, ending_node, **kwargs):
            """Given an ending Node instance, returns a boolean determining whether there is a path to it."""
            try:
                return len(list(self.path_raw(ending_node, **kwargs))) >= 1
            except NodeNotReachableException:
                return False

        def path(self, ending_node, **kwargs):
            """Return a QuerySet of the shortest path from self to ending node, optionally in either direction.

            The resulting Queryset is sorted from root-side, toward leaf-side, regardless of the relative position of
            starting and ending nodes.
            """
            pks = self._pks_from_raw(self.path_raw(ending_node, **kwargs))
            return self.ordered_queryset_from_pks(pks)

        def distance(self, ending_node, **kwargs):
            """Return the shortest hops count to the target node."""
            if self is ending_node:
                return 0
            else:
                return self.path(ending_node, **kwargs).count() - 1

        def is_root(self):
            """Return True if the current Node instance has children, but no parents."""
            return bool(self.children.exists() and not self.parents.exists())

        def is_leaf(self):
            """Return True if the current Node instance has parents, but no children."""
            return bool(self.parents.exists() and not self.children.exists())

        def is_island(self):
            """Return True if the current Node instance has no parents nor children."""
            return bool(not self.children.exists() and not self.parents.exists())

        def is_ancestor_of(self, ending_node, **kwargs):
            """Provided an ending_node Node instance, returns True if the current Node instance is an ancestor."""
            try:
                return len(self.path_raw(ending_node, **kwargs)) >= 1
            except NodeNotReachableException:
                return False

        def is_descendant_of(self, ending_node, **kwargs):
            """Provided an ending_node Node instance, returns True if the current Node instance is a descendant."""
            # If self is an ancestor, it cannot also be a descendant.
            # Note: unlike is_ancestor_of, we don't need to catch NodeNotReachableException
            # here because path_raw with directional=False never raises it when a
            # bidirectional path exists.
            if self.is_ancestor_of(ending_node, **kwargs):
                return False
            return len(self.path_raw(ending_node, directional=False, **kwargs)) >= 1

        def is_sibling_of(self, ending_node):
            """Provided an ending_node Node instance, returns True if this node and the ending node share a parent."""
            return ending_node in self.siblings()

        def is_partner_of(self, ending_node):
            """Provided an ending_node Node instance, returns True if this node and the ending node share a child."""
            return ending_node in self.partners()

        def node_depth(self):
            """Return an integer representing the depth of this Node instance from furthest root."""
            from django.db import connection

            pk_name = self.get_pk_name()
            edge_table = edge_model._meta.db_table
            QUERY = """
            WITH RECURSIVE traverse({pk_name}, depth) AS (
                SELECT first.parent_id, 1
                    FROM {edge_table} AS first
                WHERE first.child_id = %s
            UNION
                SELECT DISTINCT {edge_table}.parent_id, traverse.depth + 1
                    FROM traverse
                    INNER JOIN {edge_table}
                    ON {edge_table}.child_id = traverse.{pk_name}
            )
            SELECT COALESCE(MAX(depth), 0) FROM traverse
            """.format(pk_name=pk_name, edge_table=edge_table)
            with connection.cursor() as cursor:
                cursor.execute(QUERY, [self.pk])
                return cursor.fetchone()[0]

        def connected_graph_raw(self, **kwargs):
            """Return a raw QuerySet of all nodes connected in any way to the current Node instance."""
            return ConnectedGraphQuery(instance=self, **kwargs).raw_queryset()

        def connected_graph(self, **kwargs):
            """Return a QuerySet of all nodes connected in any way to the current Node instance."""
            pks = self._pks_from_raw(self.connected_graph_raw(**kwargs))
            return self.ordered_queryset_from_pks(pks)

        def connected_graph_node_count(self, **kwargs):
            """Return the number of nodes in the graph connected in any way to the current Node instance."""
            return len(list(self.connected_graph_raw()))

        def descendants_tree(self):
            """Return a tree-like structure with descendants for the current Node."""
            descendants = list(self.descendants())
            if not descendants:
                return {}
            all_nodes = [self] + descendants
            all_node_pks = {n.pk for n in all_nodes}
            node_map = {n.pk: n for n in all_nodes}
            children_of = defaultdict(list)
            for parent_pk, child_pk in edge_model.objects.filter(
                parent_id__in=all_node_pks, child_id__in=all_node_pks
            ).values_list("parent_id", "child_id"):
                children_of[parent_pk].append(node_map[child_pk])

            def _build(node):
                # Recursively map each child node to its own subtree dict
                return {child: _build(child) for child in children_of.get(node.pk, [])}

            return _build(self)

        def ancestors_tree(self):
            """Return a tree-like structure with ancestors for the current Node."""
            ancestors = list(self.ancestors())
            if not ancestors:
                return {}
            all_nodes = ancestors + [self]
            all_node_pks = {n.pk for n in all_nodes}
            node_map = {n.pk: n for n in all_nodes}
            parents_of = defaultdict(list)
            for parent_pk, child_pk in edge_model.objects.filter(
                parent_id__in=all_node_pks, child_id__in=all_node_pks
            ).values_list("parent_id", "child_id"):
                parents_of[child_pk].append(node_map[parent_pk])

            def _build(node):
                # Recursively map each parent node to its own ancestor subtree dict
                return {parent: _build(parent) for parent in parents_of.get(node.pk, [])}

            return _build(self)

        def roots(self):
            """Return a QuerySet of all root nodes, if any, for the current Node."""
            ancestors = self.ancestors()
            if not ancestors.exists():
                return type(self).objects.filter(pk=self.pk)
            return ancestors.filter(parents=None)

        def leaves(self):
            """Return a QuerySet of all leaf nodes, if any, for the current Node."""
            descendants = self.descendants()
            if not descendants.exists():
                return type(self).objects.filter(pk=self.pk)
            return descendants.filter(children=None)

        @staticmethod
        def _depth_case(field_name, depth_map):
            """Build a Case expression mapping a FK field to its topological position."""
            return models.Case(
                *[models.When(**{field_name: pk, "then": pos}) for pk, pos in depth_map.items()],
                default=999999,
                output_field=models.IntegerField(),
            )

        def _edges_for_ordered_nodes(self, ordered_nodes):
            """Filter and topologically sort edges for a set of ordered nodes."""
            depth_map = {node.pk: idx for idx, node in enumerate(ordered_nodes)}
            return edge_model.objects.filter(
                parent__in=ordered_nodes,
                child__in=ordered_nodes,
            ).order_by(
                self._depth_case("parent_id", depth_map),
                self._depth_case("child_id", depth_map),
            )

        def descendants_edges(self):
            """Return a QuerySet of descendant Edge instances for the current Node.

            Topologically sorted from root-side to leaf-side.
            """
            return self._edges_for_ordered_nodes(list(self.self_and_descendants()))

        def ancestors_edges(self):
            """Return a QuerySet of ancestor Edge instances for the current Node.

            Topologically sorted from root-side to leaf-side.
            """
            return self._edges_for_ordered_nodes(list(self.ancestors_and_self()))

        def clan_edges(self):
            """Return a QuerySet of all Edge instances associated with a given node."""
            return self.ancestors_edges() | self.descendants_edges()

        @staticmethod
        def circular_checker(parent, child):
            if child in parent.self_and_ancestors():
                raise ValidationError("The object is an ancestor.")

        @staticmethod
        def duplicate_edge_checker(parent, child):
            if child in parent.self_and_descendants():
                raise ValidationError("The edge is a duplicate.")

    return Node


class EdgeManager(models.Manager):
    def from_nodes_queryset(self, nodes_queryset):
        """Provided a QuerySet of nodes, returns a QuerySet of all Edge instances within the nodes."""
        return _ordered_filter(self.model.objects, ["parent", "child"], nodes_queryset)

    def descendants(self, node, **kwargs):
        """Return a QuerySet of all Edge instances descended from the given Node instance."""
        return _ordered_filter(self.model.objects, "parent", node.self_and_descendants(**kwargs))

    def ancestors(self, node, **kwargs):
        """Return a QuerySet of all Edge instances which are ancestors of the given Node instance."""
        return _ordered_filter(self.model.objects, "child", node.ancestors_and_self(**kwargs))

    def clan(self, node, **kwargs):
        """Return a QuerySet of all Edge instances for ancestors, self, and descendants."""
        return self.from_nodes_queryset(node.clan(**kwargs))

    def path(self, start_node, end_node, **kwargs):
        """Return a QuerySet of all Edge instances for the shortest path from start_node to end_node."""
        return self.from_nodes_queryset(start_node.path(end_node, **kwargs))

    def validate_route(self, edges, **kwargs):
        """Given a list or set of Edge instances, verify that they result in a contiguous route."""
        edge_list = list(edges)
        if len(edge_list) < 2:
            return True
        # Each edge's child must be the next edge's parent for a contiguous route
        for i in range(len(edge_list) - 1):
            if edge_list[i].child_id != edge_list[i + 1].parent_id:
                return False
        return True

    def sort(self, edges, **kwargs):
        """Given a list or set of Edge instances, sort them from root-side to leaf-side."""
        edge_list = list(edges)
        if len(edge_list) < 2:
            return edge_list
        # Collect all referenced node PKs
        node_pks = set()
        for e in edge_list:
            node_pks.add(e.parent_id)
            node_pks.add(e.child_id)
        # Build depth map: node_pk -> depth from root
        node_model = type(edge_list[0].parent)
        nodes = {n.pk: n for n in node_model.objects.filter(pk__in=node_pks)}
        depth_map = {pk: nodes[pk].node_depth() for pk in node_pks}

        # Sort by parent depth first, then child depth (root-side to leaf-side)
        def edge_sort_key(edge):
            return (depth_map[edge.parent_id], depth_map[edge.child_id])

        return sorted(edge_list, key=edge_sort_key)

    def insert_node(self, edge, node, clone_to_rootside=False, clone_to_leafside=False, pre_save=None, post_save=None):
        """Insert a node into an existing Edge instance.

        Returns a tuple of the newly created rootside_edge (parent to
        the inserted node) and leafside_edge (child to the inserted node).

        Process:
        1. Add a new Edge from the parent Node of the current Edge instance to the provided Node instance,
           optionally cloning properties of the existing Edge.
        2. Add a new Edge from the provided Node instance to the child Node of the current Edge instance,
           optionally cloning properties of the existing Edge.
        3. Remove the original Edge instance.

        The instance will still exist in memory, though not in database
        (https://docs.djangoproject.com/en/3.1/ref/models/instances/#refreshing-objects-from-database).
        Recommend running the following after conducting the deletion:
            `del instancename`

        Cloning will fail if a field has unique=True, so a pre_save function can be passed into this method
        Likewise, a post_save function can be passed in to rebuild relationships. For instance, if you have a `name`
        field that is unique and generated automatically in the model's save() method, you could pass in a the following
        `pre_save` function to clear the name prior to saving the new Edge instance(s):

        def pre_save(new_edge):
            new_edge.name = ""
            return new_edge

        A more complete example, where we have models named NetworkEdge & NetworkNode, and we want to insert a new
        Node (n2) into Edge e1, while copying e1's field properties (except `name`) to the newly created rootside Edge
        instance (n1 to n2) is shown below.

        Original        Final

        n1  o           n1  o
            |                 \
            |                  o n2
            |                 /
        n3  o           n3  o

        ##################################################################################
        from myapp.models import NetworkEdge, NetworkNode

        n1 = NetworkNode.objects.create(name="n1")
        n2 = NetworkNode.objects.create(name="n2")
        n3 = NetworkNode.objects.create(name="n3")

        # Connect n3 to n1
        n1.add_child(n3)

        e1 = NetworkEdge.objects.last()

        # function to clear the `name` field, which is autogenerated and must be unique
        def pre_save(new_edge):
            new_edge.name = ""
            return new_edge

        NetworkEdge.objects.insert_node(e1, n2, clone_to_rootside=True, pre_save=pre_save)
        ##################################################################################
        """

        rootside_edge = None
        leafside_edge = None

        # Attach the root-side edge
        if clone_to_rootside:
            rootside_edge = deepcopy(edge)
            rootside_edge.pk = None
            rootside_edge.parent = edge.parent
            rootside_edge.child = node

            if callable(pre_save):
                rootside_edge = pre_save(rootside_edge)

            rootside_edge.save()

            if callable(post_save):
                rootside_edge = post_save(rootside_edge)

        else:
            edge.parent.add_child(node)

        # Attach the leaf-side edge
        if clone_to_leafside:
            leafside_edge = deepcopy(edge)
            leafside_edge.pk = None
            leafside_edge.parent = node
            leafside_edge.child = edge.child

            if callable(pre_save):
                leafside_edge = pre_save(leafside_edge)

            leafside_edge.save()

            if callable(post_save):
                leafside_edge = post_save(leafside_edge)

        else:
            edge.child.add_parent(node)

        # Remove the original edge in the database. Still remains in memory, though, as noted above.
        edge.delete()
        return rootside_edge, leafside_edge


def edge_factory(
    node_model,
    concrete=True,
    base_model=models.Model,
):
    class Edge(base_model):
        # Get the current model's name for use in related_name
        qualname = locals()["__qualname__"]
        model_name = qualname.rsplit(".", 1)[-1].lower()
        if not model_name.endswith("s"):
            model_name = model_name + "s"

        parent = models.ForeignKey(
            node_model,
            related_name=f"children_{model_name}",
            on_delete=models.CASCADE,
        )
        child = models.ForeignKey(
            node_model,
            related_name=f"parent_{model_name}",
            on_delete=models.CASCADE,
        )

        objects = EdgeManager()

        class Meta:
            abstract = not concrete

        def save(self, *args, **kwargs):
            if not kwargs.pop("disable_circular_check", False):
                self.parent.__class__.circular_checker(self.parent, self.child)

            if not kwargs.pop("allow_duplicate_edges", True):
                self.parent.__class__.duplicate_edge_checker(self.parent, self.child)

            super().save(*args, **kwargs)

    return Edge
