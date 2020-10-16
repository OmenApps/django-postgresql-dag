"""
A class to model hierarchies of objects following Directed Acyclic Graph structure.

The graph traversal queries use Postgresql's recursive CTEs to fetch an entire tree
of related node ids in a single query. These queries also topologically sort the ids
by generation.

Inspired by:
https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/
https://github.com/elpaso/django-dag
https://github.com/worsht/django-dag-postgresql
https://github.com/stdbrouw/django-treebeard-dag
"""

from django.db import models, connection
from django.db.models import Case, When
from django.core.exceptions import ValidationError


ANCESTOR_QUERY = """
WITH RECURSIVE traverse(id, depth) AS (
    SELECT first.parent_id, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.parent_id = second.child_id
    WHERE first.child_id = %(id)s
UNION
    SELECT DISTINCT parent_id, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.child_id = traverse.id
)
SELECT id FROM traverse
GROUP BY id
ORDER BY MAX(depth) DESC, id ASC
"""

DESCENDANT_QUERY = """
WITH RECURSIVE traverse(id, depth) AS (
    SELECT first.child_id, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.child_id = second.parent_id
    WHERE first.parent_id = %(id)s
UNION
    SELECT DISTINCT child_id, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.parent_id = traverse.id
)
SELECT id FROM traverse
GROUP BY id
ORDER BY MAX(depth), id ASC
"""


class NodeNotReachableException(Exception):
    """
    Exception for node distance and path
    """

    pass


