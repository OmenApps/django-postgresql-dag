from django.test import TestCase

from django_postgresql_dag.query_builders import AncestorQuery, DescendantQuery
from tests.helpers import DAGFixtureMixin, TenNodeDAGFixtureMixin
from tests.testapp.models import EdgeSet, NetworkEdge, NetworkNode, NodeSet


class NodeManagerTestCase(DAGFixtureMixin, TestCase):
    def test_roots_no_arg(self):
        roots = NetworkNode.objects.roots()
        self.assertIn(self.root, roots)
        self.assertIn(self.island, roots)
        self.assertNotIn(self.a1, roots)

    def test_roots_with_node_arg(self):
        roots = NetworkNode.objects.roots(node=self.b1)
        self.assertIn(self.root, roots)

    def test_leaves_no_arg(self):
        leaves = NetworkNode.objects.leaves()
        self.assertIn(self.b1, leaves)
        self.assertIn(self.b2, leaves)
        self.assertIn(self.island, leaves)
        self.assertNotIn(self.root, leaves)

    def test_leaves_with_node_arg(self):
        leaves = NetworkNode.objects.leaves(node=self.root)
        self.assertIn(self.b1, leaves)
        self.assertIn(self.b2, leaves)


class NodePredicateTestCase(DAGFixtureMixin, TestCase):
    def test_is_root(self):
        self.assertTrue(self.root.is_root())
        self.assertFalse(self.a1.is_root())
        self.assertFalse(self.b1.is_root())
        self.assertFalse(self.island.is_root())

    def test_is_leaf(self):
        self.assertTrue(self.b1.is_leaf())
        self.assertTrue(self.b2.is_leaf())
        self.assertFalse(self.root.is_leaf())
        self.assertFalse(self.a1.is_leaf())
        self.assertFalse(self.island.is_leaf())

    def test_is_island(self):
        self.assertTrue(self.island.is_island())
        self.assertFalse(self.root.is_island())
        self.assertFalse(self.b1.is_island())

    def test_is_ancestor_of(self):
        self.assertTrue(self.root.is_ancestor_of(self.b1))
        self.assertTrue(self.a1.is_ancestor_of(self.b1))
        self.assertFalse(self.b1.is_ancestor_of(self.root))
        self.assertFalse(self.island.is_ancestor_of(self.root))

    def test_is_descendant_of(self):
        self.assertTrue(self.b1.is_descendant_of(self.root))
        self.assertFalse(self.root.is_descendant_of(self.b1))

    def test_is_sibling_of(self):
        self.assertTrue(self.a1.is_sibling_of(self.a2))
        self.assertTrue(self.a1.is_sibling_of(self.a3))
        self.assertFalse(self.a1.is_sibling_of(self.b1))
        self.assertFalse(self.root.is_sibling_of(self.island))

    def test_is_partner_of(self):
        # a1 and a2 both have child b1, so they are partners
        self.assertTrue(self.a1.is_partner_of(self.a2))
        self.assertFalse(self.a1.is_partner_of(self.a3))
        self.assertFalse(self.island.is_partner_of(self.root))


class PredicateFromTenNodeDAGTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_is_root_and_is_leaf(self):
        self.assertTrue(self.root.is_root())
        self.assertTrue(self.c1.is_leaf())
        self.assertFalse(self.c1.is_root())
        self.assertFalse(self.root.is_leaf())
        self.assertFalse(self.a1.is_leaf())
        self.assertFalse(self.a1.is_root())


class LeavesRootsTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_leaves_from_root(self):
        self.assertEqual({p.name for p in self.root.leaves()}, {"b2", "c1", "c2", "b1"})

    def test_roots_from_leaf(self):
        self.assertEqual([p.name for p in self.c2.roots()], ["root"])


class EdgeQueryTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_edge_auto_name(self):
        self.assertEqual(self.b3.children.through.objects.filter(child=self.c1)[0].name, "b3 c1")

    def test_descendants_edges(self):
        self.assertEqual(self.b3.descendants_edges().first(), NetworkEdge.objects.get(parent=self.b3, child=self.c1))

    def test_ancestors_edges(self):
        self.assertEqual(self.a1.ancestors_edges().first(), NetworkEdge.objects.get(parent=self.root, child=self.a1))

    def test_clan_edges(self):
        self.assertTrue(NetworkEdge.objects.get(parent=self.a1, child=self.b2) in self.a1.clan_edges())
        self.assertTrue(NetworkEdge.objects.get(parent=self.a1, child=self.b1) in self.a1.clan_edges())
        self.assertTrue(NetworkEdge.objects.get(parent=self.root, child=self.a1) in self.a1.clan_edges())


