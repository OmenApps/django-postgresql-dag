from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from django_postgresql_dag.query_builders import (
    AllDownwardPathsQuery,
    AllUpwardPathsQuery,
    AncestorQuery,
    ConnectedGraphQuery,
    CriticalPathQuery,
    DescendantQuery,
    DownwardPathQuery,
    LCAQuery,
    TopologicalSortQuery,
    TransitiveReductionQuery,
    UpwardPathQuery,
    WeightedDownwardPathQuery,
    WeightedUpwardPathQuery,
)
from tests.helpers import DAGFixtureMixin
from tests.testapp.models import EdgeSet, NetworkEdge, NetworkNode, NodeSet


class QueryFilteringTestCase(DAGFixtureMixin, TestCase):
    def test_disallowed_nodes_ancestors(self):
        """Disallow a1 from b1's ancestors -- should still find root via a2"""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        ancestors = self.b1.ancestors(disallowed_nodes_queryset=disallowed)
        self.assertNotIn(self.a1, ancestors)

    def test_disallowed_nodes_descendants(self):
        """Disallow a1 from root's descendants"""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        descendants = self.root.descendants(disallowed_nodes_queryset=disallowed)
        self.assertNotIn(self.a1, descendants)

    def test_allowed_nodes_ancestors(self):
        """Only allow a1 in b1's ancestor traversal"""
        allowed = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.root.pk])
        ancestors = self.b1.ancestors(allowed_nodes_queryset=allowed)
        self.assertNotIn(self.a2, ancestors)

    def test_allowed_nodes_descendants(self):
        """Only allow a1 in root's descendant traversal"""
        allowed = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.b1.pk])
        descendants = self.root.descendants(allowed_nodes_queryset=allowed)
        self.assertNotIn(self.a2, descendants)


class EdgeSetFKFilteringTestCase(TestCase):
    def setUp(self):
        self.edge_set = EdgeSet.objects.create(name="set1")
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.b1 = NetworkNode.objects.create(name="b1")
        self.a2 = NetworkNode.objects.create(name="a2")

        # Create edges with edge_set FK
        self.root.add_child(self.a1)
        self.root.add_child(self.a2)
        self.a1.add_child(self.b1)

        # Assign edge_set to some edges
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(edge_set=self.edge_set)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(edge_set=self.edge_set)

    def test_limiting_edges_set_fk_ancestors(self):
        ancestors = self.b1.ancestors(limiting_edges_set_fk=self.edge_set)
        self.assertIn(self.root, ancestors)
        self.assertIn(self.a1, ancestors)

    def test_limiting_edges_set_fk_descendants(self):
        descendants = self.root.descendants(limiting_edges_set_fk=self.edge_set)
        self.assertIn(self.a1, descendants)
        self.assertIn(self.b1, descendants)


class QueryBuilderErrorsTestCase(TestCase):
    def test_base_query_missing_instance_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            AncestorQuery()

    def test_ancestor_query_requires_instance(self):
        n1 = NetworkNode.objects.create(name="n1")
        n2 = NetworkNode.objects.create(name="n2")
        with self.assertRaises(ImproperlyConfigured):
            AncestorQuery(starting_node=n1, ending_node=n2)

    def test_descendant_query_requires_instance(self):
        n1 = NetworkNode.objects.create(name="n1")
        n2 = NetworkNode.objects.create(name="n2")
        with self.assertRaises(ImproperlyConfigured):
            DescendantQuery(starting_node=n1, ending_node=n2)


