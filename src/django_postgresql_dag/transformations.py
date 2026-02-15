"""Functions for transforming RawQuerySet or other outputs of django-postgresql-dag to alternate formats."""

from .utils import (
    _ordered_filter,
    edges_from_nodes_queryset,
    get_queryset_characteristics,
    model_to_dict,
    nodes_from_edges_queryset,
)

try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore[assignment]

HAS_NETWORKX = nx is not None

try:
    import rustworkx as rx
except ImportError:
    rx = None  # type: ignore[assignment]

HAS_RUSTWORKX = rx is not None

__all__ = [
    "_ordered_filter",
    "json_from_queryset",
    "edges_from_nodes_queryset",
    "graph_hash",
    "graphs_are_isomorphic",
    "model_to_dict",
    "nodes_from_edges_queryset",
    "nx_from_queryset",
    "rx_from_queryset",
    "subgraph_hashes",
]


def nx_from_queryset(
    queryset,
    graph_attributes_dict=None,
    node_attribute_fields_list=None,
    edge_attribute_fields_list=None,
    date_strf=None,
    digraph=False,
):
    """Provided a queryset of nodes or edges, returns a NetworkX graph.

    Optionally, the following can be supplied to add attributes to components of the generated graph:
    graph_attributes_dict: A dictionary of attributes to add to the graph itself
    node_attribute_fields_list: a list of strings of field names to be added to nodes
    edge_attribute_fields_list: a list of strings of field names to be added to edges
    date_strf: if any provided fields are date-like, how should they be formatted?
    digraph: bool to determine whether to output a directed or undirected graph
    """
    if nx is None:
        raise ImportError(
            "networkx is required for nx_from_queryset(). "
            "Install it with: pip install django-postgresql-dag[transforms]"
        )

    _NodeModel, _EdgeModel, queryset_type = get_queryset_characteristics(queryset)

    if graph_attributes_dict is None:
        graph_attributes_dict = {}

    if not digraph:
        graph = nx.Graph(**graph_attributes_dict)
    else:
        graph = nx.DiGraph(**graph_attributes_dict)

    if queryset_type == "nodes_queryset":
        nodes_queryset = queryset
        edges_queryset = edges_from_nodes_queryset(nodes_queryset)
    else:
        edges_queryset = queryset
        nodes_queryset = nodes_from_edges_queryset(edges_queryset)

    for node in nodes_queryset:
        if node_attribute_fields_list is not None:
            node_attribute_fields_dict = model_to_dict(node, fields=node_attribute_fields_list, date_strf=date_strf)
        else:
            node_attribute_fields_dict = {}

        graph.add_node(node.pk, **node_attribute_fields_dict)

    for edge in edges_queryset:
        if edge_attribute_fields_list is not None:
            edge_attribute_fields_dict = model_to_dict(edge, fields=edge_attribute_fields_list, date_strf=date_strf)
        else:
            edge_attribute_fields_dict = {}

        graph.add_edge(edge.parent_id, edge.child_id, **edge_attribute_fields_dict)

    return graph


def rx_from_queryset(
    queryset,
    graph_attributes=None,
    node_attribute_fields_list=None,
    edge_attribute_fields_list=None,
    date_strf=None,
    digraph=False,
):
    """Provided a queryset of nodes or edges, returns a rustworkx graph.

    Unlike NetworkX, rustworkx uses integer node indices, so the Django PK is always
    stored in the node data dict under the ``"pk"`` key.

    Optionally, the following can be supplied to add attributes to components of the generated graph:
    graph_attributes: Any Python object to store as ``graph.attrs``
    node_attribute_fields_list: a list of strings of field names to be added to nodes
    edge_attribute_fields_list: a list of strings of field names to be added to edges
    date_strf: if any provided fields are date-like, how should they be formatted?
    digraph: bool to determine whether to output a directed or undirected graph
    """
    if rx is None:
        raise ImportError(
            "rustworkx is required for rx_from_queryset(). "
            "Install it with: pip install django-postgresql-dag[transforms]"
        )

    _NodeModel, _EdgeModel, queryset_type = get_queryset_characteristics(queryset)

    if digraph:
        graph = rx.PyDiGraph(check_cycle=False)
    else:
        graph = rx.PyGraph()

    if graph_attributes is not None:
        graph.attrs = graph_attributes

    if queryset_type == "nodes_queryset":
        nodes_queryset = queryset
        edges_queryset = edges_from_nodes_queryset(nodes_queryset)
    else:
        edges_queryset = queryset
        nodes_queryset = nodes_from_edges_queryset(edges_queryset)

    pk_to_index = {}
    for node in nodes_queryset:
        node_data = {"pk": node.pk}
        if node_attribute_fields_list is not None:
            node_data.update(model_to_dict(node, fields=node_attribute_fields_list, date_strf=date_strf))
        index = graph.add_node(node_data)
        pk_to_index[node.pk] = index

    for edge in edges_queryset:
        if edge_attribute_fields_list is not None:
            edge_data = model_to_dict(edge, fields=edge_attribute_fields_list, date_strf=date_strf)
        else:
            edge_data = {}
        graph.add_edge(pk_to_index[edge.parent_id], pk_to_index[edge.child_id], edge_data)

    return graph


