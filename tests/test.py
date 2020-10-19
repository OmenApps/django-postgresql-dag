import multiprocessing

from django.test import TestCase
from django.core.exceptions import ValidationError
from django_postgresql_dag.models import NodeNotReachableException
# from .dag_output import expected_dag_output
from .models import NetworkNode, NetworkEdge


node_name_list = ["root", "a1", "a2", "a3", "b1", "b2", "b3", "b4", "c1", "c2"]


class DagTestCase(TestCase):    

    def setUp(self):
        for node in node_name_list:
            NetworkNode.objects.create(name=node)
        
    def test_01_objects_were_created(self):
        for node in node_name_list:
            self.assertEqual(NetworkNode.objects.get(name=f"{node}").name, f"{node}")

    def test_02_dag(self):

        # Get nodes
        for node in node_name_list:
            globals()[f"{node}"] = NetworkNode.objects.get(name=node)

        # Creates a DAG
        root.add_child(a1)
        b1.add_parent(a1)

        tree = root.descendants_tree()
        # {<ConcreteNode: # 5>: {<ConcreteNode: # 7>: {}}}
        self.assertIn(a1, tree)
        self.assertEqual(len(tree), 1)
        self.assertIn(b1, tree[a1])
        self.assertEqual(tree[a1][b1], {})

        l = root.descendant_ids()
        self.assertEqual(l, [12, 15])

        root.add_child(a2)
        a3.add_parent(root)
        a3.add_child(b3)
        a3.add_child(b4)
        b3.add_child(c1)
        l = root.descendant_ids()
        self.assertEqual(l, [12, 13, 14, 15, 17, 18, 19])

        a1.add_child(b2)
        a2.add_child(b2)
        b3.add_child(c2)
        b4.add_child(c1)

        # Try to add a node that is already an ancestor
        try:
            b3.add_parent(c1)
        except ValidationError as e:
            self.assertEqual(e.message, 'The object is an ancestor.')

        # Try to add a node that is already an ancestor (alternate method)
        try:
            c1.add_child(b3)
        except ValidationError as e:
            self.assertEqual(e.message, 'The object is an ancestor.')

        # Try to add a node as it's own child
        try:
            b3.add_child(b3)
        except ValidationError as e:
            self.assertEqual(e.message, 'The object is an ancestor.')

        # Verify that the three methods work
        tree = root.descendants_tree()
        self.assertIn(a1, tree)
        self.assertIn(a2, tree)
        self.assertIn(a3, tree)
        self.assertIn(b2, tree[a1])
        self.assertIn(b1, tree[a1])
        self.assertIn(b2, tree[a2])
        self.assertIn(b3, tree[a3])
        self.assertIn(b4, tree[a3])
        self.assertIn(c2, tree[a3][b3])
        self.assertIn(c1, tree[a3][b3])
        self.assertIn(c1, tree[a3][b4])

        self.assertEqual(len(tree), 3)
        self.assertEqual(len(tree[a3]), 2)
        self.assertEqual(len(tree[a3][b4]), 1)

        # Check distance between nodes
        self.assertEqual(root.distance(c1), 3)

        # Test additional fields for edge
        self.assertEqual(b3.children.through.objects.filter(child=c1)[0].name, 'b3 c1')

        self.assertTrue([p.name for p in root.shortest_path(c1)] == ['root', 'a3', 'b3', 'c1'] or [p.name for p in c1.shortest_path(root, directional=False)] == ['root', 'a3', 'b4', 'c1'])

        try:
            [p.name for p in c1.shortest_path(root)]
        except Exception as e:
            self.assertRaises(NodeNotReachableException)

        self.assertTrue([p.name for p in c1.shortest_path(root, directional=False)] == ['root', 'a3', 'b3', 'c1'] or [p.name for p in c1.shortest_path(root, directional=False)] == ['root', 'a3', 'b4', 'c1'])

        self.assertEqual([p.name for p in root.get_leaves()], ['b2', 'c1', 'c2', 'b1'])
        self.assertEqual([p.name for p in c2.get_roots()], ['root'])

        self.assertTrue(root.is_root())
        self.assertTrue(c1.is_leaf())
        self.assertFalse(c1.is_root())
        self.assertFalse(root.is_leaf())
        self.assertFalse(a1.is_leaf())
        self.assertFalse(a1.is_root())

        # Remove a node and test island
        self.assertTrue(c2 in b3.descendants())
        self.assertEqual([p.name for p in c2.ancestors()], ['root', 'a3', 'b3'])
        c2.remove_parent(b3)
        self.assertFalse(c2 in b3.descendants())
        self.assertEqual([p.name for p in c2.ancestors()], [])
        self.assertTrue(c2.is_island())

    def test_03_deep_dag(self):
        """
        Create a deep graph and check that graph operations run in a
        reasonable amount of time (linear in size of graph, not
        exponential).
        """
        def run_test():
            # There are on the order of 1 million paths through the graph, so
            # results for intermediate nodes need to be cached
            n = 20  # Keep it an even number

            for i in range(2*n):
                NetworkNode(pk=i, name=str(i)).save()

            # Create edges
            for i in range(0, 2*n - 2, 2):
                p1 = NetworkNode.objects.get(pk=i)
                p2 = NetworkNode.objects.get(pk=i+1)
                p3 = NetworkNode.objects.get(pk=i+2)
                p4 = NetworkNode.objects.get(pk=i+3)

                p1.add_child(p3)
                p1.add_child(p4)
                p2.add_child(p3)
                p2.add_child(p4)

            # Compute descendants of a root node
            NetworkNode.objects.get(pk=0).descendants()

            # Compute ancestors of a leaf node
            NetworkNode.objects.get(pk=2*n - 1).ancestors()

            # Connect the first-created node to the last-created node
            NetworkNode.objects.get(pk=0).add_child(NetworkNode.objects.get(pk=2*n - 1))

            first = NetworkNode.objects.get(name="0")

            last = NetworkNode.objects.get(name=str(n-1))

            self.assertEqual(first.distance(last, max_depth=n), n/2 - 1)

        # Run the test, raising an error if the code times out
        p = multiprocessing.Process(target=run_test)
        p.start()
        p.join(10)  # Seconds allowed to live
        if p.is_alive():
            p.terminate()
            p.join()
            raise RuntimeError('Graph operations take too long!')
