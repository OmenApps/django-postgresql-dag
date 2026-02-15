"""Tests for depth annotation: ancestors_with_depth, descendants_with_depth."""

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin


class DepthAnnotationFromDAGTestCase(DAGFixtureMixin, TestCase):
    """Test depth annotation using the small DAG fixture.

    root -> a1 -> b1
         -> a2 -> b1
         -> a3 -> b2
    island (disconnected)
    """

    def test_descendants_with_depth_from_root(self):
        result = self.root.descendants_with_depth()
        depth_dict = {node.name: depth for node, depth in result}
        self.assertEqual(depth_dict["a1"], 1)
        self.assertEqual(depth_dict["a2"], 1)
        self.assertEqual(depth_dict["a3"], 1)
        self.assertEqual(depth_dict["b1"], 2)
        self.assertEqual(depth_dict["b2"], 2)
        self.assertEqual(len(result), 5)

    def test_ancestors_with_depth_from_b1(self):
        result = self.b1.ancestors_with_depth()
        depth_dict = {node.name: depth for node, depth in result}
        # b1 has parents a1 and a2 (depth 1), and root (depth 2)
        self.assertEqual(depth_dict["a1"], 1)
        self.assertEqual(depth_dict["a2"], 1)
        self.assertEqual(depth_dict["root"], 2)
        self.assertEqual(len(result), 3)

    def test_ancestors_with_depth_root_node(self):
        result = self.root.ancestors_with_depth()
        self.assertEqual(len(result), 0)

    def test_descendants_with_depth_leaf_node(self):
        result = self.b2.descendants_with_depth()
        self.assertEqual(len(result), 0)

    def test_descendants_with_depth_island(self):
        result = self.island.descendants_with_depth()
        self.assertEqual(len(result), 0)

    def test_ancestors_with_depth_island(self):
        result = self.island.ancestors_with_depth()
        self.assertEqual(len(result), 0)


class DepthAnnotationFromTenNodeDAGTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test depth annotation using the 10-node DAG fixture.

    root -> a1 -> b1
         -> a1 -> b2
         -> a2 -> b2
         -> a3 -> b3 -> c1
                     -> c2
              -> b4 -> c1
    """

    def test_descendants_with_depth_from_root(self):
        result = self.root.descendants_with_depth()
        depth_dict = {node.name: depth for node, depth in result}
        self.assertEqual(depth_dict["a1"], 1)
        self.assertEqual(depth_dict["a2"], 1)
        self.assertEqual(depth_dict["a3"], 1)
        self.assertEqual(depth_dict["b1"], 2)
        self.assertEqual(depth_dict["b2"], 2)
        self.assertEqual(depth_dict["b3"], 2)
        self.assertEqual(depth_dict["b4"], 2)
        self.assertEqual(depth_dict["c1"], 3)
        self.assertEqual(depth_dict["c2"], 3)

    def test_ancestors_with_depth_from_c1(self):
        result = self.c1.ancestors_with_depth()
        depth_dict = {node.name: depth for node, depth in result}
        # c1's parents: b3 and b4 (depth 1), a3 (depth 2), root (depth 3)
        self.assertEqual(depth_dict["b3"], 1)
        self.assertEqual(depth_dict["b4"], 1)
        self.assertEqual(depth_dict["a3"], 2)
        self.assertEqual(depth_dict["root"], 3)

    def test_descendants_returns_nodes_not_just_pks(self):
        result = self.root.descendants_with_depth()
        for node, depth in result:
            self.assertTrue(hasattr(node, "name"))
            self.assertIsInstance(depth, int)
