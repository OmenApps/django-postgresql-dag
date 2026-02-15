"""Tests for critical path."""

from django.test import TestCase

from tests.helpers import TenNodeDAGFixtureMixin
from tests.testapp.models import NetworkEdge, NetworkNode


class CriticalPathTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test critical path using the 10-node DAG fixture.

    root -> a1 -> b1
         -> a1 -> b2
         -> a2 -> b2
         -> a3 -> b3 -> c1
                     -> c2
              -> b4 -> c1
    """

    def test_critical_path_by_hops(self):
        qs, weight = NetworkNode.objects.critical_path()
        names = list(qs.values_list("name", flat=True))
        # Longest path by hops is 4 nodes (3 edges): root -> a3 -> b3/b4 -> c1/c2
        self.assertEqual(len(names), 4)
        self.assertEqual(names[0], "root")
        self.assertAlmostEqual(weight, 3.0)

    def test_critical_path_includes_root_and_leaf(self):
        qs, weight = NetworkNode.objects.critical_path()
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names[0], "root")
        self.assertIn(names[-1], ["c1", "c2"])

    def test_critical_path_with_weights(self):
        # Set specific weights so one path is clearly longest
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(weight=10.0)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(weight=10.0)

        qs, weight = NetworkNode.objects.critical_path(weight_field="weight")
        names = list(qs.values_list("name", flat=True))
        # root -> a1 -> b1 should be the heaviest path (20.0)
        self.assertEqual(names, ["root", "a1", "b1"])
        self.assertAlmostEqual(weight, 20.0)


class CriticalPathEmptyTestCase(TestCase):
    def test_critical_path_no_edges(self):
        NetworkNode.objects.create(name="lonely")
        qs, weight = NetworkNode.objects.critical_path()
        # A single node with no edges is a root and also a leaf;
        # it forms a path of length 0 (one node, zero edges)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(weight, 0)

    def test_critical_path_empty_graph(self):
        qs, weight = NetworkNode.objects.critical_path()
        self.assertEqual(qs.count(), 0)
        self.assertEqual(weight, 0)


class CriticalPathSimpleChainTestCase(TestCase):
    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n3 = NetworkNode.objects.create(name="n3")
        self.n1.add_child(self.n2)
        self.n2.add_child(self.n3)

    def test_simple_chain_critical_path(self):
        qs, weight = NetworkNode.objects.critical_path()
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names, ["n1", "n2", "n3"])
        self.assertAlmostEqual(weight, 2.0)
