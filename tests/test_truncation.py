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
from tests.testapp.models import NetworkNode


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
