"""Tests for the max_depth truncation signal on ancestor/descendant/connected-graph walks.

A long serial chain (the shape an irrigation lateral takes) is the case where the default
``max_depth`` silently drops everything past the ceiling. These tests prove that a high ceiling
returns the whole chain, and that hitting the ceiling now sets ``query.truncated`` and logs a
warning instead of failing quietly.
"""

from django.test import TestCase
from django.test.utils import override_settings

from django_postgresql_dag.query_builders import (
    AncestorQuery,
    ConnectedGraphQuery,
    DescendantQuery,
)
from tests.testapp.models import NetworkEdge, NetworkNode


class SerialChainFixtureMixin:
    """Build a straight chain head -> n1 -> n2 -> ... of ``CHAIN_LENGTH`` nodes."""

    CHAIN_LENGTH = 30

    def setUp(self):
        self.nodes = [NetworkNode.objects.create(name=f"n{i}") for i in range(self.CHAIN_LENGTH)]
        for parent, child in zip(self.nodes, self.nodes[1:]):
            # No cycle is possible in a straight chain, so skip the ancestor walk during construction.
            parent.add_child(child, disable_circular_check=True)
        self.head = self.nodes[0]
        self.tail = self.nodes[-1]


class TruncationTestCase(SerialChainFixtureMixin, TestCase):
    def test_high_max_depth_returns_whole_chain(self):
        """A ceiling above the chain length returns every node and does not flag truncation."""
        query = DescendantQuery(instance=self.head, max_depth=1000)
        pks = query.pk_list()
        self.assertEqual(len(pks), self.CHAIN_LENGTH - 1)
        self.assertFalse(query.truncated)

    def test_descendants_helper_returns_whole_chain_with_high_ceiling(self):
        """The node method returns the full downstream chain when the ceiling is high enough."""
        self.assertEqual(self.head.descendants(max_depth=1000).count(), self.CHAIN_LENGTH - 1)

    def test_ancestors_return_whole_chain_with_high_ceiling(self):
        """The full upstream chain is returned when the ceiling clears the chain length."""
        query = AncestorQuery(instance=self.tail, max_depth=1000)
        pks = query.pk_list()
        self.assertEqual(len(pks), self.CHAIN_LENGTH - 1)
        self.assertFalse(query.truncated)

    def test_low_max_depth_truncates_and_flags(self):
        """A ceiling below the chain length drops rows past it and sets the truncated flag."""
        query = DescendantQuery(instance=self.head, max_depth=10)
        pks = query.pk_list()
        self.assertEqual(len(pks), 10)
        self.assertTrue(query.truncated)

    def test_low_max_depth_logs_warning(self):
        """Hitting the ceiling logs a truncation warning rather than failing silently."""
        query = DescendantQuery(instance=self.head, max_depth=10)
        with self.assertLogs("django_postgresql_dag", level="WARNING") as captured:
            query.pk_list()
        self.assertTrue(any("truncated" in message for message in captured.output))

    def test_ancestor_low_max_depth_truncates_and_flags(self):
        """The ancestor walk flags truncation the same way when the ceiling is too low."""
        query = AncestorQuery(instance=self.tail, max_depth=10)
        pks = query.pk_list()
        self.assertEqual(len(pks), 10)
        self.assertTrue(query.truncated)

    def test_connected_graph_low_max_depth_flags(self):
        """A short ceiling on the connected-graph walk sets the truncated flag."""
        query = ConnectedGraphQuery(instance=self.head, max_depth=10)
        query.pk_list()
        self.assertTrue(query.truncated)

    def test_connected_graph_high_ceiling_no_truncation(self):
        """The connected-graph walk does not flag truncation when the ceiling clears the chain."""
        query = ConnectedGraphQuery(instance=self.head, max_depth=1000)
        pks = query.pk_list()
        # Every node in the chain is connected to the head.
        self.assertEqual(len(pks), self.CHAIN_LENGTH)
        self.assertFalse(query.truncated)

    @override_settings(DJANGO_POSTGRESQL_DAG_MAX_DEPTH=1000)
    def test_setting_default_ceiling_is_honored(self):
        """When the project raises the setting, the default (no explicit max_depth) clears the chain."""
        self.assertEqual(self.head.descendants().count(), self.CHAIN_LENGTH - 1)

    def test_package_default_ceiling_truncates_deep_chain(self):
        """With no project override the package keeps its conservative default of 20, which truncates."""
        # This documents the unchanged default for existing package users: a 30-node chain is cut at 20.
        query = DescendantQuery(instance=self.head)
        self.assertEqual(query.max_depth, 20)
        pks = query.pk_list()
        self.assertEqual(len(pks), 20)
        self.assertTrue(query.truncated)

    def test_boundary_exactly_at_ceiling_not_truncated(self):
        """A ceiling equal to the deepest node returns everything and does not flag truncation."""
        # 30 nodes -> head has 29 descendants, deepest at depth 29. max_depth=29 keeps them all.
        query = DescendantQuery(instance=self.head, max_depth=self.CHAIN_LENGTH - 1)
        pks = query.pk_list()
        self.assertEqual(len(pks), self.CHAIN_LENGTH - 1)
        self.assertFalse(query.truncated)

    def test_boundary_one_below_ceiling_is_truncated(self):
        """A ceiling one below the deepest node drops the last node and flags truncation."""
        query = DescendantQuery(instance=self.head, max_depth=self.CHAIN_LENGTH - 2)
        pks = query.pk_list()
        self.assertEqual(len(pks), self.CHAIN_LENGTH - 2)
        self.assertTrue(query.truncated)

    def test_connected_graph_boundary_returns_all_no_false_positive(self):
        """A connected-graph ceiling that returns the whole component does not false-warn."""
        # The chain has CHAIN_LENGTH nodes; a ceiling of exactly CHAIN_LENGTH reaches them all.
        query = ConnectedGraphQuery(instance=self.head, max_depth=self.CHAIN_LENGTH)
        pks = query.pk_list()
        self.assertEqual(len(pks), self.CHAIN_LENGTH)
        self.assertFalse(query.truncated)


class TruncationPrecisionTestCase(TestCase):
    """A node reachable at both a shallow and a deep depth must not trip a false truncation flag."""

    def setUp(self):
        # Diamond: s -> a -> x and s -> x. x is reachable at depth 1 (s->x) and depth 2 (s->a->x).
        self.s = NetworkNode.objects.create(name="s")
        self.a = NetworkNode.objects.create(name="a")
        self.x = NetworkNode.objects.create(name="x")
        self.s.add_child(self.a, disable_circular_check=True)
        self.a.add_child(self.x, disable_circular_check=True)
        self.s.add_child(self.x, disable_circular_check=True)

    def test_node_reachable_within_ceiling_is_not_flagged(self):
        """With max_depth=1, both a and x survive (depth 1); the depth-2 path to x must not warn."""
        query = DescendantQuery(instance=self.s, max_depth=1)
        pks = query.pk_list()
        self.assertEqual(set(pks), {self.a.pk, self.x.pk})
        self.assertFalse(query.truncated)


class TruncationWarningToggleTestCase(SerialChainFixtureMixin, TestCase):
    @override_settings(DJANGO_POSTGRESQL_DAG_WARN_ON_TRUNCATION=False)
    def test_warning_suppressed_but_flag_still_set(self):
        """Disabling the warning setting silences the log but keeps the truncated flag."""
        query = DescendantQuery(instance=self.head, max_depth=10)
        with self.assertNoLogs("django_postgresql_dag", level="WARNING"):
            query.pk_list()
        self.assertTrue(query.truncated)
