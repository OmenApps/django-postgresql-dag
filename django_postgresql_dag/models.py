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

from django.apps import apps
from django.db import models, connection
from django.db.models import Case, When
from django.core.exceptions import ValidationError

from .exceptions import NodeNotReachableException
from .transformations import *

LIMITING_FK_EDGES_CLAUSE_1 = (
    """AND second.{fk_field_name}_{pk_name} = %(limiting_fk_edges_instance_pk)s"""
)
LIMITING_FK_EDGES_CLAUSE_2 = """AND {relationship_table}.{fk_field_name}_{pk_name} = %(limiting_fk_edges_instance_pk)s"""

LIMITING_FK_NODES_CLAUSE_1 = """"""
LIMITING_FK_NODES_CLAUSE_2 = """"""

# DISALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND second.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
# DISALLOWED_ANCESTORS_NODES_CLAUSE_2 = ("""AND {relationship_table}.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)""")

# DISALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND second.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""  # Used for descendants and downward path
# DISALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""

DISALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND first.parent_{pk_name} <> ALL(%(disallowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
DISALLOWED_ANCESTORS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_{pk_name} <> ALL(%(disallowed_ancestors_node_pks)s)"""

DISALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND first.child_{pk_name} <> ALL(%(disallowed_descendants_node_pks)s)"""  # Used for descendants and downward path
DISALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.child_{pk_name} <> ALL(%(disallowed_descendants_node_pks)s)"""


ALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND first.parent_pk = ANY(%(allowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
ALLOWED_ANCESTORS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_{pk_name} = ANY(%(allowed_ancestors_node_pks)s)"""

ALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND first.child_{pk_name} = ANY(%(allowed_descendants_node_pks)s)"""  # Used for descendants and downward path
ALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.child_{pk_name} = ANY(%(allowed_descendants_node_pks)s)"""

ANCESTORS_QUERY = """
WITH RECURSIVE traverse({pk_name}, depth) AS (
    SELECT first.parent_{pk_name}, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.parent_{pk_name} = second.child_{pk_name}
    WHERE first.child_{pk_name} = %(pk)s
    -- LIMITING_FK_EDGES_CLAUSE_1
    -- DISALLOWED_ANCESTORS_NODES_CLAUSE_1
    -- ALLOWED_ANCESTORS_NODES_CLAUSE_1
    {ancestors_clauses_1}
UNION
    SELECT DISTINCT parent_{pk_name}, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.child_{pk_name} = traverse.{pk_name}
    WHERE 1 = 1
    -- LIMITING_FK_EDGES_CLAUSE_2
    -- DISALLOWED_ANCESTORS_NODES_CLAUSE_2
    -- ALLOWED_ANCESTORS_NODES_CLAUSE_2
    {ancestors_clauses_2}
)
SELECT {pk_name} FROM traverse
WHERE depth <= %(max_depth)s
GROUP BY {pk_name}
ORDER BY MAX(depth) DESC, {pk_name} ASC
"""

DESCENDANTS_QUERY = """
WITH RECURSIVE traverse({pk_name}, depth) AS (
    SELECT first.child_{pk_name}, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.child_{pk_name} = second.parent_{pk_name}
    WHERE first.parent_{pk_name} = %(pk)s
    -- LIMITING_FK_EDGES_CLAUSE_1
    -- DISALLOWED_DESCENDANTS_NODES_CLAUSE_1
    -- ALLOWED_DESCENDANTS_NODES_CLAUSE_1
    {descendants_clauses_1}
UNION
    SELECT DISTINCT child_{pk_name}, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.parent_{pk_name} = traverse.{pk_name}
    WHERE 1=1
    -- LIMITING_FK_EDGES_CLAUSE_2
    -- DISALLOWED_DESCENDANTS_NODES_CLAUSE_2
    -- ALLOWED_DESCENDANTS_NODES_CLAUSE_2
    {descendants_clauses_1}
)
SELECT {pk_name} FROM traverse
WHERE depth <= %(max_depth)s
GROUP BY {pk_name}
ORDER BY MAX(depth), {pk_name} ASC
"""

PATH_LIMITING_FK_EDGES_CLAUSE = (
    """AND first.{fk_field_name}_{pk_name} = %(limiting_fk_edges_instance_pk)s"""
)
PATH_LIMITING_FK_NODES_CLAUSE = """"""

DISALLOWED_UPWARD_PATH_NODES_CLAUSE = (
    """AND second.parent_{pk_name} <> ALL('{disallowed_path_node_pks}')"""
)
DISALLOWED_DOWNWARD_PATH_NODES_CLAUSE = (
    """AND second.child_{pk_name} <> ALL('{disallowed_path_node_pks}')"""
)
ALLOWED_UPWARD_PATH_NODES_CLAUSE = (
    """AND second.parent_{pk_name} = ALL('{allowed_path_node_pks}')"""
)
ALLOWED_DOWNWARD_PATH_NODES_CLAUSE = (
    """AND second.child_{pk_name} = ALL('{allowed_path_node_pks}')"""
)

UPWARD_PATH_QUERY = """
WITH RECURSIVE traverse(child_{pk_name}, parent_{pk_name}, depth, path) AS (
    SELECT
        first.child_{pk_name},
        first.parent_{pk_name},
        1 AS depth,
        ARRAY[first.child_{pk_name}] AS path
        FROM {relationship_table} AS first
    WHERE child_{pk_name} = %(starting_node)s
UNION ALL
    SELECT
        first.child_{pk_name},
        first.parent_{pk_name},
        second.depth + 1 AS depth,
        path || first.child_{pk_name} AS path
        FROM {relationship_table} AS first, traverse AS second
    WHERE first.child_{pk_name} = second.parent_{pk_name}
    AND (first.child_{pk_name} <> ALL(second.path))
    -- PATH_LIMITING_FK_EDGES_CLAUSE
    -- DISALLOWED_UPWARD_PATH_NODES_CLAUSE
    -- ALLOWED_UPWARD_PATH_NODES_CLAUSE
    -- LIMITING_UPWARD_NODES_CLAUSE_1  -- CORRECT?
    {upward_clauses}
)
SELECT 
    UNNEST(ARRAY[{pk_name}]) AS {pk_name}
FROM 
    (
    SELECT path || ARRAY[%(ending_node)s], depth FROM traverse
        WHERE parent_{pk_name} = %(ending_node)s
        AND depth <= %(max_depth)s
        LIMIT 1
) AS x({pk_name});
"""

DOWNWARD_PATH_QUERY = """
WITH RECURSIVE traverse(parent_{pk_name}, child_{pk_name}, depth, path) AS (
    SELECT
        first.parent_{pk_name},
        first.child_{pk_name},
        1 AS depth,
        ARRAY[first.parent_{pk_name}] AS path
        FROM {relationship_table} AS first
    WHERE parent_{pk_name} = %(starting_node)s
UNION ALL
    SELECT
        first.parent_{pk_name},
        first.child_{pk_name},
        second.depth + 1 AS depth,
        path || first.parent_{pk_name} AS path
        FROM {relationship_table} AS first, traverse AS second
    WHERE first.parent_{pk_name} = second.child_{pk_name}
    AND (first.parent_{pk_name} <> ALL(second.path))
    -- PATH_LIMITING_FK_EDGES_CLAUSE
    -- DISALLOWED_DOWNWARD_PATH_NODES_CLAUSE
    -- ALLOWED_DOWNWARD_PATH_NODES_CLAUSE
    -- LIMITING_DOWNWARD_NODES_CLAUSE_1  -- CORRECT?
    {downward_clauses}
)      
SELECT 
    UNNEST(ARRAY[{pk_name}]) AS {pk_name}
FROM 
    (
    SELECT path || ARRAY[%(ending_node)s], depth FROM traverse
        WHERE child_{pk_name} = %(ending_node)s
        AND depth <= %(max_depth)s
        LIMIT 1
) AS x({pk_name});
"""


def node_factory(edge_model, children_null=True, base_model=models.Model):
    edge_model_table = edge_model._meta.db_table

    def get_foreign_key_field(instance=None):
        """
        Provided a model instance and model class, checks if the edge model has a ForeignKey
        field to the model for that instance, and then returns the field name and instance pk.
        """
        if instance is not None:
            for field in edge_model._meta.get_fields():
                if field.related_model is instance._meta.model:
                    # Return the first field that matches
                    return field.name
        return None

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

        def add_child(self, child, **kwargs):
            kwargs.update({"parent": self, "child": child})
            disable_check = kwargs.pop("disable_circular_check", False)
            cls = self.children.through(**kwargs)
            return cls.save(disable_circular_check=disable_check)

        def remove_child(self, child, delete_node=False):
            """Removes the edge connecting this node to child, and optionally deletes the child node as well"""
            if child in self.children.all():
                self.children.through.objects.get(parent=self, child=child).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    child.delete()

        def add_parent(self, parent, *args, **kwargs):
            return parent.add_child(self, **kwargs)

        def remove_parent(self, parent, delete_node=False):
            """Removes the edge connecting this node to parent, and optionally deletes the parent node as well"""
            if parent in self.parents.all():
                parent.children.through.objects.get(parent=parent, child=self).delete()
                if delete_node:
                    # Note: Per django docs:
                    # https://docs.djangoproject.com/en/dev/ref/models/instances/#deleting-objects
                    # This only deletes the object in the database; the Python instance will still
                    # exist and will still have data in its fields.
                    parent.delete()

        def filter_order_pks(self, pks):
            """
            Generates a queryset, based on the current class and the provided pks
            """
            return _filter_order(self.__class__.objects, "pk", pks)

        def get_pk_name(self):
            """Sometimes we set a field other than 'pk' for the primary key.
            This method is used to get the correct primary key field name for the
            model so that raw queries return the correct information."""
            return self._meta.pk.name

        def ancestors_raw(self, max_depth=20, **kwargs):
            ancestors_clauses_1, ancestors_clauses_2 = ("", "")
            query_parameters = {"pk": self.pk, "max_depth": max_depth}

            limiting_fk_nodes_instance = kwargs.get("limiting_fk_nodes_instance", None)
            limiting_fk_edges_instance = kwargs.get("limiting_fk_edges_instance", None)
            disallowed_nodes_queryset = kwargs.get("disallowed_nodes_queryset", None)
            disallowed_edges_queryset = kwargs.get("disallowed_edges_queryset", None)
            allowed_nodes_queryset = kwargs.get("allowed_nodes_queryset", None)
            allowed_edges_queryset = kwargs.get("allowed_edges_queryset", None)

            if limiting_fk_nodes_instance is not None:
                pass  # Not implemented yet

            # Limits the search to nodes that connect to edges defined in a ForeignKey
            # ToDo: Currently fails in the case that the starting node is not in the
            #   set of nodes related by the ForeignKey, but is adjacend to one that is
            if limiting_fk_edges_instance is not None:
                fk_field_name = get_foreign_key_field(limiting_fk_edges_instance)
                if fk_field_name is not None:
                    ancestors_clauses_1 += "\n" + LIMITING_FK_EDGES_CLAUSE_1.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        fk_field_name=fk_field_name,
                    )
                    ancestors_clauses_2 += "\n" + LIMITING_FK_EDGES_CLAUSE_2.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        fk_field_name=fk_field_name,
                    )
                    query_parameters[
                        "limiting_fk_edges_instance_pk"
                    ] = limiting_fk_edges_instance.pk

            # Nodes that MUST NOT be included in the results
            if disallowed_nodes_queryset is not None:
                ancestors_clauses_1 += (
                    "\n"
                    + DISALLOWED_ANCESTORS_NODES_CLAUSE_1.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                ancestors_clauses_2 += (
                    "\n"
                    + DISALLOWED_ANCESTORS_NODES_CLAUSE_2.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                query_parameters["disallowed_ancestors_node_pks"] = str(
                    set(disallowed_nodes_queryset.values_list("pk", flat=True))
                )

            if disallowed_edges_queryset is not None:
                pass  # Not implemented yet

            # Nodes that MAY be included in the results
            if allowed_nodes_queryset is not None:
                ancestors_clauses_1 += "\n" + ALLOWED_ANCESTORS_NODES_CLAUSE_1.format(
                    relationship_table=edge_model_table,
                    pk_name=self.get_pk_name(),
                )
                ancestors_clauses_2 += "\n" + ALLOWED_ANCESTORS_NODES_CLAUSE_2.format(
                    relationship_table=edge_model_table,
                    pk_name=self.get_pk_name(),
                )
                query_parameters["allowed_ancestors_node_pks"] = str(
                    set(allowed_nodes_queryset.values_list("pk", flat=True))
                )

            if allowed_edges_queryset is not None:
                pass  # Not implemented yet

            NodeModel = self._meta.model
            raw_qs = NodeModel.objects.raw(
                ANCESTORS_QUERY.format(
                    relationship_table=edge_model_table,
                    pk_name=self.get_pk_name(),
                    ancestors_clauses_1=ancestors_clauses_1,
                    ancestors_clauses_2=ancestors_clauses_2,
                ),
                query_parameters,
            )
            return raw_qs

        def ancestors(self, **kwargs):
            pks = [item.pk for item in self.ancestors_raw(**kwargs)]
            return self.filter_order_pks(pks)

        def ancestors_count(self):
            # ToDo: Implement
            pass

        def self_and_ancestors(self, **kwargs):
            pks = [self.pk] + [item.pk for item in self.ancestors_raw(**kwargs)][::-1]
            return self.filter_order_pks(pks)

        def ancestors_and_self(self, **kwargs):
            pks = [item.pk for item in self.ancestors_raw(**kwargs)] + [self.pk]
            return self.filter_order_pks(pks)

        def descendants_raw(self, max_depth=20, **kwargs):
            descendants_clauses_1, descendants_clauses_2 = ("", "")
            query_parameters = {"pk": self.pk, "max_depth": max_depth}

            limiting_fk_nodes_instance = kwargs.get("limiting_fk_nodes_instance", None)
            limiting_fk_edges_instance = kwargs.get("limiting_fk_edges_instance", None)
            disallowed_nodes_queryset = kwargs.get("disallowed_nodes_queryset", None)
            disallowed_edges_queryset = kwargs.get("disallowed_edges_queryset", None)
            allowed_nodes_queryset = kwargs.get("allowed_nodes_queryset", None)
            allowed_edges_queryset = kwargs.get("allowed_edges_queryset", None)

            if limiting_fk_nodes_instance is not None:
                pass  # Not implemented yet

            # Limits the search to nodes that connect to edges defined in a ForeignKey
            # ToDo: Currently fails in the case that the starting node is not in the
            #   set of nodes related by the ForeignKey, but is adjacend to one that is
            if limiting_fk_edges_instance is not None:
                fk_field_name = get_foreign_key_field(limiting_fk_edges_instance)
                if fk_field_name is not None:
                    descendants_clauses_1 += "\n" + LIMITING_FK_EDGES_CLAUSE_1.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        fk_field_name=fk_field_name,
                    )
                    descendants_clauses_2 += "\n" + LIMITING_FK_EDGES_CLAUSE_2.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        fk_field_name=fk_field_name,
                    )
                    query_parameters[
                        "limiting_fk_edges_instance_pk"
                    ] = limiting_fk_edges_instance.pk

            # Nodes that MUST NOT be included in the results
            if disallowed_nodes_queryset is not None:
                descendants_clauses_1 += (
                    "\n"
                    + DISALLOWED_DESCENDANTS_NODES_CLAUSE_1.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                descendants_clauses_2 += (
                    "\n"
                    + DISALLOWED_DESCENDANTS_NODES_CLAUSE_2.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                query_parameters["disallowed_downward_node_pks"] = str(
                    set(disallowed_nodes_queryset.values_list("pk", flat=True))
                )

            if disallowed_edges_queryset is not None:
                pass  # Not implemented yet

            # Nodes that MAY be included in the results
            if allowed_nodes_queryset is not None:
                descendants_clauses_1 += (
                    "\n"
                    + ALLOWED_DESCENDANTS_NODES_CLAUSE_1.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                descendants_clauses_2 += (
                    "\n"
                    + ALLOWED_DESCENDANTS_NODES_CLAUSE_2.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                    )
                )
                query_parameters["allowed_descendants_node_pks"] = str(
                    set(allowed_nodes_queryset.values_list("pk", flat=True))
                )

            if allowed_edges_queryset is not None:
                pass  # Not implemented yet

            NodeModel = self._meta.model

            raw_qs = NodeModel.objects.raw(
                DESCENDANTS_QUERY.format(
                    relationship_table=edge_model_table,
                    pk_name=self.get_pk_name(),
                    descendants_clauses_1=descendants_clauses_1,
                    descendants_clauses_2=descendants_clauses_2,
                ),
                query_parameters,
            )
            return raw_qs

        def descendants(self, **kwargs):
            pks = [item.pk for item in self.descendants_raw(**kwargs)]
            return self.filter_order_pks(pks)

        def descendants_count(self):
            # ToDo: Implement
            pass

        def self_and_descendants(self, **kwargs):
            pks = [self.pk] + [item.pk for item in self.descendants_raw(**kwargs)]
            return self.filter_order_pks(pks)

        def descendants_and_self(self, **kwargs):
            pks = [item.pk for item in self.descendants_raw(**kwargs)] + [self.pk]
            return self.filter_order_pks(pks)

        def clan(self, **kwargs):
            """
            Returns a queryset with all ancestors, self, and all descendants
            """
            pks = (
                [item.pk for item in self.ancestors_raw(**kwargs)]
                + [self.pk]
                + [item.pk for item in self.descendants_raw(**kwargs)]
            )
            return self.filter_order_pks(pks)

        def clan_count(self):
            # ToDo: Implement
            pass

        def siblings(self):
            # ToDo: Implement
            pass

        def siblings_count(self):
            # ToDo: Implement
            pass

        def self_and_siblings(self):
            # ToDo: Implement
            pass

        def siblings_and_self(self):
            # ToDo: Implement
            pass

        def descendants_edges(self):
            """
            Returns a queryset of descendants edges

            ToDo: Perform topological sort
            """
            return edge_model.objects.filter(
                parent__in=self.self_and_descendants(),
                child__in=self.self_and_descendants(),
            )

        def ancestors_edges(self):
            """
            Returns a queryset of ancestors edges

            ToDo: Perform topological sort
            """
            return edge_model.objects.filter(
                parent__in=self.self_and_ancestors(),
                child__in=self.self_and_ancestors(),
            )

        def clan_edges(self):
            """
            Returns a queryset of all edges associated with a given node
            """
            return self.ancestors_edges() | self.descendants_edges()

        def path_raw(self, target_node, directional=True, max_depth=20, **kwargs):
            """
            Returns a list of paths from self to target node, optionally in either
            direction. The resulting lists are always sorted from root-side, toward
            leaf-side, regardless of the relative position of starting and ending nodes.
            """

            # ToDo: Implement filters

            if self == target_node:
                return [[self.pk]]

            downward_clauses, upward_clauses = ("", "")
            query_parameters = {
                "starting_node": self.pk,
                "ending_node": target_node.pk,
                "max_depth": max_depth,
            }

            limiting_fk_nodes_instance = kwargs.get("limiting_fk_nodes_instance", None)
            limiting_fk_edges_instance = kwargs.get("limiting_fk_edges_instance", None)
            disallowed_nodes_queryset = kwargs.get("disallowed_nodes_queryset", None)
            disallowed_edges_queryset = kwargs.get("disallowed_edges_queryset", None)
            allowed_nodes_queryset = kwargs.get("allowed_nodes_queryset", None)
            allowed_edges_queryset = kwargs.get("allowed_edges_queryset", None)

            if limiting_fk_nodes_instance is not None:
                pass  # Not implemented yet

            if limiting_fk_edges_instance is not None:
                fk_field_name = get_foreign_key_field(limiting_fk_edges_instance)
                if fk_field_name is not None:
                    downward_clauses += "\n" + PATH_LIMITING_FK_EDGES_CLAUSE.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        fk_field_name=fk_field_name,
                    )
                    query_parameters[
                        "limiting_fk_edges_instance_pk"
                    ] = limiting_fk_edges_instance.pk

            if disallowed_nodes_queryset is not None:
                downward_clauses += "\n" + DISALLOWED_DOWNWARD_PATH_NODES_CLAUSE
                query_parameters["disallowed_path_node_pks"] = str(
                    set(disallowed_nodes_queryset.values_list("pk", flat=True))
                )

            if disallowed_edges_queryset is not None:
                pass  # Not implemented yet

            if allowed_nodes_queryset is not None:
                pass  # Not implemented yet

            if allowed_edges_queryset is not None:
                pass  # Not implemented yet

            NodeModel = self._meta.model

            path = NodeModel.objects.raw(
                DOWNWARD_PATH_QUERY.format(
                    relationship_table=edge_model_table,
                    pk_name=self.get_pk_name(),
                    downward_clauses=downward_clauses,
                ),
                query_parameters,
            )

            if len(list(path)) == 0 and not directional:

                if limiting_fk_nodes_instance is not None:
                    pass  # Not implemented yet

                if limiting_fk_edges_instance is not None:
                    pass  # Not implemented yet

                if limiting_fk_edges_instance is not None:
                    if "fk_field_name" in locals():
                        upward_clauses += "\n" + PATH_LIMITING_FK_EDGES_CLAUSE.format(
                            relationship_table=edge_model_table,
                            pk_name=self.get_pk_name(),
                            fk_field_name=fk_field_name,
                        )

                if disallowed_nodes_queryset is not None:
                    upward_clauses += "\n" + DISALLOWED_UPWARD_PATH_NODES_CLAUSE
                    query_parameters["disallowed_path_node_pks"] = str(
                        set(disallowed_nodes_queryset.values_list("pk", flat=True))
                    )

                if disallowed_edges_queryset is not None:
                    pass  # Not implemented yet

                if allowed_nodes_queryset is not None:
                    pass  # Not implemented yet

                if allowed_edges_queryset is not None:
                    pass  # Not implemented yet

                path = NodeModel.objects.raw(
                    UPWARD_PATH_QUERY.format(
                        relationship_table=edge_model_table,
                        pk_name=self.get_pk_name(),
                        upward_clauses=upward_clauses,
                    ),
                    query_parameters,
                )

            if len(list(path)) == 0:
                raise NodeNotReachableException
            return path

        def path(self, target_node, **kwargs):
            pks = [item.pk for item in self.path_raw(target_node, **kwargs)]
            return self.filter_order_pks(pks)

        def distance(self, target_node, **kwargs):
            """
            Returns the shortest hops count to the target node
            """
            return self.path(target_node, **kwargs).count() - 1

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

        def is_descendant_of(self, target):
            # ToDo: Implement
            pass

        def is_ancestor_of(self, target):
            # ToDo: Implement
            pass

        def is_sibling_of(self, target):
            # ToDo: Implement
            pass

        def node_depth(self):
            # Depth from furthest root
            # ToDo: Implement
            pass

        def entire_graph(self):
            # Gets all nodes connected in any way to this node

            pass

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
            Returns roots nodes, if any
            # ToDo: Modify to use CTE
            """
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
            Returns leaves nodes, if any
            # ToDo: Modify to use CTE
            """
            descendants_tree = self.descendants_tree()
            leaves = set()
            for descendant in descendants_tree:
                leaves.update(descendant._leaves(descendants_tree[descendant]))
            if len(leaves) < 1:
                leaves.add(self)
            return leaves

        @staticmethod
        def circular_checker(parent, child):
            if child in parent.self_and_ancestors():
                raise ValidationError("The object is an ancestor.")

    return Node


class EdgeManager(models.Manager):

    def from_nodes_queryset(self, nodes_queryset):
        """Provided a queryset of nodes, returns all edges where a parent and child
        node are within the queryset of nodes."""
        return _filter_order(
            self.model.objects, ["parent", "child"], nodes_queryset
        )

    def descendants(self, node, **kwargs):
        """
        Returns a queryset of all edges descended from the given node
        """
        return _filter_order(
            self.model.objects, "parent", node.self_and_descendants(**kwargs)
        )

    def ancestors(self, node, **kwargs):
        """
        Returns a queryset of all edges which are ancestors of the given node
        """
        return _filter_order(
            self.model.objects, "child", node.ancestors_and_self(**kwargs)
        )

    def clan(self, node, **kwargs):
        """
        Returns a queryset of all edges for ancestors, self, and descendants
        """
        return self.from_nodes_queryset(node.clan(**kwargs))

    def path(self, start_node, end_node, **kwargs):
        """
        Returns a queryset of all edges for the shortest path from start_node to end_node
        """
        return self.from_nodes_queryset(start_node.path(end_node, **kwargs))

    def validate_route(self, edges, **kwargs):
        """
        Given a list or set of edges, verify that they result in a contiguous route
        """
        # ToDo: Implement
        pass

    def sort(self, edges, **kwargs):
        """
        Given a list or set of edges, sort them from root-side to leaf-side
        """
        # ToDo: Implement
        pass


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
        parent = models.ForeignKey(
            node_model,
            related_name=f"{node_model_name}_child",
            on_delete=models.CASCADE,
        )
        child = models.ForeignKey(
            node_model,
            related_name=f"{node_model_name}_parent",
            on_delete=models.CASCADE,
        )

        objects = EdgeManager()

        class Meta:
            abstract = not concrete

        def save(self, *args, **kwargs):
            if not kwargs.pop("disable_circular_check", False):
                self.parent.__class__.circular_checker(self.parent, self.child)
            super().save(*args, **kwargs)

    return Edge