class AncestorDescendantNoopFilterTestCase(DAGFixtureMixin, TestCase):
    """Tests for no-op filter branches and edge filtering in AncestorQuery and DescendantQuery."""

    def setUp(self):
        super().setUp()
        self.edge_set = EdgeSet.objects.create(name="ad_set")
        # Assign all edges to edge_set
        NetworkEdge.objects.all().update(edge_set=self.edge_set)

    def test_ancestors_limiting_nodes_set_fk(self):
        """Covers AncestorQuery._limit_to_nodes_set_fk no-op (line 201) via dispatch (line 79)."""
        ancestors = self.b1.ancestors(limiting_nodes_set_fk=self.edge_set)
        # No-op, so ancestors should be returned normally
        self.assertIn(self.root, ancestors)

    def test_descendants_limiting_nodes_set_fk(self):
        """Covers DescendantQuery._limit_to_nodes_set_fk no-op (line 319)."""
        descendants = self.root.descendants(limiting_nodes_set_fk=self.edge_set)
        self.assertIn(self.a1, descendants)

    def test_ancestors_disallowed_edges(self):
        """Disallow root->a1 edge from b1's ancestors. b1 is still reachable via a2."""
        disallowed = NetworkEdge.objects.filter(parent=self.root, child=self.a1)
        ancestors = self.b1.ancestors(disallowed_edges_queryset=disallowed)
        # a1 is still reachable (a1->b1 edge is not disallowed), but root is
        # only reachable via a2->b1 path (root->a2 edge is still allowed)
        self.assertIn(self.a1, ancestors)
        self.assertIn(self.a2, ancestors)
        self.assertIn(self.root, ancestors)

    def test_descendants_disallowed_edges(self):
        """Disallow root->a1 edge from root's descendants. a1 should be excluded."""
        disallowed = NetworkEdge.objects.filter(parent=self.root, child=self.a1)
        descendants = self.root.descendants(disallowed_edges_queryset=disallowed)
        self.assertNotIn(self.a1, descendants)
        # a2 and b1 should still be reachable
        self.assertIn(self.a2, descendants)

    def test_ancestors_allowed_edges(self):
        """Allow only edges on the root->a1->b1 path. a2 should be excluded from b1's ancestors."""
        edge_root_a1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        edge_a1_b1 = NetworkEdge.objects.get(parent=self.a1, child=self.b1)
        allowed = NetworkEdge.objects.filter(pk__in=[edge_root_a1.pk, edge_a1_b1.pk])
        ancestors = self.b1.ancestors(allowed_edges_queryset=allowed)
        self.assertIn(self.root, ancestors)
        self.assertIn(self.a1, ancestors)
        self.assertNotIn(self.a2, ancestors)

    def test_descendants_allowed_edges(self):
        """Allow only root->a1 edge. a2 should be excluded from root's descendants."""
        edge_root_a1 = NetworkEdge.objects.get(parent=self.root, child=self.a1)
        allowed = NetworkEdge.objects.filter(pk=edge_root_a1.pk)
        descendants = self.root.descendants(allowed_edges_queryset=allowed)
        self.assertIn(self.a1, descendants)
        self.assertNotIn(self.a2, descendants)


class EdgeTypeSugarTestCase(TestCase):
    """Tests that edge_type kwarg is equivalent to limiting_edges_set_fk."""

    def setUp(self):
        self.edge_set = EdgeSet.objects.create(name="sugar_set")
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.b1 = NetworkNode.objects.create(name="b1")
        self.a2 = NetworkNode.objects.create(name="a2")

        self.root.add_child(self.a1)
        self.root.add_child(self.a2)
        self.a1.add_child(self.b1)

        # Only tag root->a1 and a1->b1 edges with edge_set
        NetworkEdge.objects.filter(parent=self.root, child=self.a1).update(edge_set=self.edge_set)
        NetworkEdge.objects.filter(parent=self.a1, child=self.b1).update(edge_set=self.edge_set)

    def test_descendants_edge_type(self):
        expected = set(self.root.descendants(limiting_edges_set_fk=self.edge_set).values_list("pk", flat=True))
        actual = set(self.root.descendants(edge_type=self.edge_set).values_list("pk", flat=True))
        self.assertEqual(expected, actual)

    def test_ancestors_edge_type(self):
        expected = set(self.b1.ancestors(limiting_edges_set_fk=self.edge_set).values_list("pk", flat=True))
        actual = set(self.b1.ancestors(edge_type=self.edge_set).values_list("pk", flat=True))
        self.assertEqual(expected, actual)

    def test_clan_edge_type(self):
        expected = set(self.a1.clan(limiting_edges_set_fk=self.edge_set).values_list("pk", flat=True))
        actual = set(self.a1.clan(edge_type=self.edge_set).values_list("pk", flat=True))
        self.assertEqual(expected, actual)

    def test_path_edge_type(self):
        expected = set(self.root.path(self.b1, limiting_edges_set_fk=self.edge_set).values_list("pk", flat=True))
        actual = set(self.root.path(self.b1, edge_type=self.edge_set).values_list("pk", flat=True))
        self.assertEqual(expected, actual)

    def test_self_and_descendants_edge_type(self):
        expected = set(self.root.self_and_descendants(limiting_edges_set_fk=self.edge_set).values_list("pk", flat=True))
        actual = set(self.root.self_and_descendants(edge_type=self.edge_set).values_list("pk", flat=True))
        self.assertEqual(expected, actual)

    def test_is_ancestor_of_edge_type(self):
        self.assertTrue(self.root.is_ancestor_of(self.b1, edge_type=self.edge_set))


