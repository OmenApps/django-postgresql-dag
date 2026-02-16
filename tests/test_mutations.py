from django.core.exceptions import ValidationError
from django.test import TestCase

from tests.helpers import CheckLongTestCaseMixin, TenNodeDAGFixtureMixin, log, node_name_list
from tests.testapp.models import NetworkEdge, NetworkNode


class NodeCreationTestCase(TestCase):
    def setUp(self):
        for node in node_name_list:
            NetworkNode.objects.create(name=node)

    def test_objects_were_created(self):
        log.debug("Creating objects")
        for node in node_name_list:
            self.assertEqual(NetworkNode.objects.get(name=f"{node}").name, f"{node}")
        log.debug("Done creating objects")


class CircularDependencyTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_add_ancestor_as_parent_raises(self):
        try:
            self.b3.add_parent(self.c1)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")

    def test_add_ancestor_as_child_raises(self):
        try:
            self.c1.add_child(self.b3)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")

    def test_add_self_as_child_raises(self):
        try:
            self.b3.add_child(self.b3)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")


class RemovalTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_remove_parent_creates_island(self):
        self.assertTrue(self.c2 in self.b3.descendants())
        self.assertEqual([p.name for p in self.c2.ancestors()], ["root", "a3", "b3"])
        self.c2.remove_parent(self.b3)
        self.assertFalse(self.c2 in self.b3.descendants())
        self.assertEqual([p.name for p in self.c2.ancestors()], [])
        self.assertTrue(self.c2.is_island())

    def test_remove_child_preserves_other_connections(self):
        self.assertTrue(self.c1 in self.b3.descendants())
        self.assertEqual([p.name for p in self.c1.ancestors()], ["root", "a3", "b3", "b4"])
        self.b3.remove_child(self.c1)
        self.assertFalse(self.c1 in self.b3.descendants())
        self.assertEqual([p.name for p in self.c1.ancestors()], ["root", "a3", "b4"])
        self.assertFalse(self.c1.is_island())


class RemoveWithDeleteTestCase(TestCase):
    def setUp(self):
        self.root = NetworkNode.objects.create(name="root")
        self.child1 = NetworkNode.objects.create(name="child1")
        self.child2 = NetworkNode.objects.create(name="child2")
        self.parent2 = NetworkNode.objects.create(name="parent2")

        self.root.add_child(self.child1)
        self.root.add_child(self.child2)
        self.parent2.add_child(self.child1)

    def test_remove_child_with_delete_node(self):
        self.root.remove_child(self.child2, delete_node=True)
        self.assertFalse(NetworkNode.objects.filter(name="child2").exists())

    def test_remove_all_children(self):
        """remove_child with no arg removes edges to all children"""
        self.root.remove_child()
        self.assertEqual(self.root.children.count(), 0)
        # Nodes still exist
        self.assertTrue(NetworkNode.objects.filter(name="child1").exists())

    def test_remove_all_children_with_delete(self):
        self.root.remove_child(delete_node=True)
        self.assertEqual(self.root.children.count(), 0)
        self.assertFalse(NetworkNode.objects.filter(name="child1").exists())
        self.assertFalse(NetworkNode.objects.filter(name="child2").exists())

    def test_remove_parent_with_delete_node(self):
        self.child1.remove_parent(self.parent2, delete_node=True)
        self.assertFalse(NetworkNode.objects.filter(name="parent2").exists())

    def test_remove_all_parents(self):
        """remove_parent with no arg removes edges to all parents"""
        self.child1.remove_parent()
        self.assertEqual(self.child1.parents.count(), 0)
        # Nodes still exist
        self.assertTrue(NetworkNode.objects.filter(name="root").exists())

    def test_remove_all_parents_with_delete(self):
        self.child1.remove_parent(delete_node=True)
        self.assertEqual(self.child1.parents.count(), 0)
        self.assertFalse(NetworkNode.objects.filter(name="root").exists())
        self.assertFalse(NetworkNode.objects.filter(name="parent2").exists())


class MultilinkedTestCase(CheckLongTestCaseMixin, TestCase):
    def test_multilinked_nodes(self):
        log.debug("Test deletion of nodes two nodes with multiple shared edges")

        shared_edge_count = 5

        def create_multilinked_nodes(shared_edge_count):
            log.debug("Creating multiple links between a parent and child node")
            child_node = NetworkNode.objects.create()
            parent_node = NetworkNode.objects.create()

            # Call this multiple times to create multiple edges between same parent/child
            for _ in range(shared_edge_count):
                child_node.add_parent(parent_node)

            return child_node, parent_node

        def delete_parents():
            child_node, parent_node = create_multilinked_nodes(shared_edge_count)

            # Refresh the related manager
            child_node.refresh_from_db()

            self.assertEqual(child_node.parents.count(), shared_edge_count)
            log.debug(f"Initial parents count: {child_node.parents.count()}")
            child_node.remove_parent(parent_node)
            self.assertEqual(child_node.parents.count(), 0)
            log.debug(f"Final parents count: {child_node.parents.count()}")

        def delete_children():
            child_node, parent_node = create_multilinked_nodes(shared_edge_count)

            # Refresh the related manager
            parent_node.refresh_from_db()

            self.assertEqual(parent_node.children.count(), shared_edge_count)
            log.debug(f"Initial children count: {parent_node.children.count()}")
            parent_node.remove_child(child_node)
            self.assertEqual(parent_node.children.count(), 0)
            log.debug(f"Final children count: {parent_node.children.count()}")

        delete_parents()
        delete_children()