def filter_order(queryset, field_names, values):
    """
    Filters the provided queryset for 'field_name__in values' for each given field_name in [field_names]
    orders results in the same order as provided values

        For instance
            filter_order(self.__class__.objects, "pk", ids)
        returns a queryset of the current class, with instances where the 'pk' field matches an id in ids
    """
    if not isinstance(field_names, list):
        field_names = [field_names]
    case = []
    for pos, value in enumerate(values):
        when_condition = {field_names[0]: value, "then": pos}
        case.append(When(**when_condition))
    order_by = Case(*case)
    filter_condition = {field_name + "__in": values for field_name in field_names}
    return queryset.filter(**filter_condition).order_by(order_by)


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

        class Meta:
            abstract = True

        def add_child(self, descendant, **kwargs):
            kwargs.update({"parent": self, "child": descendant})
            disable_check = kwargs.pop("disable_circular_check", False)
            cls = self.children.through(**kwargs)
            return cls.save(disable_circular_check=disable_check)

        def remove_child(self, descendant):
            self.children.through.objects.get(parent=self, child=descendant).delete()

        def add_parent(self, parent, *args, **kwargs):
            return parent.add_child(self, **kwargs)

        def remove_parent(self, parent):
            parent.children.through.objects.get(parent=parent, child=self).delete()

        def filter_order_ids(self, ids):
            """
            Generates a queryset, based on the current class and the provided ids
            """
            return filter_order(self.__class__.objects, "pk", ids)

        def ancestor_ids(self):
            with connection.cursor() as cursor:
                cursor.execute(
                    ANCESTOR_QUERY.format(relationship_table=edge_model_table),
                    {"id": self.id},
                )
                return [row[0] for row in cursor.fetchall()]

        def ancestor_and_self_ids(self):
            return self.ancestor_ids() + [self.id]

        def self_and_ancestor_ids(self):
            return self.ancestor_and_self_ids()[::-1]

        def ancestors(self):
            return self.filter_order_ids(self.ancestor_ids())

        def ancestors_and_self(self):
            return self.filter_order_ids(self.ancestor_and_self_ids())

        def self_and_ancestors(self):
            return self.ancestors_and_self()[::-1]

        def descendant_ids(self):
            with connection.cursor() as cursor:
                cursor.execute(
                    DESCENDANT_QUERY.format(relationship_table=edge_model_table),
                    {"id": self.id},
                )
                return [row[0] for row in cursor.fetchall()]

        def self_and_descendant_ids(self):
            return [self.id] + self.descendant_ids()

        def descendants_and_self_ids(self):
            return self.self_and_descendant_ids()[::-1]

        def descendants(self):
            return self.filter_order_ids(self.descendant_ids())

        def self_and_descendants(self):
            return self.filter_order_ids(self.self_and_descendant_ids())

        def descendants_and_self(self):
            return self.self_and_descendants()[::-1]

        def clan_ids(self):
            """
            Returns a list of ids with all ancestors, self, and all descendants
            """
            return self.ancestor_ids() + self.self_and_descendant_ids()

        def clan(self):
            """
            Returns a queryset with all ancestors, self, and all descendants
            """
            return self.filter_order_ids(self.clan_ids())

        def descendants_tree(self):
            """
            Returns a tree-like structure with descendants
            # ToDo: Modify to use CTE
            """
            tree = {}
            for child in self.children.all():
                tree[child] = child.descendants_tree()
            return tree

        def ancestors_tree(self):
            """
            Returns a tree-like structure with ancestors
            # ToDo: Modify to use CTE
            """
            tree = {}
            for parent in self.parents.all():
                tree[parent] = parent.ancestors_tree()
            return tree

        def distance(self, target_node):
            """
            Returns the shortest hops count to the target node
            """
            return len(self.path(target_node))

        def path(self, target_node):
            """
            Returns the shortest path
            Only works from root-side toward leaf-side
            # ToDo: Modify to use CTE
            """
            if self == target_node:
                return []
            if target_node in self.children.all():
                return [target_node]
            if target_node in self.descendants():
                path = None
                for child in self.children.all():
                    try:
                        desc_path = child.path(target_node)
                        if not path or len(desc_path) < len(path):
                            path = [child] + desc_path
                    except NodeNotReachableException:
                        pass
            else:
                raise NodeNotReachableException
            return path

        def is_root(self):
            """
            Check if has children and not ancestors
            """
            return bool(self.children.exists() and not self.parents.exists())

        def is_leaf(self):
            """
            Check if has ancestors and not children
            """
            return bool(self.parents.exists() and not self.children.exists())

        def is_island(self):
            """
            Check if has no ancestors nor children
            """
            return bool(not self.children.exists() and not self.parents.exists())

        def _get_roots(self, ancestors_tree):
            """
            Works on objects: no queries
            """
            if not ancestors_tree:
                return set([self])
            roots = set()
            for ancestor in ancestors_tree:
                roots.update(ancestor._get_roots(ancestors_tree[ancestor]))
            return roots

        def get_roots(self):
            """
            Returns roots nodes, if any
            # ToDo: Modify to use CTE
            """
            ancestors_tree = self.ancestors_tree()
            roots = set()
            for ancestor in ancestors_tree:
                roots.update(ancestor._get_roots(ancestors_tree[ancestor]))
            return roots

        def _get_leaves(self, descendants_tree):
            """
            Works on objects: no queries
            """
            if not descendants_tree:
                return set([self])
            leaves = set()
            for descendant in descendants_tree:
                leaves.update(descendant._get_leaves(descendants_tree[descendant]))
            return leaves

        def get_leaves(self):
            """
            Returns leaves nodes, if any
            # ToDo: Modify to use CTE
            """
            descendants_tree = self.descendants_tree()
            leaves = set()
            for descendant in descendants_tree:
                leaves.update(descendant._get_leaves(descendants_tree[descendant]))
            return leaves

        @staticmethod
        def circular_checker(parent, child):
            if child.id in parent.self_and_ancestor_ids():
                raise ValidationError("The object is an ancestor.")

    return Node


class EdgeManager(models.Manager):
    def descendants(self, node):
        """
        Returns a queryset of all edges descended from the given node
        """
        return filter_order(
            self.model.objects, "parent_id", node.self_and_descendant_ids()
        )

    def ancestors(self, node):
        """
        Returns a queryset of all edges which are ancestors of the given node
        """
        return filter_order(
            self.model.objects, "child_id", node.self_and_ancestor_ids()
        )

    def clan(self, node):
        """
        Returns a queryset of all edges for ancestors, self, and descendants
        """
        return filter_order(
            self.model.objects, ["parent_id", "child_id"], node.clan_ids()
        )

    # ToDo: Need additional manager methods, particularly edges from node-to-node


def edge_factory(
    node_model,
    child_to_field="id",
    parent_to_field="id",
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
        parent = models.ForeignKey(
            node_model,
            related_name="%s_child" % node_model_name,
            to_field=parent_to_field,
            on_delete=models.CASCADE,
        )
        child = models.ForeignKey(
            node_model,
            related_name="%s_parent" % node_model_name,
            to_field=child_to_field,
            on_delete=models.CASCADE,
        )

        objects = EdgeManager()

        class Meta:
            abstract = not concrete

        def save(self, *args, **kwargs):
            if not kwargs.pop("disable_circular_check", False):
                self.parent.__class__.circular_checker(self.parent, self.child)
            super(Edge, self).save(*args, **kwargs)

    return Edge