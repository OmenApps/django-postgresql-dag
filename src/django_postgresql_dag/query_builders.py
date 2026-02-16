from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from .debug import _dag_query_collector
from .utils import get_instance_characteristics, validate_weight_field

_PK_TYPE_MAP = {
    "AutoField": "integer",
    "SmallAutoField": "smallint",
    "BigAutoField": "bigint",
    "IntegerField": "integer",
    "SmallIntegerField": "smallint",
    "BigIntegerField": "bigint",
    "UUIDField": "uuid",
    "CharField": "text",
    "SlugField": "text",
    "TextField": "text",
}


class BaseQuery(ABC):
    """Base Query Class."""

    def __init__(
        self,
        instance=None,
        starting_node=None,
        ending_node=None,
        max_depth=None,
        limiting_nodes_set_fk=None,
        limiting_edges_set_fk=None,
        disallowed_nodes_queryset=None,
        disallowed_edges_queryset=None,
        allowed_nodes_queryset=None,
        allowed_edges_queryset=None,
        node_model=None,
        edge_model=None,
    ):
        self.instance = instance
        self.starting_node = starting_node
        self.ending_node = ending_node
        self.max_depth = (
            max_depth if max_depth is not None else getattr(settings, "DJANGO_POSTGRESQL_DAG_MAX_DEPTH", 20)
        )
        self.limiting_nodes_set_fk = limiting_nodes_set_fk
        self.limiting_edges_set_fk = limiting_edges_set_fk
        self.disallowed_nodes_queryset = disallowed_nodes_queryset
        self.disallowed_edges_queryset = disallowed_edges_queryset
        self.allowed_nodes_queryset = allowed_nodes_queryset
        self.allowed_edges_queryset = allowed_edges_queryset

        if self.instance is not None:
            self.query_parameters = {
                "pk": self.instance.pk,
                "max_depth": self.max_depth,
            }
            (
                self.node_model,
                self.edge_model,
                self.instance_type,
            ) = get_instance_characteristics(self.instance)
        elif self.starting_node is not None and self.ending_node is not None:
            self.query_parameters = {
                "starting_node": self.starting_node.pk,
                "ending_node": self.ending_node.pk,
                "max_depth": self.max_depth,
            }
            (
                self.node_model,
                self.edge_model,
                self.instance_type,
            ) = get_instance_characteristics(self.starting_node)
        elif node_model is not None and edge_model is not None:
            self.query_parameters = {"max_depth": self.max_depth}
            self.node_model = node_model
            self.edge_model = edge_model
            self.instance_type = "graph_wide"
        else:
            raise ImproperlyConfigured("Either instance or both starting_node and ending_node are required")

        self.edge_model_table = self.edge_model._meta.db_table
        super().__init__()

    def _get_node_instance(self):
        """Return the node instance to use for method calls like get_foreign_key_field."""
        node = self.instance if self.instance is not None else self.starting_node
        if node is None:
            raise ValueError("Either instance or starting_node must be set")
        return node

    def _get_pk_name(self):
        """Return the primary key field name, working for both instance-based and graph-wide queries."""
        if self.instance is not None:
            return self.instance.get_pk_name()
        if self.starting_node is not None:
            return self.starting_node.get_pk_name()
        return self.node_model._meta.pk.attname

    def _get_pk_type(self):
        """Return the PostgreSQL type name for the primary key field."""
        if self.instance is not None:
            return self.instance.get_pk_type()
        if self.starting_node is not None:
            return self.starting_node.get_pk_type()
        django_pk_type = type(self.node_model._meta.pk).__name__
        return _PK_TYPE_MAP.get(django_pk_type, "integer")

    def _execute_raw_on_edge_model(self, sql_template, format_kwargs):
        """Format the SQL template and return a RawQuerySet on the edge model."""
        formatted_sql = sql_template.format(**format_kwargs)  # nosec B608
        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )
        return self.edge_model.objects.raw(formatted_sql, self.query_parameters)

    def limit_to_nodes_set_fk(self):
        """Limit the search to those nodes which are included in a ForeignKey's node set.

        ToDo: Currently fails in the case that the starting node is not in the
          set of nodes related by the ForeignKey, but is adjacent to one that is.
        """
        if not self.limiting_nodes_set_fk:
            return
        else:
            return self._limit_to_nodes_set_fk()

    @abstractmethod
    def _limit_to_nodes_set_fk(self):
        """Helper method. Override this method in subclasses."""
        return

    def limit_to_edges_set_fk(self):
        """Limit the search to those nodes which connect to edges defined in a ForeignKey's edge set.

        ToDo: Currently fails in the case that the starting node is not in the
          set of nodes related by the ForeignKey, but is adjacent to one that is.
        """
        if not self.limiting_edges_set_fk:
            return
        else:
            return self._limit_to_edges_set_fk()

    @abstractmethod
    def _limit_to_edges_set_fk(self):
        """Helper method. Override this method in subclasses."""
        return

    def disallow_nodes(self):
        """A queryset of Nodes that MUST NOT be included in the query."""
        if not self.disallowed_nodes_queryset:
            return
        else:
            return self._disallow_nodes()

    @abstractmethod
    def _disallow_nodes(self):
        """Helper method. Override this method in subclasses."""
        return

    def disallow_edges(self):
        """A queryset of Edges that MUST NOT be included in the query."""
        if not self.disallowed_edges_queryset:
            return
        else:
            return self._disallow_edges()

    @abstractmethod
    def _disallow_edges(self):
        """Helper method. Override this method in subclasses."""
        return

    def allow_nodes(self):
        """A queryset of Nodes that MAY be included in the query."""
        if not self.allowed_nodes_queryset:
            return
        else:
            return self._allow_nodes()

    @abstractmethod
    def _allow_nodes(self):
        """Helper method. Override this method in subclasses."""
        return

    def allow_edges(self):
        """A queryset of Edges that MAY be included in the query."""
        if not self.allowed_edges_queryset:
            return
        else:
            return self._allow_edges()

    @abstractmethod
    def _allow_edges(self):
        """Helper method. Override this method in subclasses."""
        return

    def _add_filter_clause(self, part_1_clause, part_2_clause, param_name, queryset):
        """Append filter clauses to CTE parts and set the query parameter from a queryset's PKs."""
        if part_1_clause:
            self.where_clauses_part_1 += "\n" + part_1_clause
        if part_2_clause:
            self.where_clauses_part_2 += "\n" + part_2_clause
        self.query_parameters[param_name] = list(queryset.values_list("pk", flat=True))

    @abstractmethod
    def raw_queryset(self):
        """Return the RawQueryset for this query. Should be extended in child classes."""

        # Set the query clauses here, rather than in init so that we don't keep adding to the
        # clauses each time we check/utilize raw_queryset()
        self.where_clauses_part_1 = ""
        self.where_clauses_part_2 = ""

        self.limit_to_nodes_set_fk()
        self.limit_to_edges_set_fk()
        self.disallow_nodes()
        self.disallow_edges()
        self.allow_nodes()
        self.allow_edges()

        return

    def _execute_raw(self, sql_template, format_kwargs):
        """Format the SQL template, optionally record it, and return a RawQuerySet."""
        formatted_sql = sql_template.format(**format_kwargs)  # nosec B608 - format_kwargs are Django model metadata (table/column names), not user input
        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )
        return self.node_model.objects.raw(formatted_sql, self.query_parameters)

    def id_list(self):
        """Return a list of ids in the resulting query."""
        return [item.pk for item in self.raw_queryset()]  # type: ignore[union-attr]

    def __str__(self):
        """Return a string representation of the RawQueryset."""
        return str(self.raw_queryset())

    def __repr__(self):
        """Return a string representation of the RawQueryset."""
        return str(self.raw_queryset())


