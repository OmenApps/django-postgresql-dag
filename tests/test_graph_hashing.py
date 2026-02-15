"""Tests for graph hashing."""

import unittest

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import NetworkNode

try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


@unittest.skipUnless(HAS_NETWORKX, "networkx required")
class GraphHashTestCase(DAGFixtureMixin, TestCase):
    """Test graph_hash using the small DAG fixture."""

    def test_graph_hash_returns_string(self):
        from django_postgresql_dag.transformations import graph_hash

        h = graph_hash(self.root.clan())
        self.assertIsInstance(h, str)
        self.assertTrue(len(h) > 0)

    def test_graph_hash_deterministic(self):
        from django_postgresql_dag.transformations import graph_hash

        h1 = graph_hash(self.root.clan())
        h2 = graph_hash(self.root.clan())
        self.assertEqual(h1, h2)

    def test_graph_hash_differs_for_different_graphs(self):
        from django_postgresql_dag.transformations import graph_hash

        h1 = graph_hash(self.root.self_and_descendants())
        h2 = graph_hash(NetworkNode.objects.filter(pk=self.island.pk))
        self.assertNotEqual(h1, h2)

    def test_node_graph_hash(self):
        h = self.root.graph_hash(scope="descendants")
        self.assertIsInstance(h, str)
        self.assertTrue(len(h) > 0)

    def test_node_graph_hash_scope_connected(self):
        h = self.root.graph_hash(scope="connected")
        self.assertIsInstance(h, str)

    def test_node_graph_hash_scope_ancestors(self):
        h = self.b1.graph_hash(scope="ancestors")
        self.assertIsInstance(h, str)

    def test_node_graph_hash_scope_clan(self):
        h = self.a1.graph_hash(scope="clan")
        self.assertIsInstance(h, str)

    def test_node_graph_hash_invalid_scope(self):
        with self.assertRaises(ValueError):
            self.root.graph_hash(scope="invalid")


@unittest.skipUnless(HAS_NETWORKX, "networkx required")
class GraphsAreIsomorphicTestCase(DAGFixtureMixin, TestCase):
    def test_same_graph_is_isomorphic(self):
        from django_postgresql_dag.transformations import graphs_are_isomorphic

        self.assertTrue(graphs_are_isomorphic(self.root.clan(), self.root.clan()))

    def test_different_graphs_not_isomorphic(self):
        from django_postgresql_dag.transformations import graphs_are_isomorphic

        qs_a = self.root.self_and_descendants()
        qs_b = NetworkNode.objects.filter(pk=self.island.pk)
        self.assertFalse(graphs_are_isomorphic(qs_a, qs_b))


@unittest.skipUnless(HAS_NETWORKX, "networkx required")
class SubgraphHashesTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_subgraph_hashes_returns_dict(self):
        if not hasattr(nx, "weisfeiler_lehman_subgraph_hashes"):
            self.skipTest("NetworkX >= 3.3 required for subgraph hashes")
        from django_postgresql_dag.transformations import subgraph_hashes

        result = subgraph_hashes(self.root.clan())
        self.assertIsInstance(result, dict)
        # Should have entries for all nodes in the clan
        self.assertTrue(len(result) > 0)

    def test_node_subgraph_hashes(self):
        if not hasattr(nx, "weisfeiler_lehman_subgraph_hashes"):
            self.skipTest("NetworkX >= 3.3 required for subgraph hashes")
        result = self.root.subgraph_hashes(scope="descendants")
        self.assertIsInstance(result, dict)


@unittest.skipUnless(HAS_NETWORKX, "networkx required")
class GraphHashEmptyTestCase(TestCase):
    def test_empty_queryset_hash(self):
        from django_postgresql_dag.transformations import graph_hash

        h = graph_hash(NetworkNode.objects.none())
        self.assertIsInstance(h, str)