class EdgeManagerTestCase(DAGFixtureMixin, TestCase):
    def test_from_nodes_queryset(self):
        nodes_qs = self.root.clan()
        edges = NetworkEdge.objects.from_nodes_queryset(nodes_qs)
        self.assertTrue(edges.exists())
        # All edges should connect nodes within the clan
        for edge in edges:
            self.assertIn(edge.parent, nodes_qs)
            self.assertIn(edge.child, nodes_qs)

    def test_descendants_edges(self):
        edges = NetworkEdge.objects.descendants(self.root)
        self.assertTrue(edges.exists())
        # Should include edge from root->a1
        self.assertTrue(edges.filter(parent=self.root, child=self.a1).exists())

    def test_ancestors_edges(self):
        edges = NetworkEdge.objects.ancestors(self.b1)
        self.assertTrue(edges.exists())
        self.assertTrue(edges.filter(parent=self.root, child=self.a1).exists())

    def test_clan_edges(self):
        edges = NetworkEdge.objects.clan(self.a1)
        self.assertTrue(edges.exists())

    def test_path_edges(self):
        edges = NetworkEdge.objects.path(self.root, self.b1)
        self.assertTrue(edges.exists())


class GetPkNameTestCase(TestCase):
    def test_get_pk_name_returns_attname(self):
        """get_pk_name should return attname (db column name), not name (field name).
        For standard AutoField/BigAutoField PKs these are identical ('id'),
        but for relational PKs (e.g. OneToOneField in polymorphic models) they differ."""
        node = NetworkNode.objects.create(name="pk_name_test")
        self.assertEqual(node.get_pk_name(), node._meta.pk.attname)


class GetPkTypeTestCase(TestCase):
    def test_bigautofield(self):
        """DEFAULT_AUTO_FIELD is BigAutoField, so get_pk_type should return 'bigint'"""
        node = NetworkNode.objects.create(name="pk_test")
        self.assertEqual(node.get_pk_type(), "bigint")


class GetForeignKeyFieldTestCase(TestCase):
    def test_with_edge_set_instance(self):
        edge_set = EdgeSet.objects.create(name="es1")
        node = NetworkNode.objects.create(name="fk_test")
        # NetworkEdge has a FK to EdgeSet, so get_foreign_key_field should find it
        result = node.get_foreign_key_field(fk_instance=edge_set)
        self.assertEqual(result, "edge_set")

    def test_with_none(self):
        node = NetworkNode.objects.create(name="fk_test2")
        result = node.get_foreign_key_field(fk_instance=None)
        self.assertIsNone(result)

    def test_with_unrelated_model(self):
        node_set = NodeSet.objects.create(name="ns1")
        node = NetworkNode.objects.create(name="fk_test3")
        # NetworkEdge has no FK to NodeSet
        result = node.get_foreign_key_field(fk_instance=node_set)
        self.assertIsNone(result)


class NodeDepthTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_node_depth(self):
        self.assertEqual(self.root.node_depth(), 0)
        self.assertEqual(self.a1.node_depth(), 1)
        self.assertEqual(self.a2.node_depth(), 1)
        self.assertEqual(self.a3.node_depth(), 1)
        self.assertEqual(self.b1.node_depth(), 2)
        self.assertEqual(self.b2.node_depth(), 2)
        self.assertEqual(self.b3.node_depth(), 2)
        self.assertEqual(self.b4.node_depth(), 2)
        self.assertEqual(self.c1.node_depth(), 3)
        self.assertEqual(self.c2.node_depth(), 3)

    def test_node_depth_root(self):
        self.assertEqual(self.root.node_depth(), 0)

    def test_node_depth_island(self):
        island = NetworkNode.objects.create(name="island")
        self.assertEqual(island.node_depth(), 0)


class ValidateRouteTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_validate_route_contiguous(self):
        # root -> a3 -> b3 -> c1 is a valid contiguous route
        e1 = NetworkEdge.objects.get(parent=self.root, child=self.a3)
        e2 = NetworkEdge.objects.get(parent=self.a3, child=self.b3)
        e3 = NetworkEdge.objects.get(parent=self.b3, child=self.c1)
        self.assertTrue(NetworkEdge.objects.validate_route([e1, e2, e3]))

    def test_validate_route_broken(self):
        # root -> a1 then b3 -> c1 is NOT contiguous (a1 != b3's parent in the route)
        e1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        e2 = NetworkEdge.objects.get(parent=self.b3, child=self.c1)
        self.assertFalse(NetworkEdge.objects.validate_route([e1, e2]))

    def test_validate_route_single_edge(self):
        e1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        self.assertTrue(NetworkEdge.objects.validate_route([e1]))


class SortEdgesTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_sort_edges(self):
        # Get edges in a known non-sorted order
        e_b3_c1 = NetworkEdge.objects.get(parent=self.b3, child=self.c1)
        e_root_a3 = NetworkEdge.objects.get(parent=self.root, child=self.a3)
        e_a3_b3 = NetworkEdge.objects.get(parent=self.a3, child=self.b3)
        unsorted = [e_b3_c1, e_root_a3, e_a3_b3]
        sorted_edges = NetworkEdge.objects.sort(unsorted)
        # Should be sorted root-to-leaf: root->a3, a3->b3, b3->c1
        self.assertEqual(sorted_edges[0], e_root_a3)
        self.assertEqual(sorted_edges[1], e_a3_b3)
        self.assertEqual(sorted_edges[2], e_b3_c1)


class GraphStatsTestCase(DAGFixtureMixin, TestCase):
    """Tests for NodeManager.graph_stats()."""

    def test_all_keys_present(self):
        stats = NetworkNode.objects.graph_stats()
        expected_keys = {
            "node_count",
            "edge_count",
            "root_count",
            "leaf_count",
            "island_count",
            "max_depth",
            "avg_depth",
            "density",
            "component_count",
        }
        self.assertEqual(set(stats.keys()), expected_keys)

    def test_node_count(self):
        stats = NetworkNode.objects.graph_stats()
        # DAGFixtureMixin creates: root, a1, a2, a3, b1, b2, island = 7
        self.assertEqual(stats["node_count"], 7)

    def test_edge_count(self):
        stats = NetworkNode.objects.graph_stats()
        # Edges: root->a1, root->a2, root->a3, a1->b1, a2->b1, a3->b2 = 6
        self.assertEqual(stats["edge_count"], 6)

    def test_root_count(self):
        stats = NetworkNode.objects.graph_stats()
        # roots (no parents): root, island = 2
        self.assertEqual(stats["root_count"], 2)

    def test_leaf_count(self):
        stats = NetworkNode.objects.graph_stats()
        # leaves (no children): b1, b2, island = 3
        self.assertEqual(stats["leaf_count"], 3)

    def test_island_count(self):
        stats = NetworkNode.objects.graph_stats()
        self.assertEqual(stats["island_count"], 1)

    def test_max_depth(self):
        stats = NetworkNode.objects.graph_stats()
        # b1 and b2 are depth 2, root is 0
        self.assertEqual(stats["max_depth"], 2)

    def test_density(self):
        stats = NetworkNode.objects.graph_stats()
        # density = 6 / (7 * 6) = 1/7
        self.assertAlmostEqual(stats["density"], 6 / 42)

    def test_component_count(self):
        stats = NetworkNode.objects.graph_stats()
        self.assertEqual(stats["component_count"], 2)

    def test_empty_graph(self):
        NetworkNode.objects.all().delete()
        stats = NetworkNode.objects.graph_stats()
        self.assertEqual(stats["node_count"], 0)
        self.assertEqual(stats["edge_count"], 0)
        self.assertEqual(stats["component_count"], 0)
        self.assertAlmostEqual(stats["density"], 0.0)


class QueryBuilderMethodsTestCase(DAGFixtureMixin, TestCase):
    def test_id_list(self):
        q = AncestorQuery(instance=self.b1)
        id_list = q.id_list()
        self.assertIn(self.root.pk, id_list)
        self.assertIn(self.a1.pk, id_list)

    def test_str(self):
        q = AncestorQuery(instance=self.a1)
        result = str(q)
        self.assertIsInstance(result, str)

    def test_repr(self):
        q = DescendantQuery(instance=self.root)
        result = repr(q)
        self.assertIsInstance(result, str)
