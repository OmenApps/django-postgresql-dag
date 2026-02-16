from django.test import TestCase

from django_postgresql_dag.signals import post_edge_create, post_edge_delete, pre_edge_create, pre_edge_delete
from tests.testapp.models import NetworkEdge, NetworkNode


class SignalCollector:
    """Helper to collect signal calls for assertions."""

    def __init__(self):
        self.calls = []

    def handler(self, signal, sender, **kwargs):
        self.calls.append({"signal": signal, "sender": sender, **kwargs})

    def reset(self):
        self.calls = []


class EdgeCreateSignalTestCase(TestCase):
    def setUp(self):
        self.collector = SignalCollector()
        pre_edge_create.connect(self.collector.handler)
        post_edge_create.connect(self.collector.handler)
        self.parent = NetworkNode.objects.create(name="parent")
        self.child = NetworkNode.objects.create(name="child")

    def tearDown(self):
        pre_edge_create.disconnect(self.collector.handler)
        post_edge_create.disconnect(self.collector.handler)

    def test_add_child_fires_create_signals(self):
        self.parent.add_child(self.child)
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_create)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_create)

    def test_add_parent_fires_create_signals(self):
        self.child.add_parent(self.parent)
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_create)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_create)

    def test_direct_edge_save_fires_create_signals(self):
        edge = NetworkEdge(parent=self.parent, child=self.child)
        edge.save()
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_create)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_create)

    def test_create_signal_kwargs(self):
        self.parent.add_child(self.child)
        for call in self.collector.calls:
            self.assertEqual(call["sender"], NetworkEdge)
            self.assertEqual(call["parent"], self.parent)
            self.assertEqual(call["child"], self.child)
            self.assertIn("instance", call)
            self.assertIsInstance(call["instance"], NetworkEdge)

    def test_edge_update_does_not_fire_create_signals(self):
        self.parent.add_child(self.child)
        self.collector.reset()
        edge = NetworkEdge.objects.first()
        edge.save()
        self.assertEqual(len(self.collector.calls), 0)


class EdgeDeleteSignalTestCase(TestCase):
    def setUp(self):
        self.collector = SignalCollector()
        pre_edge_delete.connect(self.collector.handler)
        post_edge_delete.connect(self.collector.handler)
        self.parent = NetworkNode.objects.create(name="parent")
        self.child = NetworkNode.objects.create(name="child")

    def tearDown(self):
        pre_edge_delete.disconnect(self.collector.handler)
        post_edge_delete.disconnect(self.collector.handler)

    def test_remove_child_fires_delete_signals(self):
        self.parent.add_child(self.child)
        self.parent.remove_child(self.child)
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_delete)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_delete)

    def test_remove_parent_fires_delete_signals(self):
        self.child.add_parent(self.parent)
        self.child.remove_parent(self.parent)
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_delete)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_delete)

    def test_direct_edge_delete_fires_signals(self):
        self.parent.add_child(self.child)
        edge = NetworkEdge.objects.first()
        edge.delete()
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_delete)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_delete)

    def test_delete_signal_kwargs(self):
        self.parent.add_child(self.child)
        edge = NetworkEdge.objects.first()
        edge.delete()
        for call in self.collector.calls:
            self.assertEqual(call["sender"], NetworkEdge)
            self.assertEqual(call["parent"], self.parent)
            self.assertEqual(call["child"], self.child)
            self.assertIn("instance", call)

    def test_insert_node_fires_delete_signal(self):
        """insert_node() removes the original edge - signals should fire."""
        self.parent.add_child(self.child)
        mid = NetworkNode.objects.create(name="mid")
        edge = NetworkEdge.objects.get(parent=self.parent, child=self.child)
        NetworkEdge.objects.insert_node(edge, mid)
        # Should have pre + post delete for the original edge
        self.assertEqual(len(self.collector.calls), 2)
        self.assertEqual(self.collector.calls[0]["signal"], pre_edge_delete)
        self.assertEqual(self.collector.calls[1]["signal"], post_edge_delete)
        self.assertEqual(self.collector.calls[0]["parent"], self.parent)
        self.assertEqual(self.collector.calls[0]["child"], self.child)

    def test_remove_all_children_fires_signals(self):
        child2 = NetworkNode.objects.create(name="child2")
        self.parent.add_child(self.child)
        self.parent.add_child(child2)
        self.parent.remove_child()  # remove all
        self.assertEqual(len(self.collector.calls), 2)  # 1 bulk pre + 1 bulk post

    def test_remove_all_parents_fires_signals(self):
        parent2 = NetworkNode.objects.create(name="parent2")
        self.child.add_parent(self.parent)
        self.child.add_parent(parent2)
        self.child.remove_parent()  # remove all
        self.assertEqual(len(self.collector.calls), 2)  # 1 bulk pre + 1 bulk post
