"""Tests for transitive reduction."""

from django.test import TestCase

from tests.testapp.models import NetworkEdge, NetworkNode


class TransitiveReductionTestCase(TestCase):
    """Test transitive reduction with a diamond + shortcut pattern.

    A -> B -> D
    A -> C -> D
    A -> D         (this is the redundant edge)
    """

    def setUp(self):
        self.a = NetworkNode.objects.create(name="A")
        self.b = NetworkNode.objects.create(name="B")
        self.c = NetworkNode.objects.create(name="C")
        self.d = NetworkNode.objects.create(name="D")

        self.a.add_child(self.b)
        self.a.add_child(self.c)
        self.b.add_child(self.d)
        self.c.add_child(self.d)
        self.a.add_child(self.d)  # redundant

    def test_redundant_edges_found(self):
        qs = NetworkNode.objects.transitive_reduction()
        self.assertEqual(qs.count(), 1)
        edge = qs.first()
        self.assertEqual(edge.parent_id, self.a.pk)
        self.assertEqual(edge.child_id, self.d.pk)

    def test_dry_run_does_not_delete(self):
        initial_count = NetworkEdge.objects.count()
        NetworkNode.objects.transitive_reduction(delete=False)
        self.assertEqual(NetworkEdge.objects.count(), initial_count)

    def test_delete_removes_redundant(self):
        initial_count = NetworkEdge.objects.count()
        count = NetworkNode.objects.transitive_reduction(delete=True)
        self.assertEqual(count, 1)
        self.assertEqual(NetworkEdge.objects.count(), initial_count - 1)
        # Verify the direct A->D edge is gone
        self.assertFalse(NetworkEdge.objects.filter(parent=self.a, child=self.d).exists())

    def test_edge_manager_redundant_edges(self):
        qs = NetworkEdge.objects.redundant_edges()
        self.assertEqual(qs.count(), 1)

    def test_edge_manager_transitive_reduction(self):
        count = NetworkEdge.objects.transitive_reduction(delete=True)
        self.assertEqual(count, 1)


class TransitiveReductionNoRedundantTestCase(TestCase):
    """Tree structure has no redundant edges."""

    def setUp(self):
        self.a = NetworkNode.objects.create(name="A")
        self.b = NetworkNode.objects.create(name="B")
        self.c = NetworkNode.objects.create(name="C")
        self.a.add_child(self.b)
        self.a.add_child(self.c)

    def test_no_redundant_edges(self):
        qs = NetworkNode.objects.transitive_reduction()
        self.assertEqual(qs.count(), 0)


class TransitiveReductionMultipleRedundantTestCase(TestCase):
    """Test with multiple redundant edges.

    A -> B -> C -> D
    A -> C             (redundant)
    A -> D             (redundant)
    B -> D             (redundant)
    """

    def setUp(self):
        self.a = NetworkNode.objects.create(name="A")
        self.b = NetworkNode.objects.create(name="B")
        self.c = NetworkNode.objects.create(name="C")
        self.d = NetworkNode.objects.create(name="D")

        self.a.add_child(self.b)
        self.b.add_child(self.c)
        self.c.add_child(self.d)
        self.a.add_child(self.c)  # redundant
        self.a.add_child(self.d)  # redundant
        self.b.add_child(self.d)  # redundant

    def test_three_redundant_edges(self):
        qs = NetworkNode.objects.transitive_reduction()
        self.assertEqual(qs.count(), 3)

    def test_delete_all_redundant(self):
        count = NetworkNode.objects.transitive_reduction(delete=True)
        self.assertEqual(count, 3)
        # Only 3 edges remain: A->B, B->C, C->D
        self.assertEqual(NetworkEdge.objects.count(), 3)