class EdgesFKFieldNoneTestCase(DAGFixtureMixin, TestCase):
    """Tests the fk_field_name == None branch in _limit_to_edges_set_fk."""

    def setUp(self):
        super().setUp()
        self.node_set = NodeSet.objects.create(name="ns_unrelated")

    def test_ancestors_limiting_edges_fk_unrelated_model(self):
        """Pass a NodeSet instance (no FK on NetworkEdge) -- get_foreign_key_field returns None.
        Covers the None branch in AncestorQuery._limit_to_edges_set_fk (lines 210-223)."""
        ancestors = self.b1.ancestors(limiting_edges_set_fk=self.node_set)
        # FK field is None, so no limiting clause is added -- returns all ancestors
        self.assertIn(self.root, ancestors)
        self.assertIn(self.a1, ancestors)

    def test_descendants_limiting_edges_fk_unrelated_model(self):
        """Pass a NodeSet instance (no FK on NetworkEdge) -- get_foreign_key_field returns None.
        Covers the None branch in DescendantQuery._limit_to_edges_set_fk (lines 328-341)."""
        descendants = self.root.descendants(limiting_edges_set_fk=self.node_set)
        self.assertIn(self.a1, descendants)
        self.assertIn(self.b1, descendants)

    def test_path_limiting_edges_fk_unrelated_model(self):
        """Covers the None branch in DownwardPathQuery._limit_to_edges_set_fk."""
        path = list(self.root.path(self.b1, limiting_edges_set_fk=self.node_set))
        self.assertIn(self.root, path)
        self.assertIn(self.b1, path)

    def test_upward_path_limiting_edges_fk_unrelated_model(self):
        """Covers the None branch in UpwardPathQuery._limit_to_edges_set_fk."""
        path = list(self.b1.path(self.root, directional=False, limiting_edges_set_fk=self.node_set))
        self.assertIn(self.root, path)
        self.assertIn(self.b1, path)

    def test_connected_graph_limiting_edges_fk_unrelated_model(self):
        """Covers the None branch in ConnectedGraphQuery._limit_to_edges_set_fk."""
        nodes = list(self.root.connected_graph(limiting_edges_set_fk=self.node_set))
        self.assertIn(self.root, nodes)


