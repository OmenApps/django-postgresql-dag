
# DISALLOWED_ANCESTORS_NODES_CLAUSE_1 = """AND second.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)"""  # Used for ancestors and upward path
# DISALLOWED_ANCESTORS_NODES_CLAUSE_2 = ("""AND {relationship_table}.child_pk <> ALL(%(disallowed_ancestors_node_pks)s)""")

# DISALLOWED_DESCENDANTS_NODES_CLAUSE_1 = """AND second.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""  # Used for descendants and downward path
# DISALLOWED_DESCENDANTS_NODES_CLAUSE_2 = """AND {relationship_table}.parent_pk <> ALL(%(disallowed_descendants_node_pks)s)"""



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

