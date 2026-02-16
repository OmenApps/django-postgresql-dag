"""Tests for all-paths enumeration."""

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import NetworkNode


class AllPathsFromDAGTestCase(DAGFixtureMixin, TestCase):
    """Test all-paths using the small DAG fixture.

    root -> a1 -> b1
         -> a2 -> b1
         -> a3 -> b2
    island (disconnected)
    """

    def test_all_paths_single_path(self):
        # root -> a3 -> b2 (only one path)
        paths = self.root.all_paths_as_pk_lists(self.b2)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], [self.root.pk, self.a3.pk, self.b2.pk])

    def test_all_paths_two_paths(self):
        # root -> a1 -> b1  AND  root -> a2 -> b1
        paths = self.root.all_paths_as_pk_lists(self.b1)
        self.assertEqual(len(paths), 2)
        path_sets = [tuple(p) for p in paths]
        self.assertIn((self.root.pk, self.a1.pk, self.b1.pk), path_sets)
        self.assertIn((self.root.pk, self.a2.pk, self.b1.pk), path_sets)

    def test_all_paths_no_path(self):
        # root to island -- no path
        paths = self.root.all_paths_as_pk_lists(self.island)
        self.assertEqual(len(paths), 0)

    def test_all_paths_self_to_self(self):
        paths = self.root.all_paths_as_pk_lists(self.root)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], [self.root.pk])

    def test_all_paths_returns_querysets(self):
        paths = self.root.all_paths(self.b1)
        self.assertEqual(len(paths), 2)
        for qs in paths:
            self.assertTrue(qs.exists())

    def test_all_paths_max_results(self):
        paths = self.root.all_paths_as_pk_lists(self.b1, max_results=1)
        self.assertEqual(len(paths), 1)

    def test_all_paths_directional_false(self):
        # b1 to root (upward) with directional=False
        paths = self.b1.all_paths_as_pk_lists(self.root, directional=False)
        self.assertTrue(len(paths) >= 1)
        # Each path should start with b1 and end with root
        for path in paths:
            self.assertEqual(path[0], self.b1.pk)
            self.assertEqual(path[-1], self.root.pk)


class AllPathsFromTenNodeDAGTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test all-paths using the 10-node DAG fixture.

    root -> a1 -> b1
         -> a1 -> b2
         -> a2 -> b2
         -> a3 -> b3 -> c1
                     -> c2
              -> b4 -> c1
    """

    def test_all_paths_root_to_c1(self):
        # root -> a3 -> b3 -> c1
        # root -> a3 -> b4 -> c1
        paths = self.root.all_paths_as_pk_lists(self.c1)
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertEqual(path[0], self.root.pk)
            self.assertEqual(path[-1], self.c1.pk)

    def test_all_paths_root_to_b2(self):
        # root -> a1 -> b2
        # root -> a2 -> b2
        paths = self.root.all_paths_as_pk_lists(self.b2)
        self.assertEqual(len(paths), 2)

    def test_all_paths_a3_to_c1(self):
        # a3 -> b3 -> c1
        # a3 -> b4 -> c1
        paths = self.a3.all_paths_as_pk_lists(self.c1)
        self.assertEqual(len(paths), 2)

    def test_all_paths_root_to_c2(self):
        # Only one path: root -> a3 -> b3 -> c2
        paths = self.root.all_paths_as_pk_lists(self.c2)
        self.assertEqual(len(paths), 1)


class AllUpwardPathsMaxResultsTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Tests for upward all-paths with max_results (AllUpwardPathsQuery)."""

    def test_upward_all_paths_max_results(self):
        """Upward all-paths with max_results limits results."""
        paths = self.c1.all_paths_as_pk_lists(self.root, directional=False, max_results=1)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0][0], self.c1.pk)
        self.assertEqual(paths[0][-1], self.root.pk)

    def test_upward_all_paths_returns_all_without_limit(self):
        """Without max_results, all upward paths are returned."""
        paths = self.c1.all_paths_as_pk_lists(self.root, directional=False)
        # c1 -> b3 -> a3 -> root AND c1 -> b4 -> a3 -> root
        self.assertEqual(len(paths), 2)

    def test_upward_all_paths_no_path(self):
        """Upward all-paths returns empty when no path exists."""
        island = NetworkNode.objects.create(name="island")
        paths = island.all_paths_as_pk_lists(self.root, directional=False)
        self.assertEqual(len(paths), 0)
