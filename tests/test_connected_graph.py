import logging

from django.test import TestCase

from tests.helpers import DAGFixtureMixin
from tests.testapp.models import EdgeSet, NetworkEdge, NetworkNode, NodeSet

log = logging.getLogger("django_postgresql_log.testapp")


class ConnectedGraphTestCase(TestCase):
    """Tests for connected_graph, connected_graph_raw, and connected_graph_node_count."""

    def setUp(self):
        # Build a small DAG:
        #   root -> a1 -> b1
        #        -> a2 -> b1
        #   island (disconnected)
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.a2 = NetworkNode.objects.create(name="a2")
        self.b1 = NetworkNode.objects.create(name="b1")
        self.island = NetworkNode.objects.create(name="island")

        self.root.add_child(self.a1)
        self.root.add_child(self.a2)
        self.a1.add_child(self.b1)
        self.a2.add_child(self.b1)

    def test_connected_graph_from_root(self):
        """connected_graph from root should return all connected nodes."""
        connected = self.root.connected_graph()
        connected_names = set(connected.values_list("name", flat=True))
        self.assertEqual(connected_names, {"root", "a1", "a2", "b1"})

    def test_connected_graph_from_leaf(self):
        """connected_graph from a leaf should return the same connected component."""
        connected = self.b1.connected_graph()
        connected_names = set(connected.values_list("name", flat=True))
        self.assertEqual(connected_names, {"root", "a1", "a2", "b1"})

    def test_connected_graph_from_middle(self):
        """connected_graph from a middle node should return the same connected component."""
        connected = self.a1.connected_graph()
        connected_names = set(connected.values_list("name", flat=True))
        self.assertEqual(connected_names, {"root", "a1", "a2", "b1"})

    def test_connected_graph_island(self):
        """connected_graph from an island node should return only itself."""
        connected = self.island.connected_graph()
        connected_names = set(connected.values_list("name", flat=True))
        self.assertEqual(connected_names, {"island"})

    def test_connected_graph_node_count(self):
        """connected_graph_node_count should return the correct count."""
        self.assertEqual(self.root.connected_graph_node_count(), 4)
        self.assertEqual(self.island.connected_graph_node_count(), 1)

    def test_connected_graph_raw_returns_raw_queryset(self):
        """connected_graph_raw should return a RawQuerySet."""
        raw = self.root.connected_graph_raw()
        raw_names = {node.name for node in raw}
        self.assertEqual(raw_names, {"root", "a1", "a2", "b1"})


class ConnectedComponentsTestCase(DAGFixtureMixin, TestCase):
    """Tests for NodeManager.connected_components()."""

    def test_returns_two_components(self):
        """DAGFixtureMixin has a main graph and an island - should be 2 components."""
        components = NetworkNode.objects.connected_components()
        self.assertEqual(len(components), 2)

    def test_component_contents(self):
        """One component has the connected DAG nodes, the other has only the island."""
        components = NetworkNode.objects.connected_components()
        component_name_sets = [set(c.values_list("name", flat=True)) for c in components]
        self.assertIn({"root", "a1", "a2", "a3", "b1", "b2"}, component_name_sets)
        self.assertIn({"island"}, component_name_sets)

    def test_each_component_is_queryset(self):
        """Each component should be a standard Django QuerySet (not raw)."""
        components = NetworkNode.objects.connected_components()
        for component in components:
            # Can call .filter() - this verifies it's a regular QuerySet
            self.assertTrue(component.filter(pk__isnull=False).exists())

    def test_empty_graph(self):
        """An empty table should return an empty list."""
        NetworkNode.objects.all().delete()
        components = NetworkNode.objects.connected_components()
        self.assertEqual(components, [])

    def test_single_island(self):
        """A single island node should return 1 component."""
        NetworkNode.objects.all().delete()
        NetworkNode.objects.create(name="solo")
        components = NetworkNode.objects.connected_components()
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].first().name, "solo")


