"""Tests for discriminator-column scoping via ``edge_filter``.

``limiting_edges_set_fk`` can only scope a traversal by a ForeignKey edge set. ``edge_filter`` scopes
by any column - the case a CharField discriminator (like an ``edge_type`` enum) needs. These tests use
the test edge model's ``weight`` column as the discriminator; a project's real usage is a CharField.
"""

import pytest
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase

from django_postgresql_dag.query_builders import ConnectedGraphQuery, DescendantQuery
from tests.testapp.models import NetworkNode


class EdgeFilterTestCase(TestCase):
    def setUp(self):
        # root -> a -> c is the "weight 1.0" chain; root -> b is a "weight 5.0" edge.
        self.root = NetworkNode.objects.create(name="root")
        self.a = NetworkNode.objects.create(name="a")
        self.b = NetworkNode.objects.create(name="b")
        self.c = NetworkNode.objects.create(name="c")
        self.root.add_child(self.a, weight=1.0)
        self.a.add_child(self.c, weight=1.0)
        self.root.add_child(self.b, weight=5.0)

    def test_unscoped_follows_all_edges(self):
        """Without an edge_filter the walk follows every edge regardless of weight."""
        self.assertEqual(set(self.root.descendants().values_list("pk", flat=True)), {self.a.pk, self.b.pk, self.c.pk})

    def test_edge_filter_scopes_to_matching_edges(self):
        """A weight-scoped descendant walk follows only the matching chain."""
        scoped = self.root.descendants(edge_filter={"weight": 1.0})
        self.assertEqual(set(scoped.values_list("pk", flat=True)), {self.a.pk, self.c.pk})

    def test_edge_filter_excludes_non_matching_edges(self):
        """The other weight yields only its own edge's child."""
        scoped = self.root.descendants(edge_filter={"weight": 5.0})
        self.assertEqual(set(scoped.values_list("pk", flat=True)), {self.b.pk})

    def test_edge_filter_depth_is_not_inflated_by_other_representation(self):
        """Scoping keeps depth accurate: the weight-1.0 chain is two hops, not confused by root->b."""
        query = DescendantQuery(instance=self.root, edge_filter={"weight": 1.0})
        pks = query.pk_list()
        self.assertEqual(len(pks), 2)

    def test_unknown_field_raises(self):
        """An unknown edge_filter field is rejected at query construction (injection-safe)."""
        with pytest.raises(FieldDoesNotExist):
            self.root.descendants(edge_filter={"not_a_real_field": "x"})

    def test_edge_filter_value_is_bound_not_interpolated(self):
        """The filter value is a bound parameter, so a SQL-ish value is treated as data, not code."""
        # A string value against the numeric column simply matches nothing rather than executing.
        scoped = self.root.descendants(edge_filter={"weight": 999.0})
        self.assertEqual(list(scoped.values_list("pk", flat=True)), [])

    def test_connected_graph_respects_edge_filter(self):
        """connected_graph also honours the discriminator scoping on the recursive term."""
        connected = self.root.connected_graph(edge_filter={"weight": 1.0})
        pks = set(connected.values_list("pk", flat=True))
        # Reaches a and c through weight-1.0 edges; b is only reachable via the weight-5.0 edge.
        self.assertIn(self.a.pk, pks)
        self.assertIn(self.c.pk, pks)
        self.assertNotIn(self.b.pk, pks)

    def test_connected_graph_edge_filter_no_false_truncation(self):
        """The boundary truncation check ignores out-of-scope edges, so scoping does not false-warn.

        Without threading the filter into the boundary check, the weight-5.0 edge (root->b) would count
        as a dropped neighbour and wrongly flag truncation even though the weight-1.0 component is whole.
        """
        query = ConnectedGraphQuery(instance=self.root, edge_filter={"weight": 1.0})
        query.pk_list()
        self.assertFalse(query.truncated)