class _AncestorDescendantEdgeFilterMixin:
    """Shared edge filtering for AncestorQuery and DescendantQuery.

    In these CTEs the anchor aliases the edge table as ``first`` while the
    recursive part references it by its real table name.

    Note: this is a cooperative mixin - attributes come from BaseQuery via MRO.
    """

    def _disallow_edges(self):
        self._add_filter_clause(  # type: ignore[attr-defined]
            "AND first.id <> ALL(%(disallowed_edge_pks)s)",
            f"AND {self.edge_model_table}.id <> ALL(%(disallowed_edge_pks)s)",  # type: ignore[attr-defined]  # nosec B608 - edge_model_table from Django model metadata
            "disallowed_edge_pks",
            self.disallowed_edges_queryset,  # type: ignore[attr-defined]
        )

    def _allow_edges(self):
        self._add_filter_clause(  # type: ignore[attr-defined]
            "AND first.id = ANY(%(allowed_edge_pks)s)",
            f"AND {self.edge_model_table}.id = ANY(%(allowed_edge_pks)s)",  # type: ignore[attr-defined]  # nosec B608 - edge_model_table from Django model metadata
            "allowed_edge_pks",
            self.allowed_edges_queryset,  # type: ignore[attr-defined]
        )


class _PathEdgeFilterMixin:
    """Shared edge filtering for UpwardPathQuery and DownwardPathQuery.

    In path CTEs both the anchor and recursive parts alias the edge table as
    ``first``, so the same clause is appended to both parts.

    Note: this is a cooperative mixin - attributes come from BaseQuery via MRO.
    """

    def _disallow_edges(self):
        clause = "AND first.id <> ALL(%(disallowed_path_edge_pks)s)"
        self._add_filter_clause(clause, clause, "disallowed_path_edge_pks", self.disallowed_edges_queryset)  # type: ignore[attr-defined]

    def _allow_edges(self):
        clause = "AND first.id = ANY(%(allowed_path_edge_pks)s)"
        self._add_filter_clause(clause, clause, "allowed_path_edge_pks", self.allowed_edges_queryset)  # type: ignore[attr-defined]


