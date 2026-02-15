"""Tests for weighted shortest path."""

from django.test import TestCase

from django_postgresql_dag.exceptions import NodeNotReachableException, WeightFieldDoesNotExistException
from tests.testapp.models import NetworkEdge, NetworkNode


class WeightedPathFixtureMixin:
    """Fixture for weighted path tests.

    Creates a DAG with different weights:
        root --[w=1]--> a1 --[w=2]--> leaf
        root --[w=5]--> a2 --[w=1]--> leaf

    Shortest by weight: root -> a1 -> leaf (total=3)
    Shortest by hops: both are 2 hops
    """

    def setUp(self):
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.a2 = NetworkNode.objects.create(name="a2")
        self.leaf = NetworkNode.objects.create(name="leaf")

        self.root.add_child(self.a1)
        self.root.add_child(self.a2)
        self.a1.add_child(self.leaf)
        self.a2.add_child(self.leaf)

        # Set weights
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(weight=1.0)
        NetworkEdge.objects.filter(parent=self.root, child=self.a2).update(weight=5.0)
        NetworkEdge.objects.filter(parent=self.a1, child=self.leaf).update(weight=2.0)
        NetworkEdge.objects.filter(parent=self.a2, child=self.leaf).update(weight=1.0)


class WeightedPathTestCase(WeightedPathFixtureMixin, TestCase):
    def test_weighted_path_picks_lightest(self):
        qs, weight = self.root.weighted_path(self.leaf)
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names, ["root", "a1", "leaf"])
        self.assertAlmostEqual(weight, 3.0)

    def test_weighted_distance(self):
        dist = self.root.weighted_distance(self.leaf)
        self.assertAlmostEqual(dist, 3.0)

    def test_weighted_path_raw(self):
        result = self.root.weighted_path_raw(self.leaf)
        self.assertEqual(result.nodes, [self.root.pk, self.a1.pk, self.leaf.pk])
        self.assertAlmostEqual(result.total_weight, 3.0)

    def test_weighted_path_self_to_self(self):
        result = self.root.weighted_path_raw(self.root)
        self.assertEqual(result.nodes, [self.root.pk])
        self.assertEqual(result.total_weight, 0)

    def test_weighted_path_no_path(self):
        island = NetworkNode.objects.create(name="island")
        with self.assertRaises(NodeNotReachableException):
            self.root.weighted_path(island)

    def test_weighted_path_invalid_field(self):
        with self.assertRaises(WeightFieldDoesNotExistException):
            self.root.weighted_path(self.leaf, weight_field="nonexistent")

    def test_weighted_path_non_numeric_field(self):
        with self.assertRaises(WeightFieldDoesNotExistException):
            self.root.weighted_path(self.leaf, weight_field="name")

    def test_weighted_path_adjacent_nodes(self):
        qs, weight = self.root.weighted_path(self.a1)
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names, ["root", "a1"])
        self.assertAlmostEqual(weight, 1.0)


class WeightedPathHeavyRouteTestCase(TestCase):
    """Test with a heavier route that is shorter by hops but longer by weight."""

    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n3 = NetworkNode.objects.create(name="n3")
        self.n4 = NetworkNode.objects.create(name="n4")

        # Direct: n1 -> n4 with weight 100
        # Indirect: n1 -> n2 -> n3 -> n4 with weights 1, 1, 1
        self.n1.add_child(self.n4)
        self.n1.add_child(self.n2)
        self.n2.add_child(self.n3)
        self.n3.add_child(self.n4)

        NetworkEdge.objects.filter(parent=self.n1, child=self.n4).update(weight=100.0)
        NetworkEdge.objects.filter(parent=self.n1, child=self.n2).update(weight=1.0)
        NetworkEdge.objects.filter(parent=self.n2, child=self.n3).update(weight=1.0)
        NetworkEdge.objects.filter(parent=self.n3, child=self.n4).update(weight=1.0)

    def test_weighted_prefers_light_long_path(self):
        qs, weight = self.n1.weighted_path(self.n4)
        names = list(qs.values_list("name", flat=True))
        self.assertEqual(names, ["n1", "n2", "n3", "n4"])
        self.assertAlmostEqual(weight, 3.0)
