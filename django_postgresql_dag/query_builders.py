from abc import ABC, abstractmethod

from .transformations import get_instance_characteristics, get_queryset_characteristics

class BaseQuery(ABC):
    """
    Base Query Class
    """

    def __init__(
        self,
        instance,
        max_depth=20,
        limiting_nodes_set_fk=None,
        limiting_edges_set_fk=None,
        disallowed_nodes_queryset=None,
        disallowed_edges_queryset=None,
        allowed_nodes_queryset=None,
        allowed_edges_queryset=None,
    ):
        self.instance = instance
        self.max_depth = max_depth
        self.limiting_nodes_set_fk = limiting_nodes_set_fk
        self.limiting_edges_set_fk = limiting_edges_set_fk
        self.disallowed_nodes_queryset = disallowed_nodes_queryset
        self.disallowed_edges_queryset = disallowed_edges_queryset
        self.allowed_nodes_queryset = allowed_nodes_queryset
        self.allowed_edges_queryset = allowed_edges_queryset

        self.query_parameters = {"pk": self.instance.pk, "max_depth": self.max_depth}
        self.node_model, self.edge_model, self.instance_type = get_instance_characteristics(instance)
        self.edge_model_table = self.edge_model._meta.db_table
        super().__init__()

    def limit_to_nodes_set_fk(self):
        """
        Limits the search to those nodes which are included in a ForeignKey's node set
            ToDo: Currently fails in the case that the starting node is not in the
              set of nodes related by the ForeignKey, but is adjacend to one that is
        """
        if not self.limiting_nodes_set_fk:
            return
        else:
            return self._limit_to_nodes_set_fk()

    @abstractmethod
    def _limit_to_nodes_set_fk(self):
        return

    def limit_to_edges_set_fk(self):
        """
        Limits the search to those nodes which connect to edges defined in a ForeignKey's edge set
            ToDo: Currently fails in the case that the starting node is not in the
              set of nodes related by the ForeignKey, but is adjacend to one that is
        """
        if not self.limiting_edges_set_fk:
            return
        else:
            return self._limit_to_edges_set_fk()

    @abstractmethod
    def _limit_to_edges_set_fk(self):
        return

    def disallow_nodes(self):
        """
        A queryset of Nodes that MUST NOT be included in the query
        """
        if not self.disallowed_nodes_queryset:
            return
        else:
            return self._disallow_nodes()

    @abstractmethod
    def _disallow_nodes(self):
        return

    def disallow_edges(self):
        """
        A queryset of Edges that MUST NOT be included in the query
        """
        if not self.disallowed_edges_queryset:
            return
        else:
            return self._disallow_edges()

    @abstractmethod
    def _disallow_edges(self):
        return

    def allow_nodes(self):
        """
        A queryset of Edges that MAY be included in the query
        """
        if not self.allowed_nodes_queryset:
            return
        else:
            return self._allow_nodes()

    @abstractmethod
    def _allow_nodes(self):
        return

    def allow_edges(self):
        """
        A queryset of Edges that MAY be included in the query
        """
        if not self.allowed_edges_queryset:
            return
        else:
            return self._allow_edges()

    @abstractmethod
    def _allow_edges(self):
        return

    @abstractmethod
    def raw_queryset(self):

        # Set the clases here, rather than in init so that we don't keep adding to the
        # clauses each time we check/utilize raw_queryset()
        self.where_clauses_part_1 = ""
        self.where_clauses_part_2 = ""
        return

    def __str__(self):
        return str(self.raw_queryset())

    def __repr__(self):
        return str(self.raw_queryset())


class AncestorQuery(BaseQuery):
    """Ancestor Query Class"""

    def _limit_to_nodes_set_fk(self):
        # Not yet implemented
        return

    def _limit_to_edges_set_fk(self):

        LIMITING_EDGES_SET_FK_CLAUSE_1 = """AND second.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""
        LIMITING_EDGES_SET_FK_CLAUSE_2 = """AND {relationship_table}.{fk_field_name}_id = %(limiting_edges_set_fk_pk)s"""

        fk_field_name = get_foreign_key_field(fk_instance=self.limiting_edges_set_fk)
        if fk_field_name is not None:
            self.where_clauses_part_1 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_1.format(
                relationship_table=self.edge_model_table,
                pk_name=self.instance.get_pk_name(),
                fk_field_name=fk_field_name,
            )
            self.where_clauses_part_2 += "\n" + LIMITING_EDGES_SET_FK_CLAUSE_2.format(
                relationship_table=self.edge_model_table,
                pk_name=self.instance.get_pk_name(),
                fk_field_name=fk_field_name,
            )
            self.query_parameters[
                "limiting_edges_set_fk_pk"
            ] = self.limiting_edges_set_fk.pk

        return

    def _disallow_nodes(self):

        DISALLOWED_NODES_CLAUSE_1 = """AND first.parent_id <> ALL(%(disallowed_node_pks)s)"""
        DISALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id <> ALL(%(disallowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + DISALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
            pk_name=self.instance.get_pk_name(),
        )
        self.where_clauses_part_2 += "\n" + DISALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
            pk_name=self.instance.get_pk_name(),  
        )
        self.query_parameters["disallowed_node_pks"] = str(
            set(self.disallowed_nodes_queryset.values_list("pk", flat=True))
        )

        return

    def _disallow_edges(self):
        # Not yet implemented

        return

    def _allow_nodes(self):

        ALLOWED_NODES_CLAUSE_1 = """AND first.parent_id = ANY(%(allowed_node_pks)s)"""  # Used for ancestors and upward path
        ALLOWED_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id = ANY(%(allowed_node_pks)s)"""

        self.where_clauses_part_1 += "\n" + ALLOWED_NODES_CLAUSE_1.format(
            relationship_table=self.edge_model_table,
            pk_name=self.instance.get_pk_name(),
        )
        self.where_clauses_part_2 += "\n" + ALLOWED_NODES_CLAUSE_2.format(
            relationship_table=self.edge_model_table,
            pk_name=self.instance.get_pk_name(),
        )
        self.query_parameters["allowed_node_pks"] = str(
            set(self.allowed_nodes_queryset.values_list("pk", flat=True))
        )

        return

    def _allow_edges(self):
        # Not yet implemented

        return

    def raw_queryset(self): 
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

        self.limit_to_nodes_set_fk()
        self.limit_to_edges_set_fk()
        self.disallow_nodes()
        self.disallow_edges()
        self.allow_nodes()
        self.allow_edges()

        return self.node_model.objects.raw(
            QUERY.format(
                relationship_table=self.edge_model_table,
                pk_name=self.instance.get_pk_name(),
                where_clauses_part_1=self.where_clauses_part_1,
                where_clauses_part_2=self.where_clauses_part_2,
            ),
            self.query_parameters,
        )