class ConnectedGraphFilterTestCase(DAGFixtureMixin, TestCase):
    """Tests that ConnectedGraphQuery filter methods work correctly."""

    def setUp(self):
        super().setUp()
        self.edge_set = EdgeSet.objects.create(name="cg_set")
        # Assign all edges to edge_set
        NetworkEdge.objects.all().update(edge_set=self.edge_set)

    def test_connected_graph_disallow_nodes(self):
        """Disallowing a node should exclude it and nodes only reachable through it."""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        result = self.root.connected_graph(disallowed_nodes_queryset=disallowed)
        result_names = set(result.values_list("name", flat=True))
        self.assertNotIn("a1", result_names)
        # root, a2, a3 should still be present
        self.assertIn("root", result_names)
        self.assertIn("a2", result_names)
        self.assertIn("a3", result_names)

    def test_connected_graph_disallow_edges(self):
        """Disallowing an edge should prevent traversal along it."""
        edge_root_a1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        disallowed = NetworkEdge.objects.filter(pk=edge_root_a1.pk)
        result = self.root.connected_graph(disallowed_edges_queryset=disallowed)
        result_names = set(result.values_list("name", flat=True))
        # a1 and b1 may still be reachable via a2->b1 path, but a1 is only reachable via root->a1
        self.assertIn("root", result_names)

    def test_connected_graph_allow_nodes(self):
        """Only traverse through allowed nodes."""
        allowed = NetworkNode.objects.filter(name__in=["root", "a1", "b1"])
        result = self.root.connected_graph(allowed_nodes_queryset=allowed)
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("root", result_names)
        self.assertIn("a1", result_names)
        self.assertIn("b1", result_names)
        self.assertNotIn("a2", result_names)
        self.assertNotIn("a3", result_names)

    def test_connected_graph_allow_edges(self):
        """Only traverse along allowed edges."""
        edge_root_a1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        edge_a1_b1 = NetworkEdge.objects.get(parent=self.a1, child=self.b1)
        allowed = NetworkEdge.objects.filter(pk__in=[edge_root_a1.pk, edge_a1_b1.pk])
        result = self.root.connected_graph(allowed_edges_queryset=allowed)
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("root", result_names)
        self.assertIn("a1", result_names)
        self.assertIn("b1", result_names)
        self.assertNotIn("a2", result_names)

    def test_connected_graph_limiting_edges_set_fk(self):
        """Limiting edges by FK should restrict traversal to those edges."""
        other_set = EdgeSet.objects.create(name="other_set")
        # Only assign root->a1 and a1->b1 to other_set
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(edge_set=other_set)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(edge_set=other_set)
        result = self.root.connected_graph(limiting_edges_set_fk=other_set)
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("root", result_names)
        self.assertIn("a1", result_names)
        self.assertIn("b1", result_names)
        self.assertNotIn("a2", result_names)

    def test_connected_graph_limiting_nodes_set_fk_noop(self):
        """limiting_nodes_set_fk is still a no-op but should not error."""
        node_set = NodeSet.objects.create(name="cg_ns")
        result = self.root.connected_graph(limiting_nodes_set_fk=node_set)
        # No-op, so all connected nodes should be returned
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("root", result_names)
        self.assertIn("a1", result_names)

    def test_connected_graph_max_depth(self):
        """max_depth should limit how far connected_graph traverses."""
        # With max_depth=1, from root we should reach immediate neighbors only
        result = self.root.connected_graph(max_depth=2)
        result_names = set(result.values_list("name", flat=True))
        # max_depth=2 means path array can be at most length 2 (root + 1 hop)
        self.assertIn("root", result_names)
        self.assertIn("a1", result_names)
        self.assertIn("a2", result_names)
        self.assertIn("a3", result_names)

    def test_connected_graph_no_duplicate_rows(self):
        """Ensure the rewritten CTE does not produce duplicate rows."""
        result = self.root.connected_graph()
        pks = list(result.values_list("pk", flat=True))
        self.assertEqual(len(pks), len(set(pks)))
