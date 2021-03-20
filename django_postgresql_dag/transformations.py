"""
Functions for transforming RawQuerySet or other outputs of
django-postgresql-dag to alternate formats.
"""

import networkx as nx
import pandas as pd

from .utils import (
    _ordered_filter,
    get_queryset_characteristics,
    model_to_dict,
    edges_from_nodes_queryset,
    nodes_from_edges_queryset,
)


def nx_from_queryset(
    queryset,
    graph_attributes_dict=None,
    node_attribute_fields_list=None,
    edge_attribute_fields_list=None,
    date_strf=None,
    digraph=False,
):
    """
    Provided a queryset of nodes or edges, returns a NetworkX graph

    Optionally, the following can be supplied to add attributes to components of the generated graph:
    graph_attributes_dict: A dictionary of attributes to add to the graph itself
    node_attribute_fields_list: a list of strings of field names to be added to nodes
    edge_attribute_fields_list: a list of strings of field names to be added to edges
    date_strf: if any provided fields are date-like, how should they be formatted?
    digraph: bool to determine whether to output a directed or undirected graph
    """
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
