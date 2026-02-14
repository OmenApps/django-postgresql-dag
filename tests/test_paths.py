from django.test import TestCase

from django_postgresql_dag.exceptions import NodeNotReachableException
from tests.helpers import DAGFixtureMixin, PathFilterFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import NetworkEdge, NetworkNode


class PathTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_distance(self):
        self.assertEqual(self.root.distance(self.c1), 3)

    def test_path_downward(self):
        result = [p.name for p in self.root.path(self.c1)]
        self.assertIn(
            result,
            [
                ["root", "a3", "b3", "c1"],
                ["root", "a3", "b4", "c1"],
            ],
        )

    def test_path_unreachable_raises(self):
        try:
            [p.name for p in self.c1.shortest_path(self.root)]
        except Exception:
            self.assertRaises(NodeNotReachableException)

    def test_path_nondirectional(self):
        result = [p.name for p in self.c1.path(self.root, directional=False)]
        self.assertIn(
            result,
            [
                ["c1", "b3", "a3", "root"],
                ["c1", "b4", "a3", "root"],
            ],
        )

    def test_leaves_from_root(self):
        self.assertEqual({p.name for p in self.root.leaves()}, {"b2", "c1", "c2", "b1"})

    def test_roots_from_leaf(self):
        self.assertEqual([p.name for p in self.c2.roots()], ["root"])


class PathEdgeCasesTestCase(DAGFixtureMixin, TestCase):
    def test_path_raw_self(self):
        result = self.root.path_raw(self.root)
        self.assertEqual(result, [[self.root.pk]])

    def test_path_exists_false(self):
        self.assertFalse(self.island.path_exists(self.root))

    def test_path_not_reachable(self):
        with self.assertRaises(NodeNotReachableException):
            self.b1.path_raw(self.root)

    def test_distance_self(self):
        # Uses `is` comparison, so same object returns 0
        self.assertEqual(self.root.distance(self.root), 0)


class DownwardPathFilterTestCase(PathFilterFixtureMixin, TestCase):
    """Tests for DownwardPathQuery filter methods (root->leaf direction)."""

    def test_path_with_limiting_edges_set_fk(self):
        """Covers DownwardPathQuery._limit_to_edges_set_fk (lines 592-603)."""
        path = self.root.path_raw(self.leaf, limiting_edges_set_fk=self.edge_set)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_disallowed_nodes(self):
        """Covers DownwardPathQuery._disallow_nodes (lines 606-613).
        Disallow mid1 -- path should still exist via mid2."""
        disallowed = NetworkNode.objects.filter(pk=self.mid1.pk)
        path = self.root.path_raw(self.leaf, disallowed_nodes_queryset=disallowed)
        pks = [node.pk for node in path]
        self.assertNotIn(self.mid1.pk, pks)
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_allowed_nodes(self):
        """Covers DownwardPathQuery._allow_nodes (lines 619-626).
        Only allow mid2 -- path should go through mid2."""
        allowed = NetworkNode.objects.filter(pk__in=[self.mid2.pk, self.root.pk, self.leaf.pk])
        path = self.root.path_raw(self.leaf, allowed_nodes_queryset=allowed)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_disallowed_edges(self):
        """Disallow mid1->leaf edge. Path should go through mid2."""
        disallowed_edges = NetworkEdge.objects.filter(parent=self.mid1, child=self.leaf)
        path = self.root.path_raw(self.leaf, disallowed_edges_queryset=disallowed_edges)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.mid2.pk, pks)
        self.assertIn(self.leaf.pk, pks)
        self.assertNotIn(self.mid1.pk, pks)

    def test_path_with_allowed_edges(self):
        """Allow only mid2-path edges. Path should exclude mid1."""
        edge_root_mid2 = NetworkEdge.objects.get(parent=self.root, child=self.mid2)
        edge_mid2_leaf = NetworkEdge.objects.get(parent=self.mid2, child=self.leaf)
        allowed_edges = NetworkEdge.objects.filter(pk__in=[edge_root_mid2.pk, edge_mid2_leaf.pk])
        path = self.root.path_raw(self.leaf, allowed_edges_queryset=allowed_edges)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.mid2.pk, pks)
        self.assertIn(self.leaf.pk, pks)
        self.assertNotIn(self.mid1.pk, pks)


class UpwardPathFilterTestCase(PathFilterFixtureMixin, TestCase):
    """Tests for UpwardPathQuery filter methods (leaf->root direction, non-directional)."""

    def test_path_with_limiting_edges_set_fk(self):
        """Covers UpwardPathQuery._limit_to_edges_set_fk."""
        path = self.leaf.path_raw(self.root, directional=False, limiting_edges_set_fk=self.edge_set)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_disallowed_nodes(self):
        """Disallow mid1 -- path should still exist via mid2."""
        disallowed = NetworkNode.objects.filter(pk=self.mid1.pk)
        path = self.leaf.path_raw(self.root, directional=False, disallowed_nodes_queryset=disallowed)
        pks = [node.pk for node in path]
        self.assertNotIn(self.mid1.pk, pks)
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_allowed_nodes(self):
        """Only allow mid2 -- path should go through mid2."""
        allowed = NetworkNode.objects.filter(pk__in=[self.mid2.pk, self.root.pk, self.leaf.pk])
        path = self.leaf.path_raw(self.root, directional=False, allowed_nodes_queryset=allowed)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.leaf.pk, pks)

    def test_path_with_disallowed_edges(self):
        """Disallow mid1->leaf edge. Path should go through mid2."""
        disallowed_edges = NetworkEdge.objects.filter(parent=self.mid1, child=self.leaf)
        path = self.leaf.path_raw(self.root, directional=False, disallowed_edges_queryset=disallowed_edges)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.mid2.pk, pks)
        self.assertIn(self.leaf.pk, pks)
        self.assertNotIn(self.mid1.pk, pks)

    def test_path_with_allowed_edges(self):
        """Allow only mid2-path edges. Path should exclude mid1."""
        edge_root_mid2 = NetworkEdge.objects.get(parent=self.root, child=self.mid2)
        edge_mid2_leaf = NetworkEdge.objects.get(parent=self.mid2, child=self.leaf)
        allowed_edges = NetworkEdge.objects.filter(pk__in=[edge_root_mid2.pk, edge_mid2_leaf.pk])
        path = self.leaf.path_raw(self.root, directional=False, allowed_edges_queryset=allowed_edges)
        pks = [node.pk for node in path]
        self.assertIn(self.root.pk, pks)
        self.assertIn(self.mid2.pk, pks)
        self.assertIn(self.leaf.pk, pks)
        self.assertNotIn(self.mid1.pk, pks)
