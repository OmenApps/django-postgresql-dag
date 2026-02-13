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

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import rustworkx as rx

    HAS_RUSTWORKX = True
except ImportError:
    HAS_RUSTWORKX = False

__all__ = [
    "_ordered_filter",
    "edges_from_nodes_queryset",
    "model_to_dict",
    "nodes_from_edges_queryset",
    "nx_from_queryset",
    "rx_from_queryset",
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
    if not HAS_NETWORKX:
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

        graph.add_edge(edge.parent.pk, edge.child.pk, **edge_attribute_fields_dict)

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
    if not HAS_RUSTWORKX:
        raise ImportError(
            "rustworkx is required for rx_from_queryset(). "
            "Install it with: pip install django-postgresql-dag[rustworkx]"
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
        graph.add_edge(pk_to_index[edge.parent.pk], pk_to_index[edge.child.pk], edge_data)

    return graph
