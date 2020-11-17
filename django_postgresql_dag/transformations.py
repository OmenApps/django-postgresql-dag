"""
Functions for transforming RawQuerySet or other outputs of
django-postgresql-dag to alternate formats.
"""

from django.db.models import Case, When

import networkx as nx
import pandas as pd


def _filter_order(queryset, field_names, values):
    """
    Filters the provided queryset for 'field_name__in values' for each given field_name in [field_names]
    orders results in the same order as provided values

        For instance
            _filter_order(self.__class__.objects, "pk", pks)
        returns a queryset of the current class, with instances where the 'pk' field matches an pk in pks

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


def rawqueryset_to_values_list(rawqueryset):
    """Returns a list of lists of each instance"""
    columns = rawqueryset.columns
    for row in rawqueryset:
        yield tuple(getattr(row, column) for column in columns)


def rawqueryset_to_dataframe(rawqueryset):
    """Retruns a pandas dataframe"""
    return pd.DataFrame(
        rawqueryset_to_values_list(rawqueryset), columns=list(rawqueryset.columns)
    )


def edges_from_nodes_queryset(edge_model, nodes_queryset):
    """Given a QuerySet or RawQuerySet of nodes, returns a queryset of the associated edges"""
    return _filter_order(edge_model.objects, ["parent", "child"], nodes_queryset)


def nodes_from_edges_queryset(node_model, edges_queryset):
    """Given a QuerySet or RawQuerySet of edges, returns a queryset of the associated nodes"""
    nodes_list = (
        _filter_order(
            node_model.objects,
            [
                f"{node_model.__name__}_child",
            ],
            edges_queryset,
        )
        | _filter_order(
            node_model.objects,
            [
                f"{node_model.__name__}_parent",
            ],
            edges_queryset,
        )
    ).values_list("pk")

    return node_model.objects.filter(pk__in=nodes_list)


def nx_from_edges(queryset, fields_array=None):
    """Provided a queryset of edges, builds a NetworkX graph"""
    # ToDo: Implement
    graph = nx.Graph()


def nx_from_nodes(queryset):
    # ToDo: Implement
    pass