class AncestorQuery(_AncestorDescendantEdgeFilterMixin, BaseQuery):
    """Ancestor Query Class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.instance:
            raise ImproperlyConfigured("AncestorQuery requires an instance")
        return

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE_1 = """AND second.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        LIMITING_EDGES_SET_FK_CLAUSE_2 = (
            """AND {relationship_table}.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        )

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            self.where_clauses_part_1 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_1.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_2 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_2.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE_1 = """AND first.parent_id <> ALL(%(disallowed_node_pks)s)"""
        DISALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id <> ALL(%(disallowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["disallowed_node_pks"] = list(self.disallowed_nodes_queryset.values_list("pk", flat=True))

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE_1 = """AND first.parent_id = ANY(%(allowed_node_pks)s)"""
        ALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id = ANY(%(allowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["allowed_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.instance is None:
            raise ValueError("instance must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, depth) AS (
            SELECT first.parent_id, 1
                FROM {relationship_table} AS first
                LEFT OUTER JOIN {relationship_table} AS second
                ON first.parent_id = second.child_id
            WHERE first.child_id = %(pk)s
            -- LIMITING_FK_EDGES_CLAUSE_1
            -- DISALLOWED_ANCESTORS_NODES_CLAUSE_1
            -- ALLOWED_ANCESTORS_NODES_CLAUSE_1
            {where_clauses_part_1}
        UNION
            SELECT DISTINCT parent_id, traverse.depth + 1
                FROM traverse
                INNER JOIN {relationship_table}
                ON {relationship_table}.child_id = traverse.{pk_name}
            WHERE 1 = 1
            -- LIMITING_FK_EDGES_CLAUSE_2
            -- DISALLOWED_ANCESTORS_NODES_CLAUSE_2
            -- ALLOWED_ANCESTORS_NODES_CLAUSE_2
            {where_clauses_part_2}
        )
        SELECT {pk_name} FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY {pk_name}
        ORDER BY MAX(depth) DESC, {pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.instance.get_pk_name(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )


class DescendantQuery(_AncestorDescendantEdgeFilterMixin, BaseQuery):
    """Descendant Query Class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.instance:
            raise ImproperlyConfigured("DescendantQuery requires an instance")
        return

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE_1 = """AND second.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        LIMITING_EDGES_SET_FK_CLAUSE_2 = (
            """AND {relationship_table}.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        )

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            self.where_clauses_part_1 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_1.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_2 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_2.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE_1 = """AND first.child_id <> ALL(%(disallowed_node_pks)s)"""
        DISALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.child_id <> ALL(%(disallowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["disallowed_node_pks"] = list(self.disallowed_nodes_queryset.values_list("pk", flat=True))

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE_1 = """AND first.child_id = ANY(%(allowed_node_pks)s)"""
        ALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.child_id = ANY(%(allowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["allowed_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.instance is None:
            raise ValueError("instance must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, depth) AS (
            SELECT first.child_id, 1
                FROM {relationship_table} AS first
                LEFT OUTER JOIN {relationship_table} AS second
                ON first.child_id = second.parent_id
            WHERE first.parent_id = %(pk)s
            {where_clauses_part_1}
        UNION
            SELECT DISTINCT child_id, traverse.depth + 1
                FROM traverse
                INNER JOIN {relationship_table}
                ON {relationship_table}.parent_id = traverse.{pk_name}
            WHERE 1=1
            {where_clauses_part_2}
        )
        SELECT {pk_name} FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY {pk_name}
        ORDER BY MAX(depth), {pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.instance.get_pk_name(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )


class ConnectedGraphQuery(BaseQuery):
    """Queries for the entire graph of nodes connected to the provided instance node."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.instance:
            raise ImproperlyConfigured("ConnectedGraphQuery requires an instance")
        return

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE = """AND edge.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            formatted_clause = LIMITING_EDGES_SET_FK_CLAUSE.format(fk_field_name=fk_field_name)
            self.where_clauses_part_2 += "\n" + formatted_clause
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

    def _disallow_nodes(self):
        self._add_filter_clause(
            None,
            "AND CASE WHEN edge.child_id = traverse.{pk_name} THEN edge.parent_id ELSE edge.child_id END"
            " <> ALL(%(disallowed_node_pks)s)".format(pk_name=self._get_node_instance().get_pk_name()),
            "disallowed_node_pks",
            self.disallowed_nodes_queryset,
        )

    def _disallow_edges(self):
        self._add_filter_clause(
            None,
            "AND edge.id <> ALL(%(disallowed_edge_pks)s)",
            "disallowed_edge_pks",
            self.disallowed_edges_queryset,
        )

    def _allow_nodes(self):
        self._add_filter_clause(
            None,
            "AND CASE WHEN edge.child_id = traverse.{pk_name} THEN edge.parent_id ELSE edge.child_id END"
            " = ANY(%(allowed_node_pks)s)".format(pk_name=self._get_node_instance().get_pk_name()),
            "allowed_node_pks",
            self.allowed_nodes_queryset,
        )

    def _allow_edges(self):
        self._add_filter_clause(
            None,
            "AND edge.id = ANY(%(allowed_edge_pks)s)",
            "allowed_edge_pks",
            self.allowed_edges_queryset,
        )

    def raw_queryset(self):
        if self.instance is None:
            raise ValueError("instance must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, path) AS (
            SELECT %(pk)s::{pk_type}, ARRAY[%(pk)s::{pk_type}]
        UNION ALL
            SELECT
                CASE WHEN edge.child_id = traverse.{pk_name}
                     THEN edge.parent_id ELSE edge.child_id END,
                path || CASE WHEN edge.child_id = traverse.{pk_name}
                             THEN edge.parent_id ELSE edge.child_id END
            FROM traverse
            JOIN {relationship_table} edge
                ON (edge.parent_id = traverse.{pk_name} OR edge.child_id = traverse.{pk_name})
            WHERE CASE WHEN edge.child_id = traverse.{pk_name}
                       THEN edge.parent_id ELSE edge.child_id END <> ALL(path)
            AND array_length(path, 1) < %(max_depth)s
            {where_clauses_part_2}
        )
        SELECT DISTINCT {pk_name} FROM traverse;
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.instance.get_pk_name(),
                "pk_type": self.instance.get_pk_type(),
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )


class UpwardPathQuery(_PathEdgeFilterMixin, BaseQuery):
    """Upward Path Query Class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.starting_node and not self.ending_node:
            raise ImproperlyConfigured("UpwardPathQuery requires a starting_node and ending_node")
        return

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE = """AND first.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            formatted_clause = LIMITING_EDGES_SET_FK_CLAUSE.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_1 += "\n" + formatted_clause
            self.where_clauses_part_2 += "\n" + formatted_clause
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE = """AND first.parent_id <> ALL(%(disallowed_path_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE
        self.query_parameters["disallowed_path_node_pks"] = list(
            self.disallowed_nodes_queryset.values_list("pk", flat=True)
        )

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE = """AND first.parent_id = ANY(%(allowed_path_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE
        self.query_parameters["allowed_path_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.starting_node is None:
            raise ValueError("starting_node must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse(child_id, parent_id, depth, path) AS (
            SELECT
                first.child_id,
                first.parent_id,
                1 AS depth,
                ARRAY[first.child_id] AS path
                FROM {relationship_table} AS first
            WHERE child_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.child_id,
                first.parent_id,
                second.depth + 1 AS depth,
                path || first.child_id AS path
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.child_id = second.parent_id
            AND (first.child_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT
            UNNEST(ARRAY[{pk_name}]) AS {pk_name}
        FROM
            (
            SELECT path || ARRAY[%(ending_node)s]::{pk_type}[], depth FROM traverse
                WHERE parent_id = %(ending_node)s
                AND depth <= %(max_depth)s
                ORDER BY depth, path
                LIMIT 1
        ) AS x({pk_name});
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.starting_node.get_pk_name(),
                "pk_type": self.starting_node.get_pk_type(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )


class DownwardPathQuery(_PathEdgeFilterMixin, BaseQuery):
    """Downward Path Query Class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.starting_node and not self.ending_node:
            raise ImproperlyConfigured("DownwardPathQuery requires a starting_node and ending_node")
        return

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE = """AND first.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            formatted_clause = LIMITING_EDGES_SET_FK_CLAUSE.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_1 += "\n" + formatted_clause
            self.where_clauses_part_2 += "\n" + formatted_clause
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE = """AND first.child_id <> ALL(%(disallowed_path_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE
        self.query_parameters["disallowed_path_node_pks"] = list(
            self.disallowed_nodes_queryset.values_list("pk", flat=True)
        )

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE = """AND first.child_id = ANY(%(allowed_path_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE
        self.query_parameters["allowed_path_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.starting_node is None:
            raise ValueError("starting_node must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse(parent_id, child_id, depth, path) AS (
            SELECT
                first.parent_id,
                first.child_id,
                1 AS depth,
                ARRAY[first.parent_id] AS path
                FROM {relationship_table} AS first
            WHERE parent_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.parent_id,
                first.child_id,
                second.depth + 1 AS depth,
                path || first.parent_id AS path
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.parent_id = second.child_id
            AND (first.parent_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT
            UNNEST(ARRAY[{pk_name}]) AS {pk_name}
        FROM
            (
            SELECT path || ARRAY[%(ending_node)s]::{pk_type}[], depth FROM traverse
                WHERE child_id = %(ending_node)s
                AND depth <= %(max_depth)s
                ORDER BY depth, path
                LIMIT 1
        ) AS x({pk_name});
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.starting_node.get_pk_name(),
                "pk_type": self.starting_node.get_pk_type(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )


class _GraphWideNoFilterMixin:
    """Mixin providing no-op filter methods for graph-wide queries."""

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _disallow_edges(self):
        return

    def _allow_nodes(self):
        return

    def _allow_edges(self):
        return


class AncestorDepthQuery(_AncestorDescendantEdgeFilterMixin, BaseQuery):
    """Ancestor query that returns (pk, depth) tuples."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.instance:
            raise ImproperlyConfigured("AncestorDepthQuery requires an instance")

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE_1 = """AND second.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        LIMITING_EDGES_SET_FK_CLAUSE_2 = (
            """AND {relationship_table}.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        )

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            self.where_clauses_part_1 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_1.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_2 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_2.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE_1 = """AND first.parent_id <> ALL(%(disallowed_node_pks)s)"""
        DISALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id <> ALL(%(disallowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["disallowed_node_pks"] = list(self.disallowed_nodes_queryset.values_list("pk", flat=True))

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE_1 = """AND first.parent_id = ANY(%(allowed_node_pks)s)"""
        ALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id = ANY(%(allowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["allowed_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.instance is None:
            raise ValueError("instance must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, depth) AS (
            SELECT first.parent_id, 1
                FROM {relationship_table} AS first
                LEFT OUTER JOIN {relationship_table} AS second
                ON first.parent_id = second.child_id
            WHERE first.child_id = %(pk)s
            {where_clauses_part_1}
        UNION
            SELECT DISTINCT parent_id, traverse.depth + 1
                FROM traverse
                INNER JOIN {relationship_table}
                ON {relationship_table}.child_id = traverse.{pk_name}
            WHERE 1 = 1
            {where_clauses_part_2}
        )
        SELECT {pk_name}, MAX(depth) AS depth FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY {pk_name}
        ORDER BY MAX(depth) DESC, {pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.instance.get_pk_name(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )

    def depth_list(self):
        """Return list of (pk, depth) tuples."""
        return [(item.pk, item.depth) for item in self.raw_queryset()]


class DescendantDepthQuery(_AncestorDescendantEdgeFilterMixin, BaseQuery):
    """Descendant query that returns (pk, depth) tuples."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.instance:
            raise ImproperlyConfigured("DescendantDepthQuery requires an instance")

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        if self.limiting_edges_set_fk is None:
            raise ValueError("limiting_edges_set_fk must not be None")
        LIMITING_EDGES_SET_FK_CLAUSE_1 = """AND second.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        LIMITING_EDGES_SET_FK_CLAUSE_2 = (
            """AND {relationship_table}.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        )

        fk_field_name = self._get_node_instance().get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            self.where_clauses_part_1 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_1.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_2 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_2.format(
                relationship_table=self.edge_model_table,
                fk_field_name=fk_field_name,
            )
            self.query_parameters["limiting_edges_set_fk_pk"] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):
        if self.disallowed_nodes_queryset is None:
            raise ValueError("disallowed_nodes_queryset must not be None")
        DISALLOWED_NODES_CLAUSE_1 = """AND first.child_id <> ALL(%(disallowed_node_pks)s)"""
        DISALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.child_id <> ALL(%(disallowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["disallowed_node_pks"] = list(self.disallowed_nodes_queryset.values_list("pk", flat=True))

        return

    def _allow_nodes(self):
        if self.allowed_nodes_queryset is None:
            raise ValueError("allowed_nodes_queryset must not be None")
        ALLOWED_NODES_CLAUSE_1 = """AND first.child_id = ANY(%(allowed_node_pks)s)"""
        ALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.child_id = ANY(%(allowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
        )
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
        )
        self.query_parameters["allowed_node_pks"] = list(self.allowed_nodes_queryset.values_list("pk", flat=True))

        return

    def raw_queryset(self):
        if self.instance is None:
            raise ValueError("instance must not be None")
        super().raw_queryset()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, depth) AS (
            SELECT first.child_id, 1
                FROM {relationship_table} AS first
                LEFT OUTER JOIN {relationship_table} AS second
                ON first.child_id = second.parent_id
            WHERE first.parent_id = %(pk)s
            {where_clauses_part_1}
        UNION
            SELECT DISTINCT child_id, traverse.depth + 1
                FROM traverse
                INNER JOIN {relationship_table}
                ON {relationship_table}.parent_id = traverse.{pk_name}
            WHERE 1=1
            {where_clauses_part_2}
        )
        SELECT {pk_name}, MAX(depth) AS depth FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY {pk_name}
        ORDER BY MAX(depth), {pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "relationship_table": self.edge_model_table,
                "pk_name": self.instance.get_pk_name(),
                "where_clauses_part_1": self.where_clauses_part_1,
                "where_clauses_part_2": self.where_clauses_part_2,
            },
        )

    def depth_list(self):
        """Return list of (pk, depth) tuples."""
        return [(item.pk, item.depth) for item in self.raw_queryset()]


class TopologicalSortQuery(_GraphWideNoFilterMixin, BaseQuery):
    """Graph-wide topological sort query."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.instance_type != "graph_wide":
            raise ImproperlyConfigured("TopologicalSortQuery requires node_model and edge_model")

    def raw_queryset(self):
        super().raw_queryset()

        pk_name = self._get_pk_name()

        QUERY = """
        WITH RECURSIVE traverse({pk_name}, depth) AS (
            SELECT DISTINCT e.parent_id, 0
            FROM {edge_table} AS e
            LEFT JOIN {edge_table} AS incoming ON e.parent_id = incoming.child_id
            WHERE incoming.child_id IS NULL
        UNION
            SELECT DISTINCT {edge_table}.child_id, traverse.depth + 1
            FROM traverse
            INNER JOIN {edge_table} ON {edge_table}.parent_id = traverse.{pk_name}
            WHERE traverse.depth < %(max_depth)s
        )
        SELECT {pk_name} FROM traverse
        WHERE depth <= %(max_depth)s
        GROUP BY {pk_name}
        ORDER BY MAX(depth) ASC, {pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "edge_table": self.edge_model_table,
                "pk_name": pk_name,
            },
        )


class LCAQuery(BaseQuery):
    """Lowest Common Ancestor query using two parallel ancestor CTEs."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.starting_node or not self.ending_node:
            raise ImproperlyConfigured("LCAQuery requires starting_node and ending_node")

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _disallow_edges(self):
        return

    def _allow_nodes(self):
        return

    def _allow_edges(self):
        return

    def raw_queryset(self):
        if self.starting_node is None or self.ending_node is None:
            raise ValueError("Both starting_node and ending_node must not be None")
        super().raw_queryset()

        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()

        QUERY = """
        WITH RECURSIVE
        ancestors_a({pk_name}, depth) AS (
            SELECT %(starting_node)s::{pk_type}, 0
        UNION
            SELECT first.parent_id, ancestors_a.depth + 1
            FROM ancestors_a
            INNER JOIN {edge_table} AS first ON first.child_id = ancestors_a.{pk_name}
            WHERE ancestors_a.depth < %(max_depth)s
        ),
        ancestors_b({pk_name}, depth) AS (
            SELECT %(ending_node)s::{pk_type}, 0
        UNION
            SELECT first.parent_id, ancestors_b.depth + 1
            FROM ancestors_b
            INNER JOIN {edge_table} AS first ON first.child_id = ancestors_b.{pk_name}
            WHERE ancestors_b.depth < %(max_depth)s
        ),
        common AS (
            SELECT a.{pk_name}
            FROM ancestors_a a INNER JOIN ancestors_b b ON a.{pk_name} = b.{pk_name}
            GROUP BY a.{pk_name}
        )
        SELECT c.{pk_name} FROM common c
        WHERE NOT EXISTS (
            SELECT 1 FROM {edge_table} e
            INNER JOIN common c2 ON e.child_id = c2.{pk_name}
            WHERE e.parent_id = c.{pk_name}
        )
        ORDER BY c.{pk_name} ASC
        """

        return self._execute_raw(
            QUERY,
            {
                "edge_table": self.edge_model_table,
                "pk_name": pk_name,
                "pk_type": pk_type,
            },
        )


class AllDownwardPathsQuery(_PathEdgeFilterMixin, BaseQuery):
    """Find all paths from starting_node downward to ending_node."""

    def __init__(self, **kwargs):
        self._max_results = kwargs.pop("max_results", None)
        super().__init__(**kwargs)
        if not self.starting_node or not self.ending_node:
            raise ImproperlyConfigured("AllDownwardPathsQuery requires starting_node and ending_node")

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _allow_nodes(self):
        return

    def raw_queryset(self):
        """Not used for this query class -- use path_lists() instead."""
        super().raw_queryset()
        return None

    def path_lists(self):
        """Return list of path lists (each path is a list of PKs)."""
        super().raw_queryset()

        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()

        limit_clause = ""
        if self._max_results is not None:
            self.query_parameters["max_results"] = self._max_results
            limit_clause = "LIMIT %(max_results)s"

        QUERY = """
        WITH RECURSIVE traverse(parent_id, child_id, depth, path) AS (
            SELECT
                first.parent_id,
                first.child_id,
                1 AS depth,
                ARRAY[first.parent_id] AS path
                FROM {relationship_table} AS first
            WHERE parent_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.parent_id,
                first.child_id,
                second.depth + 1 AS depth,
                path || first.parent_id AS path
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.parent_id = second.child_id
            AND (first.parent_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT path || ARRAY[%(ending_node)s]::{pk_type}[] AS path, depth
        FROM traverse
        WHERE child_id = %(ending_node)s AND depth <= %(max_depth)s
        ORDER BY depth ASC
        {limit_clause}
        """

        formatted_sql = QUERY.format(
            relationship_table=self.edge_model_table,
            pk_name=pk_name,
            pk_type=pk_type,
            where_clauses_part_1=self.where_clauses_part_1,
            where_clauses_part_2=self.where_clauses_part_2,
            limit_clause=limit_clause,
        )  # nosec B608

        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )

        with connection.cursor() as cursor:
            cursor.execute(formatted_sql, self.query_parameters)
            return [row[0] for row in cursor.fetchall()]


class AllUpwardPathsQuery(_PathEdgeFilterMixin, BaseQuery):
    """Find all paths from starting_node upward to ending_node."""

    def __init__(self, **kwargs):
        self._max_results = kwargs.pop("max_results", None)
        super().__init__(**kwargs)
        if not self.starting_node or not self.ending_node:
            raise ImproperlyConfigured("AllUpwardPathsQuery requires starting_node and ending_node")

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _allow_nodes(self):
        return

    def raw_queryset(self):
        """Not used for this query class -- use path_lists() instead."""
        super().raw_queryset()
        return None

    def path_lists(self):
        """Return list of path lists (each path is a list of PKs)."""
        super().raw_queryset()

        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()

        limit_clause = ""
        if self._max_results is not None:
            self.query_parameters["max_results"] = self._max_results
            limit_clause = "LIMIT %(max_results)s"

        QUERY = """
        WITH RECURSIVE traverse(child_id, parent_id, depth, path) AS (
            SELECT
                first.child_id,
                first.parent_id,
                1 AS depth,
                ARRAY[first.child_id] AS path
                FROM {relationship_table} AS first
            WHERE child_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.child_id,
                first.parent_id,
                second.depth + 1 AS depth,
                path || first.child_id AS path
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.child_id = second.parent_id
            AND (first.child_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT path || ARRAY[%(ending_node)s]::{pk_type}[] AS path, depth
        FROM traverse
        WHERE parent_id = %(ending_node)s AND depth <= %(max_depth)s
        ORDER BY depth ASC
        {limit_clause}
        """

        formatted_sql = QUERY.format(
            relationship_table=self.edge_model_table,
            pk_name=pk_name,
            pk_type=pk_type,
            where_clauses_part_1=self.where_clauses_part_1,
            where_clauses_part_2=self.where_clauses_part_2,
            limit_clause=limit_clause,
        )  # nosec B608

        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )

        with connection.cursor() as cursor:
            cursor.execute(formatted_sql, self.query_parameters)
            return [row[0] for row in cursor.fetchall()]


class WeightedDownwardPathQuery(_PathEdgeFilterMixin, BaseQuery):
    """Weighted shortest path query traversing downward."""

    def __init__(self, weight_field="weight", **kwargs):
        self._weight_field = weight_field
        super().__init__(**kwargs)
        if not self.starting_node or not self.ending_node:
            raise ImproperlyConfigured("WeightedDownwardPathQuery requires starting_node and ending_node")
        self._weight_column = validate_weight_field(self.edge_model, self._weight_field)

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _allow_nodes(self):
        return

    def result(self):
        """Return WeightedPathResult(nodes=[pk,...], total_weight=N)."""
        from .utils import WeightedPathResult

        super().raw_queryset()

        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()

        QUERY = """
        WITH RECURSIVE traverse(parent_id, child_id, depth, path, total_weight) AS (
            SELECT
                first.parent_id,
                first.child_id,
                1 AS depth,
                ARRAY[first.parent_id] AS path,
                first.{weight_column}::double precision AS total_weight
                FROM {relationship_table} AS first
            WHERE parent_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.parent_id,
                first.child_id,
                second.depth + 1 AS depth,
                path || first.parent_id AS path,
                second.total_weight + first.{weight_column}::double precision AS total_weight
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.parent_id = second.child_id
            AND (first.parent_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT path || ARRAY[%(ending_node)s]::{pk_type}[] AS path, total_weight
        FROM traverse
        WHERE child_id = %(ending_node)s AND depth <= %(max_depth)s
        ORDER BY total_weight ASC
        LIMIT 1
        """

        formatted_sql = QUERY.format(
            relationship_table=self.edge_model_table,
            pk_name=pk_name,
            pk_type=pk_type,
            weight_column=self._weight_column,
            where_clauses_part_1=self.where_clauses_part_1,
            where_clauses_part_2=self.where_clauses_part_2,
        )  # nosec B608 - weight_column from Django model metadata

        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )

        with connection.cursor() as cursor:
            cursor.execute(formatted_sql, self.query_parameters)
            row = cursor.fetchone()
            if row is None:
                return None
            return WeightedPathResult(nodes=row[0], total_weight=row[1])

    def raw_queryset(self):
        """Not directly used -- use result() instead."""
        super().raw_queryset()
        return None


class WeightedUpwardPathQuery(_PathEdgeFilterMixin, BaseQuery):
    """Weighted shortest path query traversing upward."""

    def __init__(self, weight_field="weight", **kwargs):
        self._weight_field = weight_field
        super().__init__(**kwargs)
        if not self.starting_node or not self.ending_node:
            raise ImproperlyConfigured("WeightedUpwardPathQuery requires starting_node and ending_node")
        self._weight_column = validate_weight_field(self.edge_model, self._weight_field)

    def _limit_to_nodes_set_fk(self):
        return

    def _limit_to_edges_set_fk(self):
        return

    def _disallow_nodes(self):
        return

    def _allow_nodes(self):
        return

    def result(self):
        """Return WeightedPathResult(nodes=[pk,...], total_weight=N)."""
        from .utils import WeightedPathResult

        super().raw_queryset()

        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()

        QUERY = """
        WITH RECURSIVE traverse(child_id, parent_id, depth, path, total_weight) AS (
            SELECT
                first.child_id,
                first.parent_id,
                1 AS depth,
                ARRAY[first.child_id] AS path,
                first.{weight_column}::double precision AS total_weight
                FROM {relationship_table} AS first
            WHERE child_id = %(starting_node)s
            {where_clauses_part_1}
        UNION ALL
            SELECT
                first.child_id,
                first.parent_id,
                second.depth + 1 AS depth,
                path || first.child_id AS path,
                second.total_weight + first.{weight_column}::double precision AS total_weight
                FROM {relationship_table} AS first, traverse AS second
            WHERE first.child_id = second.parent_id
            AND (first.child_id <> ALL(second.path))
            {where_clauses_part_2}
        )
        SELECT path || ARRAY[%(ending_node)s]::{pk_type}[] AS path, total_weight
        FROM traverse
        WHERE parent_id = %(ending_node)s AND depth <= %(max_depth)s
        ORDER BY total_weight ASC
        LIMIT 1
        """

        formatted_sql = QUERY.format(
            relationship_table=self.edge_model_table,
            pk_name=pk_name,
            pk_type=pk_type,
            weight_column=self._weight_column,
            where_clauses_part_1=self.where_clauses_part_1,
            where_clauses_part_2=self.where_clauses_part_2,
        )  # nosec B608 - weight_column from Django model metadata

        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )

        with connection.cursor() as cursor:
            cursor.execute(formatted_sql, self.query_parameters)
            row = cursor.fetchone()
            if row is None:
                return None
            return WeightedPathResult(nodes=row[0], total_weight=row[1])

    def raw_queryset(self):
        """Not directly used -- use result() instead."""
        super().raw_queryset()
        return None


class CriticalPathQuery(_GraphWideNoFilterMixin, BaseQuery):
    """Find the longest weighted path through the entire DAG (critical path)."""

    def __init__(self, weight_field=None, **kwargs):
        self._weight_field = weight_field
        super().__init__(**kwargs)
        if self.instance_type != "graph_wide":
            raise ImproperlyConfigured("CriticalPathQuery requires node_model and edge_model")
        if self._weight_field:
            self._weight_column = validate_weight_field(self.edge_model, self._weight_field)
        else:
            self._weight_column = None

    def result(self):
        """Return (path_pks_list, total_weight) or ([], 0) if empty."""
        pk_name = self._get_pk_name()
        pk_type = self._get_pk_type()
        node_table = self.node_model._meta.db_table

        if self._weight_column:
            weight_expression = f"edge.{self._weight_column}::double precision"  # nosec B608
            weight_cast = "double precision"
        else:
            weight_expression = "1::double precision"
            weight_cast = "double precision"

        QUERY = """
        WITH RECURSIVE
        roots AS (
            SELECT {node_table}.{pk_name} FROM {node_table}
            LEFT JOIN {edge_table} ON {edge_table}.child_id = {node_table}.{pk_name}
            WHERE {edge_table}.child_id IS NULL
        ),
        traverse(node_id, depth, path, total_weight) AS (
            SELECT roots.{pk_name}, 0, ARRAY[roots.{pk_name}], 0::{weight_cast}
            FROM roots
        UNION ALL
            SELECT edge.child_id, t.depth + 1, t.path || edge.child_id,
                   t.total_weight + {weight_expression}
            FROM traverse t
            INNER JOIN {edge_table} edge ON edge.parent_id = t.node_id
            WHERE edge.child_id <> ALL(t.path) AND t.depth < %(max_depth)s
        ),
        leaf_paths AS (
            SELECT t.path, t.total_weight FROM traverse t
            LEFT JOIN {edge_table} outgoing ON outgoing.parent_id = t.node_id
            WHERE outgoing.parent_id IS NULL
        ),
        best_path AS (
            SELECT path, total_weight FROM leaf_paths
            ORDER BY total_weight DESC LIMIT 1
        )
        SELECT path, total_weight FROM best_path
        """

        formatted_sql = QUERY.format(
            node_table=node_table,
            edge_table=self.edge_model_table,
            pk_name=pk_name,
            pk_type=pk_type,
            weight_expression=weight_expression,
            weight_cast=weight_cast,
        )  # nosec B608 - all format values from Django model metadata

        collector = _dag_query_collector.get(None)
        if collector is not None:
            collector.append(
                {
                    "query_class": type(self).__name__,
                    "sql": formatted_sql,
                    "params": dict(self.query_parameters),
                }
            )

        with connection.cursor() as cursor:
            cursor.execute(formatted_sql, self.query_parameters)
            row = cursor.fetchone()
            if row is None:
                return ([], 0)
            return (row[0], row[1])

    def raw_queryset(self):
        """Not directly used -- use result() instead."""
        super().raw_queryset()
        return None


class TransitiveReductionQuery(_GraphWideNoFilterMixin, BaseQuery):
    """Find redundant edges that can be removed (transitive reduction)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.instance_type != "graph_wide":
            raise ImproperlyConfigured("TransitiveReductionQuery requires node_model and edge_model")

    def raw_queryset(self):
        super().raw_queryset()

        pk_name = self._get_pk_name()

        QUERY = """
        WITH RECURSIVE
        all_descendants(start_node, current_node, depth, path) AS (
            SELECT parent_id, child_id, 1, ARRAY[parent_id]
            FROM {edge_table}
        UNION ALL
            SELECT ad.start_node, e.child_id, ad.depth + 1, ad.path || e.parent_id
            FROM all_descendants ad
            INNER JOIN {edge_table} e ON e.parent_id = ad.current_node
            WHERE e.parent_id <> ALL(ad.path) AND ad.depth < %(max_depth)s
        ),
        indirect_reachable AS (
            SELECT DISTINCT start_node, current_node
            FROM all_descendants WHERE depth >= 2
        )
        SELECT e.id FROM {edge_table} e
        INNER JOIN indirect_reachable ir
            ON ir.start_node = e.parent_id AND ir.current_node = e.child_id
        """

        return self._execute_raw_on_edge_model(
            QUERY,
            {
                "edge_table": self.edge_model_table,
                "pk_name": pk_name,
            },
        )
