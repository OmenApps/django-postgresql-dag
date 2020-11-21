from abc import ABC, abstractmethod

from .transformations import get_instance_characteristics, get_queryset_characteristics

class BaseQuery(ABC):
    """
    Base Query Class
    """

    where_clauses_part_1 = ""
    where_clauses_part_2 = ""

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

        self.NodeModel, self.EdgeModel, self.instance_type = get_instance_characteristics(instance)
        super().__init__()

    @abstractmethod
    def limit_to_nodes_set_fk(self):
        """
        Limits the search to those nodes which are included in a ForeignKey's node set
            ToDo: Currently fails in the case that the starting node is not in the
              set of nodes related by the ForeignKey, but is adjacend to one that is
        """
        if not limiting_nodes_set_fk:
            return ""

    @abstractmethod
    def limit_to_edges_set_fk(self):
        """
        Limits the search to those nodes which connect to edges defined in a ForeignKey's edge set
            ToDo: Currently fails in the case that the starting node is not in the
              set of nodes related by the ForeignKey, but is adjacend to one that is
        """
        if not limiting_edges_set_fk:
            return ""

    @abstractmethod
    def disallow_nodes(self):
        """
        A queryset of Nodes that MUST NOT be included in the query
        """
        if not disallowed_nodes_queryset:
            return ""

    @abstractmethod
    def disallow_edges(self):
        """
        A queryset of Edges that MUST NOT be included in the query
        """
        if not disallowed_edges_queryset:
            return ""

    @abstractmethod
    def allow_nodes(self):
        """
        A queryset of Edges that MAY be included in the query
        """
        if not allowed_nodes_queryset:
            return ""

    @abstractmethod
    def allow_edges(self):
        """
        A queryset of Edges that MAY be included in the query
        """
        if not allowed_edges_queryset:
            return ""

    @abstractmethod
    def output(self): 
        pass


class AncestorQuery(BaseQuery):
    """Ancestor Query Class"""

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
        {ancestors_clauses_1}
    UNION
        SELECT DISTINCT parent_id, traverse.depth + 1
            FROM traverse
            INNER JOIN {relationship_table}
            ON {relationship_table}.child_id = traverse.{pk_name}
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

    def limit_to_nodes_set_fk(self):
        super().limit_to_nodes_set_fk()
        pass

    def limit_to_edges_set_fk(self):
        super().limit_to_edges_set_fk()
        pass

    def disallow_nodes(self):
        super().disallow_nodes()
        pass

    def disallow_edges(self):
        super().disallow_edges()
        pass

    def allow_nodes(self):
        super().allow_nodes()
        pass

    def allow_edges(self):
        super().allow_edges()
        pass

    def get_clause_1(self):
        pass

    def output(self): 
        edge_model_table = self.EdgeModel._meta.db_table

        return NodeModel.objects.raw(
            QUERY.format(
                relationship_table=edge_model_table,
                pk_name=self.instance.get_pk_name(),
                ancestors_clauses_1=ancestors_clauses_1,
                ancestors_clauses_2=ancestors_clauses_2,
            ),
            query_parameters,
        )
