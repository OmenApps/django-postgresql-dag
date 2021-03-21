"""
A set of model classes to model hierarchies of objects following Directed Acyclic Graph structure.

The graph traversal queries use Postgresql's recursive CTEs to fetch an entire tree of related node ids in a single
query. These queries also topologically sort the ids by generation.
"""

from copy import deepcopy
from django.apps import apps
from django.db import models, connection
from django.db.models import Case, When
from django.core.exceptions import ValidationError

from .exceptions import NodeNotReachableException
from .utils import _ordered_filter
from .query_builders import AncestorQuery, DescendantQuery, UpwardPathQuery, DownwardPathQuery, ConnectedGraphQuery


class NodeManager(models.Manager):
    def roots(self, node=None):
        """
        Returns a Queryset of all root nodes (nodes with no parents) in the Node model. If a node instance is specified,
        returns only the roots for that node.
        """
        if node is not None:
            return node.roots()
        return self.filter(parents__isnull=True)

    def leaves(self, node=None):
        """
        Returns a Queryset of all leaf nodes (nodes with no children) in the Node model. If a node instance is
        specified, returns only the leaves for that node.
        """
        if node is not None:
            return node.leaves()
        return self.filter(children__isnull=True)


def node_factory(edge_model, children_null=True, base_model=models.Model):
    edge_model_table = edge_model._meta.db_table

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
            """
            Provided a model instance, checks if the edge model has a ForeignKey field to the
            model class of that instance, and then returns the associated field name, else None.
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
            model so that raw queries return the correct information."""
            return self._meta.pk.name

        def ordered_queryset_from_pks(self, pks):
            """
            Generates a queryset, based on the current class and ordered by the provided pks
            """
            return _ordered_filter(self.__class__.objects, "pk", pks)

        def add_child(self, child, **kwargs):
            """Provided with a Node instance, attaches that instance as a child to the current Node instance"""
            kwargs.update({"parent": self, "child": child})

            disable_circular_check = kwargs.pop("disable_circular_check", False)
            allow_duplicate_edges = kwargs.pop("allow_duplicate_edges", True)

            cls = self.children.through(**kwargs)
            return cls.save(disable_circular_check=disable_circular_check, allow_duplicate_edges=allow_duplicate_edges)

        def remove_child(self, child, delete_node=False):
            """
            Removes the edge connecting this node to the provided child Node instance, and optionally deletes the child
            node as well
            """
            if child in self.children.all():
                self.children.through.objects.filter(parent=self, child=child).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    child.delete()

        def add_parent(self, parent, *args, **kwargs):
            """Provided with a Node instance, attaches the current instance as a child to the provided Node instance"""
            return parent.add_child(self, **kwargs)

        def remove_parent(self, parent, delete_node=False):
            """Removes the edge connecting this node to parent, and optionally deletes the parent node as well"""
            if parent in self.parents.all():
                parent.children.through.objects.filter(parent=parent, child=self).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    parent.delete()

        def ancestors_raw(self, **kwargs):
            """Returns a raw QuerySet of all nodes in connected paths in a rootward direction"""
            return AncestorQuery(instance=self, **kwargs).raw_queryset()

        def ancestors(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a rootward direction"""
            pks = [item.pk for item in self.ancestors_raw(**kwargs)]
            return self.ordered_queryset_from_pks(pks)

        def ancestors_count(self):
            """Returns an integer number representing the total number of ancestor nodes"""
            return self.ancestors().count()

        def self_and_ancestors(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a rootward direction, prepending with self"""
            pks = [self.pk] + [item.pk for item in self.ancestors_raw(**kwargs)][::-1]
            return self.ordered_queryset_from_pks(pks)

        def ancestors_and_self(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a rootward direction, appending with self"""
            pks = [item.pk for item in self.ancestors_raw(**kwargs)] + [self.pk]
            return self.ordered_queryset_from_pks(pks)

        def descendants_raw(self, **kwargs):
            """Returns a raw QuerySet of all nodes in connected paths in a leafward direction"""
            return DescendantQuery(instance=self, **kwargs).raw_queryset()

        def descendants(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a leafward direction"""
            pks = [item.pk for item in self.descendants_raw(**kwargs)]
            return self.ordered_queryset_from_pks(pks)

        def descendants_count(self):
            """Returns an integer number representing the total number of descendant nodes"""
            return self.descendants().count()

        def self_and_descendants(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a leafward direction, prepending with self"""
            pks = [self.pk] + [item.pk for item in self.descendants_raw(**kwargs)]
            return self.ordered_queryset_from_pks(pks)

        def descendants_and_self(self, **kwargs):
            """Returns a QuerySet of all nodes in connected paths in a leafward direction, appending with self"""
            pks = [item.pk for item in self.descendants_raw(**kwargs)] + [self.pk]
            return self.ordered_queryset_from_pks(pks)

        def clan(self, **kwargs):
            """
            Returns a QuerySet with all ancestors nodes, self, and all descendant nodes
            """
            pks = (
                [item.pk for item in self.ancestors_raw(**kwargs)]
                + [self.pk]
                + [item.pk for item in self.descendants_raw(**kwargs)]
            )
            return self.ordered_queryset_from_pks(pks)

        def clan_count(self):
            """Returns an integer number representing the total number of clan nodes"""
            return self.clan().count()

        def siblings(self):
            """Returns a QuerySet of all nodes that share a parent with this node, excluding self"""
            return self.siblings_with_self().exclude(pk=self.pk)

        def siblings_count(self):
            """Returns count of all nodes that share a parent with this node"""
            return self.siblings().count()

        def siblings_with_self(self):
            """Returns a QuerySet of all nodes that share a parent with this node and self"""
            return self.__class__.objects.filter(parents__in=self.parents.all()).distinct()

        def partners(self):
            """Returns a QuerySet of all nodes that share a child with this node"""
            return self.partners_with_self().exclude(pk=self.pk)

        def partners_count(self):
            # Returns count of all nodes that share a child with this node
            return self.partners().count()

        def partners_with_self(self):
            # Returns all nodes that share a child with this node and self
            return self.__class__.objects.filter(children__in=self.children.all()).distinct()

        def path_raw(self, ending_node, directional=True, **kwargs):
            """
            Returns shortest path from self to ending node, optionally in either
            direction. The resulting RawQueryset is sorted from root-side, toward
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
            """
            Given an ending Node instance, returns a boolean value determining whether there is a path from the current
            Node instance to the ending Node instance
            """
            try:
                return len(list(self.path_raw(ending_node, **kwargs))) >= 1
            except NodeNotReachableException:
                return False

        def path(self, ending_node, **kwargs):
            """
            Returns a QuerySet of the shortest path from self to ending node, optionally in either direction.
            The resulting Queryset is sorted from root-side, toward leaf-side, regardless of the relative position of
            starting and ending nodes.
            """
            pks = [item.pk for item in self.path_raw(ending_node, **kwargs)]
            return self.ordered_queryset_from_pks(pks)

        def distance(self, ending_node, **kwargs):
            """
            Returns the shortest hops count to the target node
            """
            if self is ending_node:
                return 0
            else:
                return self.path(ending_node, **kwargs).count() - 1

        def is_root(self):
            """
            Returns True if the current Node instance has children, but no parents
            """
            return bool(self.children.exists() and not self.parents.exists())

        def is_leaf(self):
            """
            Returns True if the current Node instance has parents, but no children
            """
            return bool(self.parents.exists() and not self.children.exists())

        def is_island(self):
            """
            Returns True if the current Node instance has no parents nor children
            """
            return bool(not self.children.exists() and not self.parents.exists())

        def is_ancestor_of(self, ending_node, **kwargs):
            """
            Provided an ending_node Node instance, returns True if the current Node instance and is an ancestor of the
            provided Node instance
            """
            try:
                return len(self.path_raw(ending_node, **kwargs)) >= 1
            except NodeNotReachableException:
                return False

        def is_descendant_of(self, ending_node, **kwargs):
            """
            Provided an ending_node Node instance, returns True if the current Node instance and is a descendant of the
            provided Node instance
            """
            return (
                not self.is_ancestor_of(ending_node, **kwargs)
                and len(self.path_raw(ending_node, directional=False, **kwargs)) >= 1
            )

        def is_sibling_of(self, ending_node):
            """
            Provided an ending_node Node instance, returns True if the provided Node instance and the current Node
            instance share a parent Node
            """
            return ending_node in self.siblings()

        def is_partner_of(self, ending_node):
            """
            Provided an ending_node Node instance, returns True if the provided Node instance and the current Node
            instance share a child Node
            """
            return ending_node in self.partners()

        def node_depth(self):
            """Returns an integer representing the depth of this Node instance from furthest root"""
            # ToDo: Implement
            pass

        def connected_graph_raw(self, **kwargs):
            """Returns a raw QuerySet of  all nodes connected in any way to the current Node instance"""
            return ConnectedGraphQuery(instance=self, **kwargs).raw_queryset()

        def connected_graph(self, **kwargs):
            """Returns a QuerySet of all nodes connected in any way to the current Node instance"""
            pks = [item.pk for item in self.connected_graph_raw(**kwargs)]
            return self.ordered_queryset_from_pks(pks)

        def descendants_tree(self):
            """
            Returns a tree-like structure with descendants for the current Node
            """
            # ToDo: Modify to use CTE
            tree = {}
            for child in self.children.all():
                tree[child] = child.descendants_tree()
            return tree

        def ancestors_tree(self):
            """
            Returns a tree-like structure with ancestors for the current Node
            """
            # ToDo: Modify to use CTE
            tree = {}
            for parent in self.parents.all():
                tree[parent] = parent.ancestors_tree()
            return tree

        def _roots(self, ancestors_tree):
            """
            Works on objects: no queries
            """
            if not ancestors_tree:
                return set([self])
            roots = set()
            for ancestor in ancestors_tree:
                roots.update(ancestor._roots(ancestors_tree[ancestor]))
            return roots

        def roots(self):
            """
            Returns a QuerySet of all root nodes, if any, for the current Node
            """
            # ToDo: Modify to use CTE
            ancestors_tree = self.ancestors_tree()
            roots = set()
            for ancestor in ancestors_tree:
                roots.update(ancestor._roots(ancestors_tree[ancestor]))
            if len(roots) < 1:
                roots.add(self)
            return roots

        def _leaves(self, descendants_tree):
            """
            Works on objects: no queries
            """
            if not descendants_tree:
                return set([self])
            leaves = set()
            for descendant in descendants_tree:
                leaves.update(descendant._leaves(descendants_tree[descendant]))
            return leaves

        def leaves(self):
            """
            Returns a QuerySet of all leaf nodes, if any, for the current Node
            """
            # ToDo: Modify to use CTE
            descendants_tree = self.descendants_tree()
            leaves = set()
            for descendant in descendants_tree:
                leaves.update(descendant._leaves(descendants_tree[descendant]))
            if len(leaves) < 1:
                leaves.add(self)
            return leaves

        def descendants_edges(self):
            """
            Returns a QuerySet of descendant Edge instances for the current Node
            """
            # ToDo: Perform topological sort
            return edge_model.objects.filter(
                parent__in=self.self_and_descendants(),
                child__in=self.self_and_descendants(),
            )

        def ancestors_edges(self):
            """
            Returns a QuerySet of ancestor Edge instances for the current Node
            """
            # ToDo: Perform topological sort
            return edge_model.objects.filter(
                parent__in=self.self_and_ancestors(),
                child__in=self.self_and_ancestors(),
            )

        def clan_edges(self):
            """
            Returns a QuerySet of all Edge instances associated with a given node
            """
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
        """
        Provided a QuerySet of nodes, returns a QuerySet of all Edge instances where a parent and child Node are within
        the QuerySet of nodes
        """
        return _ordered_filter(self.model.objects, ["parent", "child"], nodes_queryset)

    def descendants(self, node, **kwargs):
        """
        Returns a QuerySet of all Edge instances descended from the given Node instance
        """
        return _ordered_filter(self.model.objects, "parent", node.self_and_descendants(**kwargs))

    def ancestors(self, node, **kwargs):
        """
        Returns a QuerySet of all Edge instances which are ancestors of the given Node instance
        """
        return _ordered_filter(self.model.objects, "child", node.ancestors_and_self(**kwargs))

    def clan(self, node, **kwargs):
        """
        Returns a QuerySet of all Edge instances for ancestors, self, and descendants
        """
        return self.from_nodes_queryset(node.clan(**kwargs))

    def path(self, start_node, end_node, **kwargs):
        """
        Returns a QuerySet of all Edge instances for the shortest path from start_node to end_node
        """
        return self.from_nodes_queryset(start_node.path(end_node, **kwargs))

    def validate_route(self, edges, **kwargs):
        """
        Given a list or set of Edge instances, verify that they result in a contiguous route
        """
        # ToDo: Implement
        pass

    def sort(self, edges, **kwargs):
        """
        Given a list or set of Edge instances, sort them from root-side to leaf-side
        """
        # ToDo: Implement
        pass

    def insert_node(self, edge, node, clone_to_rootside=False, clone_to_leafside=False, pre_save=None, post_save=None):
        """
        Inserts a node into an existing Edge instance. Returns a tuple of the newly created rootside_edge (parent to
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

    if isinstance(node_model, str):
        try:
            node_model_name = node_model.split(".")[1]
        except IndexError:

            node_model_name = node_model
    else:
        node_model_name = node_model._meta.model_name

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