def json_from_queryset(
    queryset,
    graph_attributes=None,
    node_attribute_fields_list=None,
    edge_attribute_fields_list=None,
    date_strf=None,
    digraph=False,
):
    """Builds a rustworkx graph from a queryset and serializes it to JSON using ``rx.node_link_json()``.

    Returns a JSON string in node-link format. All attribute values are stringified
    for JSON compatibility.

    Optionally, the following can be supplied to add attributes to components of the generated graph:
    graph_attributes: Any Python object to store as ``graph.attrs``
    node_attribute_fields_list: a list of strings of field names to be added to nodes
    edge_attribute_fields_list: a list of strings of field names to be added to edges
    date_strf: if any provided fields are date-like, how should they be formatted?
    digraph: bool to determine whether to output a directed or undirected graph
    """
    if rx is None:
        raise ImportError(
            "rustworkx is required for json_from_queryset(). "
            "Install it with: pip install django-postgresql-dag[transforms]"
        )

    graph = rx_from_queryset(
        queryset,
        graph_attributes=graph_attributes,
        node_attribute_fields_list=node_attribute_fields_list,
        edge_attribute_fields_list=edge_attribute_fields_list,
        date_strf=date_strf,
        digraph=digraph,
    )

    def _stringify_dict(data):
        return {str(k): str(v) for k, v in data.items()}

    def _stringify_graph_attrs(attrs):
        if isinstance(attrs, dict):
            return {str(k): str(v) for k, v in attrs.items()}
        return {"attrs": str(attrs)}

    return rx.node_link_json(
        graph,
        node_attrs=_stringify_dict,
        edge_attrs=_stringify_dict,
        graph_attrs=_stringify_graph_attrs,
    )


def graph_hash(
    queryset,
    node_attr=None,
    edge_attr=None,
    node_attr_fields_list=None,
    edge_attr_fields_list=None,
    iterations=3,
    digest_size=16,
):
    """Return a Weisfeiler-Lehman graph hash for the given queryset.

    Uses NetworkX's weisfeiler_lehman_graph_hash. The hash is NOT collision-free.
    """
    if nx is None:
        raise ImportError(
            "networkx is required for graph_hash(). Install it with: pip install django-postgresql-dag[transforms]"
        )

    if node_attr and not node_attr_fields_list:
        node_attr_fields_list = [node_attr]
    if edge_attr and not edge_attr_fields_list:
        edge_attr_fields_list = [edge_attr]

    graph = nx_from_queryset(
        queryset,
        node_attribute_fields_list=node_attr_fields_list,
        edge_attribute_fields_list=edge_attr_fields_list,
        digraph=True,
    )

    return nx.weisfeiler_lehman_graph_hash(
        graph,
        node_attr=node_attr,
        edge_attr=edge_attr,
        iterations=iterations,
        digest_size=digest_size,
    )


def subgraph_hashes(
    queryset,
    node_attr=None,
    edge_attr=None,
    node_attr_fields_list=None,
    edge_attr_fields_list=None,
    iterations=3,
    digest_size=16,
    include_initial_labels=False,
):
    """Return a dict of {node_pk: [hash_str, ...]} for Weisfeiler-Lehman subgraph hashes.

    Requires NetworkX >= 3.3 for weisfeiler_lehman_subgraph_hashes.
    """
    if nx is None:
        raise ImportError(
            "networkx is required for subgraph_hashes(). Install it with: pip install django-postgresql-dag[transforms]"
        )

    if not hasattr(nx, "weisfeiler_lehman_subgraph_hashes"):
        raise ImportError(
            f"weisfeiler_lehman_subgraph_hashes requires NetworkX >= 3.3. Current version: {nx.__version__}"
        )

    if node_attr and not node_attr_fields_list:
        node_attr_fields_list = [node_attr]
    if edge_attr and not edge_attr_fields_list:
        edge_attr_fields_list = [edge_attr]

    graph = nx_from_queryset(
        queryset,
        node_attribute_fields_list=node_attr_fields_list,
        edge_attribute_fields_list=edge_attr_fields_list,
        digraph=True,
    )

    return nx.weisfeiler_lehman_subgraph_hashes(
        graph,
        node_attr=node_attr,
        edge_attr=edge_attr,
        iterations=iterations,
        digest_size=digest_size,
    )


def graphs_are_isomorphic(
    queryset_a,
    queryset_b,
    node_attr=None,
    edge_attr=None,
    node_attr_fields_list=None,
    edge_attr_fields_list=None,
    iterations=3,
    digest_size=16,
):
    """Compare graph hashes of two querysets. Returns True if hashes match.

    Hash equality is necessary but NOT sufficient for true isomorphism.
    """
    hash_a = graph_hash(
        queryset_a,
        node_attr=node_attr,
        edge_attr=edge_attr,
        node_attr_fields_list=node_attr_fields_list,
        edge_attr_fields_list=edge_attr_fields_list,
        iterations=iterations,
        digest_size=digest_size,
    )
    hash_b = graph_hash(
        queryset_b,
        node_attr=node_attr,
        edge_attr=edge_attr,
        node_attr_fields_list=node_attr_fields_list,
        edge_attr_fields_list=edge_attr_fields_list,
        iterations=iterations,
        digest_size=digest_size,
    )
    return hash_a == hash_b