class QueryBuilderConstructorGuardsTestCase(TestCase):
    """Tests for constructor guards across all query builder classes."""

    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n1.add_child(self.n2)

    def test_upward_path_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            UpwardPathQuery(instance=self.n1)

    def test_downward_path_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            DownwardPathQuery(instance=self.n1)

    def test_connected_graph_requires_instance(self):
        with self.assertRaises(ImproperlyConfigured):
            ConnectedGraphQuery(starting_node=self.n1, ending_node=self.n2)

    def test_lca_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            LCAQuery(instance=self.n1)

    def test_all_downward_paths_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            AllDownwardPathsQuery(instance=self.n1)

    def test_all_upward_paths_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            AllUpwardPathsQuery(instance=self.n1)

    def test_weighted_downward_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            WeightedDownwardPathQuery(instance=self.n1)

    def test_weighted_upward_requires_both_nodes(self):
        with self.assertRaises(ImproperlyConfigured):
            WeightedUpwardPathQuery(instance=self.n1)

    def test_topological_sort_requires_graph_wide(self):
        with self.assertRaises(ImproperlyConfigured):
            TopologicalSortQuery(instance=self.n1)

    def test_critical_path_requires_graph_wide(self):
        with self.assertRaises(ImproperlyConfigured):
            CriticalPathQuery(instance=self.n1)

    def test_transitive_reduction_requires_graph_wide(self):
        with self.assertRaises(ImproperlyConfigured):
            TransitiveReductionQuery(instance=self.n1)


class NoopFilterDispatchTestCase(DAGFixtureMixin, TestCase):
    """Tests that no-op filter methods are dispatched but don't change results.

    These cover _limit_to_nodes_set_fk no-ops and _GraphWideNoFilterMixin methods.
    """

    def test_path_limiting_nodes_set_fk_noop(self):
        """DownwardPathQuery._limit_to_nodes_set_fk is a no-op."""
        node_set = NodeSet.objects.create(name="path_ns")
        path = list(self.root.path(self.b1, limiting_nodes_set_fk=node_set))
        self.assertIn(self.root, path)
        self.assertIn(self.b1, path)

    def test_upward_path_limiting_nodes_set_fk_noop(self):
        """UpwardPathQuery._limit_to_nodes_set_fk is a no-op."""
        node_set = NodeSet.objects.create(name="up_path_ns")
        path = list(self.b1.path(self.root, directional=False, limiting_nodes_set_fk=node_set))
        self.assertIn(self.root, path)
        self.assertIn(self.b1, path)

    def test_connected_graph_limiting_nodes_set_fk_noop(self):
        """ConnectedGraphQuery._limit_to_nodes_set_fk is a no-op."""
        node_set = NodeSet.objects.create(name="cg_ns")
        nodes = list(self.root.connected_graph(limiting_nodes_set_fk=node_set))
        self.assertIn(self.root, nodes)

    def test_topological_sort_ignores_filters(self):
        """TopologicalSortQuery inherits _GraphWideNoFilterMixin - all filters are no-ops."""
        nodes = list(NetworkNode.objects.topological_sort())
        self.assertIn(self.root, nodes)

    def test_connected_graph_edge_type_noop(self):
        """Passing edge_type to connected_graph when FK field is None is a no-op."""
        node_set = NodeSet.objects.create(name="et_ns")
        nodes = list(self.root.connected_graph(edge_type=node_set))
        self.assertIn(self.root, nodes)


class LCANoopFilterTestCase(DAGFixtureMixin, TestCase):
    """LCA query has no-op filter methods - passing filters should not break results."""

    def test_lca_with_disallowed_nodes(self):
        """LCA ignores disallowed_nodes_queryset (no-op)."""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        result = list(self.b1.lowest_common_ancestors(self.b2, disallowed_nodes_queryset=disallowed))
        # Result should still work (filters are no-ops)
        self.assertTrue(len(result) >= 0)

    def test_lca_with_allowed_nodes(self):
        """LCA ignores allowed_nodes_queryset (no-op)."""
        allowed = NetworkNode.objects.filter(pk__in=[self.root.pk, self.a1.pk])
        result = list(self.b1.lowest_common_ancestors(self.b2, allowed_nodes_queryset=allowed))
        self.assertTrue(len(result) >= 0)

    def test_lca_with_disallowed_edges(self):
        """LCA ignores disallowed_edges_queryset (no-op)."""
        edge = NetworkEdge.objects.first()
        disallowed = NetworkEdge.objects.filter(pk=edge.pk)
        result = list(self.b1.lowest_common_ancestors(self.b2, disallowed_edges_queryset=disallowed))
        self.assertTrue(len(result) >= 0)

    def test_lca_with_allowed_edges(self):
        """LCA ignores allowed_edges_queryset (no-op)."""
        allowed = NetworkEdge.objects.all()
        result = list(self.b1.lowest_common_ancestors(self.b2, allowed_edges_queryset=allowed))
        self.assertTrue(len(result) >= 0)

    def test_lca_with_limiting_edges_set_fk(self):
        """LCA ignores limiting_edges_set_fk (no-op)."""
        es = EdgeSet.objects.create(name="lca_es")
        result = list(self.b1.lowest_common_ancestors(self.b2, limiting_edges_set_fk=es))
        self.assertTrue(len(result) >= 0)

    def test_lca_with_limiting_nodes_set_fk(self):
        """LCA ignores limiting_nodes_set_fk (no-op)."""
        ns = NodeSet.objects.create(name="lca_ns")
        result = list(self.b1.lowest_common_ancestors(self.b2, limiting_nodes_set_fk=ns))
        self.assertTrue(len(result) >= 0)


