LIMITING_FK_EDGES_CLAUSE_1 = (
    """AND second.{fk_field_name}_id = %(limiting_fk_edges_instance_pk)s"""
)
LIMITING_FK_EDGES_CLAUSE_2 = """AND {relationship_table}.{fk_field_name}_id = %(limiting_fk_edges_instance_pk)s"""

LIMITING_FK_NODES_CLAUSE_1 = """"""
LIMITING_FK_NODES_CLAUSE_2 = """"""

# DISALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND second.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
# DISALLOWED_ANCESTORS_NODES_CLAUSE_2 = ("""AND {relationship_table}.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)""")

# DISALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND second.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""  # Used for descendants and downward path
# DISALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""

DISALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND first.parent_id <> ALL(%(disallowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
DISALLOWED_ANCESTORS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id <> ALL(%(disallowed_ancestors_node_pks)s)"""

DISALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND first.child_id <> ALL(%(disallowed_descendants_node_pks)s)"""  # Used for descendants and downward path
DISALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.child_id <> ALL(%(disallowed_descendants_node_pks)s)"""


ALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND first.parent_pk = ANY(%(allowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
ALLOWED_ANCESTORS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_id = ANY(%(allowed_ancestors_node_pks)s)"""

ALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND first.child_id = ANY(%(allowed_descendants_node_pks)s)"""  # Used for descendants and downward path
ALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.child_id = ANY(%(allowed_descendants_node_pks)s)"""

ANCESTORS_QUERY = """
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

DESCENDANTS_QUERY = """
WITH RECURSIVE traverse({pk_name}, depth) AS (
    SELECT first.child_id, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.child_id = second.parent_id
    WHERE first.parent_id = %(pk)s
    -- LIMITING_FK_EDGES_CLAUSE_1
    -- DISALLOWED_DESCENDANTS_NODES_CLAUSE_1
    -- ALLOWED_DESCENDANTS_NODES_CLAUSE_1
    {descendants_clauses_1}
UNION
    SELECT DISTINCT child_id, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.parent_id = traverse.{pk_name}
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
    """AND first.{fk_field_name}_id = %(limiting_fk_edges_instance_pk)s"""
)
PATH_LIMITING_FK_NODES_CLAUSE = """"""

DISALLOWED_UPWARD_PATH_NODES_CLAUSE = (
    """AND second.parent_id <> ALL('{disallowed_path_node_pks}')"""
)
DISALLOWED_DOWNWARD_PATH_NODES_CLAUSE = (
    """AND second.child_id <> ALL('{disallowed_path_node_pks}')"""
)
ALLOWED_UPWARD_PATH_NODES_CLAUSE = (
    """AND second.parent_id = ALL('{allowed_path_node_pks}')"""
)
ALLOWED_DOWNWARD_PATH_NODES_CLAUSE = (
    """AND second.child_id = ALL('{allowed_path_node_pks}')"""
)

UPWARD_PATH_QUERY = """
WITH RECURSIVE traverse(child_id, parent_id, depth, path) AS (
    SELECT
        first.child_id,
        first.parent_id,
        1 AS depth,
        ARRAY[first.child_id] AS path
        FROM {relationship_table} AS first
    WHERE child_id = %(starting_node)s
UNION ALL
    SELECT
        first.child_id,
        first.parent_id,
        second.depth + 1 AS depth,
        path || first.child_id AS path
        FROM {relationship_table} AS first, traverse AS second
    WHERE first.child_id = second.parent_id
    AND (first.child_id <> ALL(second.path))
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
        WHERE parent_id = %(ending_node)s
        AND depth <= %(max_depth)s
        LIMIT 1
) AS x({pk_name});
"""

DOWNWARD_PATH_QUERY = """
WITH RECURSIVE traverse(parent_id, child_id, depth, path) AS (
    SELECT
        first.parent_id,
        first.child_id,
        1 AS depth,
        ARRAY[first.parent_id] AS path
        FROM {relationship_table} AS first
    WHERE parent_id = %(starting_node)s
UNION ALL
    SELECT
        first.parent_id,
        first.child_id,
        second.depth + 1 AS depth,
        path || first.parent_id AS path
        FROM {relationship_table} AS first, traverse AS second
    WHERE first.parent_id = second.child_id
    AND (first.parent_id <> ALL(second.path))
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
        WHERE child_id = %(ending_node)s
        AND depth <= %(max_depth)s
        LIMIT 1
) AS x({pk_name});
"""

CLUSTER_QUERY = """
WITH RECURSIVE traverse(path, last_parent, last_child) AS (
     SELECT ARRAY[id], id, id
     FROM {node_table} WHERE id = %(starting_node)s -- starting node
  UNION ALL
     SELECT tv.path || edge.child_id || edge.parent_id, edge.profile1_id, edge.child_id
     FROM traverse tv
     JOIN {relationship_table} edge
     ON (edge.parent_id = tv.last_child AND NOT path @> array[edge.child_id]) 
        OR (edge.child_id = tv.last_parent AND NOT path @> array[edge.parent_id])
 )
SELECT distinct unnest(path) FROM traverse;
"""

