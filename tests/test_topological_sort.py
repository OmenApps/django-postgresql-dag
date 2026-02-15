"""Tests for topological sort."""

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import NetworkNode


class TopologicalSortDAGTestCase(DAGFixtureMixin, TestCase):
    """Test topological sort using the small DAG fixture.

    root -> a1 -> b1
         -> a2 -> b1
         -> a3 -> b2
    island (disconnected)
    """

    def test_topological_sort_parents_before_children(self):
        result = NetworkNode.objects.topological_sort()
        result_list = list(result.values_list("name", flat=True))

        # root must come before a1, a2, a3
        self.assertLess(result_list.index("root"), result_list.index("a1"))
        self.assertLess(result_list.index("root"), result_list.index("a2"))
        self.assertLess(result_list.index("root"), result_list.index("a3"))

        # a1 and a2 must come before b1
        self.assertLess(result_list.index("a1"), result_list.index("b1"))
        self.assertLess(result_list.index("a2"), result_list.index("b1"))

        # a3 must come before b2
        self.assertLess(result_list.index("a3"), result_list.index("b2"))

    def test_topological_sort_includes_islands(self):
        result = NetworkNode.objects.topological_sort()
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("island", result_names)

    def test_topological_sort_returns_all_nodes(self):
        result = NetworkNode.objects.topological_sort()
        self.assertEqual(result.count(), NetworkNode.objects.count())

    def test_topological_sort_island_at_front(self):
        # Islands are included at front (sorted by PK among islands)
        result = list(NetworkNode.objects.topological_sort().values_list("name", flat=True))
        island_idx = result.index("island")
        root_idx = result.index("root")
        # island has no edges, should be near the front
        self.assertLessEqual(island_idx, root_idx + 1)


class TopologicalSortTenNodeDAGTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test topological sort using the 10-node DAG fixture."""

    def test_topological_sort_ordering(self):
        result = NetworkNode.objects.topological_sort()
        result_list = list(result.values_list("name", flat=True))

        # root before all
        for name in ["a1", "a2", "a3", "b1", "b2", "b3", "b4", "c1", "c2"]:
            self.assertLess(result_list.index("root"), result_list.index(name))

        # a3 before b3, b4
        self.assertLess(result_list.index("a3"), result_list.index("b3"))
        self.assertLess(result_list.index("a3"), result_list.index("b4"))

        # b3 and b4 before c1
        self.assertLess(result_list.index("b3"), result_list.index("c1"))
        self.assertLess(result_list.index("b4"), result_list.index("c1"))

        # b3 before c2
        self.assertLess(result_list.index("b3"), result_list.index("c2"))

    def test_topological_sort_count(self):
        result = NetworkNode.objects.topological_sort()
        self.assertEqual(result.count(), 10)

    def test_topological_sort_with_max_depth(self):
        result = NetworkNode.objects.topological_sort(max_depth=1)
        names = set(result.values_list("name", flat=True))
        # max_depth=1 should get root and its direct children
        self.assertIn("root", names)
        self.assertIn("a1", names)
        self.assertIn("a2", names)
        self.assertIn("a3", names)


class TopologicalDescendantsTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test node.topological_descendants()."""

    def test_topological_descendants_from_root(self):
        result = self.root.topological_descendants()
        result_list = list(result.values_list("name", flat=True))
        self.assertEqual(result_list[0], "root")
        # All descendants are included
        self.assertEqual(result.count(), 10)

    def test_topological_descendants_from_a3(self):
        result = self.a3.topological_descendants()
        result_names = set(result.values_list("name", flat=True))
        self.assertIn("a3", result_names)
        self.assertIn("b3", result_names)
        self.assertIn("b4", result_names)
        self.assertIn("c1", result_names)
        self.assertIn("c2", result_names)

    def test_topological_descendants_leaf(self):
        result = self.c2.topological_descendants()
        result_names = list(result.values_list("name", flat=True))
        self.assertEqual(result_names, ["c2"])


class TopologicalSortEmptyGraphTestCase(TestCase):
    def test_topological_sort_no_nodes(self):
        result = NetworkNode.objects.topological_sort()
        self.assertEqual(result.count(), 0)

    def test_topological_sort_single_island(self):
        NetworkNode.objects.create(name="lonely")
        result = NetworkNode.objects.topological_sort()
        self.assertEqual(result.count(), 1)
