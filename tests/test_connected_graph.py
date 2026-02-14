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
        """DAGFixtureMixin has a main graph and an island — should be 2 components."""
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
            # Can call .filter() — this verifies it's a regular QuerySet
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
    """Tests that ConnectedGraphQuery no-op filter methods are exercised (lines 430-446)."""

    def test_connected_graph_with_all_filter_params(self):
        """Pass all filter kwargs -- ConnectedGraphQuery stubs them all as no-ops."""
        edge_set = EdgeSet.objects.create(name="cg_set")
        node_set = NodeSet.objects.create(name="cg_ns")
        result = self.root.connected_graph(
            limiting_nodes_set_fk=node_set,
            limiting_edges_set_fk=edge_set,
            disallowed_nodes_queryset=NetworkNode.objects.filter(pk=self.island.pk),
            disallowed_edges_queryset=NetworkEdge.objects.all(),
            allowed_nodes_queryset=NetworkNode.objects.all(),
            allowed_edges_queryset=NetworkEdge.objects.all(),
        )
        # All filters are no-ops, so result should include the full connected component
        self.assertIn(self.root, result)
        self.assertIn(self.a1, result)