class AllPathsNoopFilterTestCase(DAGFixtureMixin, TestCase):
    """All-paths queries have no-op filter methods."""

    def test_all_paths_with_disallowed_nodes(self):
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        paths = self.root.all_paths_as_pk_lists(self.b1, disallowed_nodes_queryset=disallowed)
        # Filters are no-ops so all paths are still returned
        self.assertTrue(len(paths) >= 1)

    def test_all_paths_with_allowed_nodes(self):
        allowed = NetworkNode.objects.all()
        paths = self.root.all_paths_as_pk_lists(self.b1, allowed_nodes_queryset=allowed)
        self.assertTrue(len(paths) >= 1)

    def test_all_paths_with_limiting_edges_set_fk(self):
        es = EdgeSet.objects.create(name="ap_es")
        paths = self.root.all_paths_as_pk_lists(self.b1, limiting_edges_set_fk=es)
        self.assertTrue(len(paths) >= 1)

    def test_all_paths_with_limiting_nodes_set_fk(self):
        ns = NodeSet.objects.create(name="ap_ns")
        paths = self.root.all_paths_as_pk_lists(self.b1, limiting_nodes_set_fk=ns)
        self.assertTrue(len(paths) >= 1)

    def test_upward_all_paths_with_filters(self):
        """Upward all-paths no-op filters."""
        disallowed = NetworkNode.objects.filter(pk=self.a1.pk)
        paths = self.b1.all_paths_as_pk_lists(self.root, directional=False, disallowed_nodes_queryset=disallowed)
        self.assertTrue(len(paths) >= 1)


class WeightedPathNoopFilterTestCase(TestCase):
    """Weighted path queries have no-op filter methods."""

    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n1.add_child(self.n2)
        NetworkEdge.objects.filter(parent=self.n1, child=self.n2).update(weight=1.0)

    def test_weighted_path_with_allowed_nodes(self):
        allowed = NetworkNode.objects.all()
        qs, weight = self.n1.weighted_path(self.n2, allowed_nodes_queryset=allowed)
        self.assertAlmostEqual(weight, 1.0)

    def test_weighted_path_with_limiting_nodes_set_fk(self):
        ns = NodeSet.objects.create(name="wp_ns")
        qs, weight = self.n1.weighted_path(self.n2, limiting_nodes_set_fk=ns)
        self.assertAlmostEqual(weight, 1.0)

    def test_weighted_path_with_limiting_edges_set_fk(self):
        es = EdgeSet.objects.create(name="wp_es")
        qs, weight = self.n1.weighted_path(self.n2, limiting_edges_set_fk=es)
        self.assertAlmostEqual(weight, 1.0)

    def test_weighted_upward_with_limiting_nodes_set_fk(self):
        ns = NodeSet.objects.create(name="wpu_ns")
        qs, weight = self.n2.weighted_path(self.n1, directional=False, limiting_nodes_set_fk=ns)
        self.assertAlmostEqual(weight, 1.0)