class InsertNodeTestCase(TestCase):
    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n3 = NetworkNode.objects.create(name="n3")
        self.n1.add_child(self.n3)
        self.original_edge = NetworkEdge.objects.get(parent=self.n1, child=self.n3)

    def test_insert_node_basic(self):
        """Insert n2 between n1 and n3 without cloning"""
        NetworkEdge.objects.insert_node(self.original_edge, self.n2)
        # n1 -> n2 -> n3 now
        self.assertTrue(NetworkEdge.objects.filter(parent=self.n1, child=self.n2).exists())
        self.assertTrue(NetworkEdge.objects.filter(parent=self.n2, child=self.n3).exists())
        # Original edge should be deleted
        self.assertFalse(NetworkEdge.objects.filter(pk=self.original_edge.pk).exists())

    def test_insert_node_clone_rootside(self):
        def pre_save(new_edge):
            new_edge.name = ""
            return new_edge

        rootside, leafside = NetworkEdge.objects.insert_node(
            self.original_edge, self.n2, clone_to_rootside=True, pre_save=pre_save
        )
        self.assertIsNotNone(rootside)
        self.assertIsNone(leafside)
        self.assertEqual(rootside.parent, self.n1)
        self.assertEqual(rootside.child, self.n2)

    def test_insert_node_clone_leafside(self):
        def pre_save(new_edge):
            new_edge.name = ""
            return new_edge

        rootside, leafside = NetworkEdge.objects.insert_node(
            self.original_edge, self.n2, clone_to_leafside=True, pre_save=pre_save
        )
        self.assertIsNone(rootside)
        self.assertIsNotNone(leafside)
        self.assertEqual(leafside.parent, self.n2)
        self.assertEqual(leafside.child, self.n3)

    def test_insert_node_with_post_save(self):
        def pre_save(new_edge):
            new_edge.name = ""
            return new_edge

        def post_save(new_edge):
            return new_edge

        rootside, leafside = NetworkEdge.objects.insert_node(
            self.original_edge,
            self.n2,
            clone_to_rootside=True,
            clone_to_leafside=True,
            pre_save=pre_save,
            post_save=post_save,
        )
        self.assertIsNotNone(rootside)
        self.assertIsNotNone(leafside)


class EdgeSaveOptionsTestCase(TestCase):
    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")

    def test_disable_circular_check(self):
        """Should save without running circular_checker"""
        self.n1.add_child(self.n2, disable_circular_check=True)
        self.assertTrue(NetworkEdge.objects.filter(parent=self.n1, child=self.n2).exists())

    def test_allow_duplicate_edges_false(self):
        """Should raise ValidationError when exact duplicate edge exists"""
        self.n1.add_child(self.n2)
        with self.assertRaises(ValidationError) as ctx:
            self.n1.add_child(self.n2, allow_duplicate_edges=False)
        self.assertEqual(ctx.exception.message, "An edge already exists between these nodes.")

    def test_duplicate_edge_allowed_by_default(self):
        """By default, duplicate edges are allowed"""
        self.n1.add_child(self.n2)
        self.n1.add_child(self.n2)
        self.assertEqual(NetworkEdge.objects.filter(parent=self.n1, child=self.n2).count(), 2)


class RedundantEdgeCheckerTestCase(TestCase):
    """Tests for the redundant_edge_checker (transitive reachability check)."""

    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n3 = NetworkNode.objects.create(name="n3")
        self.n1.add_child(self.n2)
        self.n2.add_child(self.n3)

    def test_redundant_edge_blocked_when_disabled(self):
        """Adding n1->n3 when n3 is already reachable via n1->n2->n3 should raise."""
        with self.assertRaises(ValidationError) as ctx:
            self.n1.add_child(self.n3, allow_redundant_edges=False)
        self.assertEqual(ctx.exception.message, "The child is already reachable from the parent.")

    def test_redundant_edge_allowed_by_default(self):
        """By default, redundant edges are allowed."""
        self.n1.add_child(self.n3)
        self.assertTrue(NetworkEdge.objects.filter(parent=self.n1, child=self.n3).exists())

    def test_duplicate_checker_does_not_block_redundant(self):
        """duplicate_edge_checker should not block n1->n3 (not an exact duplicate)."""
        self.n1.add_child(self.n3, allow_duplicate_edges=False)
        self.assertTrue(NetworkEdge.objects.filter(parent=self.n1, child=self.n3).exists())

    def test_both_checkers_together(self):
        """Both checks can be enabled at the same time."""
        # First add n1->n3 (redundant but allowed since we only block duplicates here)
        self.n1.add_child(self.n3, allow_duplicate_edges=False)
        # Now adding the exact same edge should fail on duplicate check
        with self.assertRaises(ValidationError) as ctx:
            self.n1.add_child(self.n3, allow_duplicate_edges=False, allow_redundant_edges=False)
        self.assertEqual(ctx.exception.message, "An edge already exists between these nodes.")

    def test_add_parent_passes_through_allow_redundant_edges(self):
        """add_parent should also support allow_redundant_edges."""
        with self.assertRaises(ValidationError):
            self.n3.add_parent(self.n1, allow_redundant_edges=False)
