"""Tests for Lowest Common Ancestor."""

from django.test import TestCase

from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin


class LCAFromDAGTestCase(DAGFixtureMixin, TestCase):
    """Test LCA using the small DAG fixture.

    root -> a1 -> b1
         -> a2 -> b1
         -> a3 -> b2
    island (disconnected)
    """

    def test_lca_same_node(self):
        result = self.root.lowest_common_ancestors(self.root)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})

    def test_lca_parent_and_child(self):
        # root is ancestor of a1, so LCA should be root
        result = self.root.lowest_common_ancestors(self.a1)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})

    def test_lca_siblings(self):
        # a1 and a2 share parent root
        result = self.a1.lowest_common_ancestors(self.a2)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})

    def test_lca_diamond_pattern(self):
        # b1 has parents a1 and a2; LCA of a1 and a2 is root
        result = self.a1.lowest_common_ancestors(self.a2)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})

    def test_lca_leaves_with_shared_ancestor(self):
        # b1 and b2 share ancestor root
        result = self.b1.lowest_common_ancestors(self.b2)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})

    def test_lca_no_common_ancestor(self):
        # island is disconnected
        result = self.root.lowest_common_ancestors(self.island)
        self.assertEqual(result.count(), 0)

    def test_lca_child_to_parent_order(self):
        # LCA(b1, root) should be root (root is ancestor of b1)
        result = self.b1.lowest_common_ancestors(self.root)
        self.assertEqual(set(result.values_list("pk", flat=True)), {self.root.pk})


class LCAFromTenNodeDAGTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Test LCA using the 10-node DAG fixture.

    root -> a1 -> b1
         -> a1 -> b2
         -> a2 -> b2
         -> a3 -> b3 -> c1
                     -> c2
              -> b4 -> c1
    """

    def test_lca_c1_and_c2(self):
        # c1: parents are b3 and b4, both children of a3
        # c2: parent is b3, child of a3
        # LCA should be b3 (lowest common ancestor)
        result = self.c1.lowest_common_ancestors(self.c2)
        result_pks = set(result.values_list("pk", flat=True))
        self.assertIn(self.b3.pk, result_pks)

    def test_lca_b1_and_b2(self):
        # b1: parent is a1
        # b2: parents are a1 and a2
        # LCA should be a1
        result = self.b1.lowest_common_ancestors(self.b2)
        result_pks = set(result.values_list("pk", flat=True))
        self.assertIn(self.a1.pk, result_pks)

    def test_lca_b2_and_c1(self):
        # b2 and c1 share root
        result = self.b2.lowest_common_ancestors(self.c1)
        result_pks = set(result.values_list("pk", flat=True))
        self.assertIn(self.root.pk, result_pks)

    def test_lca_returns_queryset(self):
        result = self.c1.lowest_common_ancestors(self.c2)
        # Verify it's a usable queryset
        for node in result:
            self.assertTrue(hasattr(node, "name"))
