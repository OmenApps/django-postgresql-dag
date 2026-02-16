"""Tests for depth annotation: ancestors_with_depth, descendants_with_depth."""

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import EdgeSet, NetworkEdge, NetworkNode


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


class DepthAnnotationFilterTestCase(DAGFixtureMixin, TestCase):
    """Tests for filters on AncestorDepthQuery and DescendantDepthQuery."""

    def setUp(self):
        super().setUp()
        self.edge_set = EdgeSet.objects.create(name="depth_set")
        NetworkEdge.objects.all().update(edge_set=self.edge_set)

    def test_descendants_with_depth_disallow_nodes(self):
        """Disallow a1 from root's descendants_with_depth."""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        result = self.root.descendants_with_depth(disallowed_nodes_queryset=disallowed)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertNotIn("a1", depth_dict)
        # a2 and a3 should still be present
        self.assertIn("a2", depth_dict)
        self.assertIn("a3", depth_dict)

    def test_ancestors_with_depth_disallow_nodes(self):
        """Disallow a1 from b1's ancestors_with_depth."""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        result = self.b1.ancestors_with_depth(disallowed_nodes_queryset=disallowed)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertNotIn("a1", depth_dict)
        # a2 should still be reachable
        self.assertIn("a2", depth_dict)

    def test_descendants_with_depth_allow_nodes(self):
        """Only allow specific nodes in root's descendants_with_depth."""
        allowed = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.b1.pk])
        result = self.root.descendants_with_depth(allowed_nodes_queryset=allowed)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertIn("a1", depth_dict)
        self.assertNotIn("a2", depth_dict)

    def test_ancestors_with_depth_allow_nodes(self):
        """Only allow specific nodes in b1's ancestors_with_depth."""
        allowed = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.root.pk])
        result = self.b1.ancestors_with_depth(allowed_nodes_queryset=allowed)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertNotIn("a2", depth_dict)

    def test_descendants_with_depth_limiting_edges_set_fk(self):
        """Limit descendants_with_depth to edges in a specific edge set."""
        other_set = EdgeSet.objects.create(name="other_set")
        # Only assign root->a1 and a1->b1 to other_set
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(edge_set=other_set)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(edge_set=other_set)
        result = self.root.descendants_with_depth(limiting_edges_set_fk=other_set)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertIn("a1", depth_dict)
        self.assertIn("b1", depth_dict)
        self.assertNotIn("a2", depth_dict)

    def test_ancestors_with_depth_limiting_edges_set_fk(self):
        """Limit ancestors_with_depth to edges in a specific edge set."""
        other_set = EdgeSet.objects.create(name="other_set")
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(edge_set=other_set)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(edge_set=other_set)
        result = self.b1.ancestors_with_depth(limiting_edges_set_fk=other_set)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertIn("a1", depth_dict)
        self.assertIn("root", depth_dict)
        self.assertNotIn("a2", depth_dict)

    def test_descendants_with_depth_disallow_edges(self):
        """Disallow specific edges in descendants_with_depth."""
        edge_root_a1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        disallowed = NetworkEdge.objects.filter(pk=edge_root_a1.pk)
        result = self.root.descendants_with_depth(disallowed_edges_queryset=disallowed)
        depth_dict = {node.name: depth for node, depth in result}
        self.assertNotIn("a1", depth_dict)
        self.assertIn("a2", depth_dict)
