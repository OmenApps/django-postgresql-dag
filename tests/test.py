import logging
import multiprocessing
import time

from django.test import TestCase
from django.core.exceptions import ValidationError
from django_postgresql_dag.models import NodeNotReachableException

# from .dag_output import expected_dag_output
from .models import NetworkNode, NetworkEdge

logging.basicConfig(level=logging.DEBUG)


node_name_list = ["root", "a1", "a2", "a3", "b1", "b2", "b3", "b4", "c1", "c2"]


class DagTestCase(TestCase):
    def setUp(self):
        for node in node_name_list:
            NetworkNode.objects.create(name=node)

    def test_01_objects_were_created(self):
        log = logging.getLogger("test_01")
        log.debug("Creating objects")
        for node in node_name_list:
            self.assertEqual(NetworkNode.objects.get(name=f"{node}").name, f"{node}")
        log.debug("Done creating objects")

    def test_02_dag(self):
        log = logging.getLogger("test_02_dag")

        # Get nodes
        log.debug("Getting nodes")
        for node in node_name_list:
            globals()[f"{node}"] = NetworkNode.objects.get(name=node)
        log.debug("Done getting nodes")

        # Creates a DAG
        root.add_child(a1)
        b1.add_parent(a1)

        log.debug("descendants_tree")
        tree = root.descendants_tree()
        self.assertIn(a1, tree)
        self.assertEqual(len(tree), 1)
        self.assertIn(b1, tree[a1])
        self.assertEqual(tree[a1][b1], {})

        log.debug("descendants part 1")
        root_descendants = root.descendants()
        self.assertNotIn(root, root_descendants)
        self.assertTrue(all(elem in root_descendants for elem in [a1, b1]))

        root.add_child(a2)
        a3.add_parent(root)
        a3.add_child(b3)
        a3.add_child(b4)
        b3.add_child(c1)
        
        log.debug("descendants part 2")
        root_descendants = root.descendants()
        self.assertNotIn(root, root_descendants)
        self.assertTrue(all(elem in root_descendants for elem in [a1, a2, a3, b1, b3, b4, c1]))

        log.debug("ancestors part 1")
        c1_ancestors = c1.ancestors()
        self.assertNotIn(c1, c1_ancestors)
        self.assertNotIn(b4, c1_ancestors)
        self.assertTrue(all(elem in c1_ancestors for elem in [root, a3, b3]))
        
        a1.add_child(b2)
        a2.add_child(b2)
        b3.add_child(c2)
        b4.add_child(c1)
        
        log.debug("ancestors part 2")
        c1_ancestors = c1.ancestors()
        self.assertNotIn(c1, c1_ancestors)
        self.assertTrue(all(elem in c1_ancestors for elem in [root, a3, b3, b4]))
        
        # Try to add a node that is already an ancestor
        try:
            b3.add_parent(c1)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")

        # Try to add a node that is already an ancestor (alternate method)
        try:
            c1.add_child(b3)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")

        # Try to add a node as it's own child
        try:
            b3.add_child(b3)
        except ValidationError as e:
            self.assertEqual(e.message, "The object is an ancestor.")

        # Verify that the tree methods work
        log.debug("descendants_tree")
        tree_from_root = root.descendants_tree()
        self.assertIn(a1, tree_from_root)
        self.assertIn(a2, tree_from_root)
        self.assertIn(a3, tree_from_root)
        self.assertIn(b2, tree_from_root[a1])
        self.assertIn(b1, tree_from_root[a1])
        self.assertIn(b2, tree_from_root[a2])
        self.assertIn(b3, tree_from_root[a3])
        self.assertIn(b4, tree_from_root[a3])
        self.assertIn(c2, tree_from_root[a3][b3])
        self.assertIn(c1, tree_from_root[a3][b3])
        self.assertIn(c1, tree_from_root[a3][b4])

        self.assertEqual(len(tree_from_root), 3)
        self.assertEqual(len(tree_from_root[a3]), 2)
        self.assertEqual(len(tree_from_root[a3][b4]), 1)

        log.debug("ancestors_tree")
        tree_from_leaf = c1.ancestors_tree()
        self.assertIn(b3, tree_from_leaf)
        self.assertIn(a3, tree_from_leaf[b3])
        self.assertIn(b4, tree_from_leaf)
        self.assertIn(a3, tree_from_leaf[b4])
        self.assertIn(root, tree_from_leaf[b4][a3])

        self.assertEqual(len(tree_from_leaf), 2)
        self.assertEqual(len(tree_from_leaf[b3]), 1)
        self.assertEqual(len(tree_from_leaf[b4]), 1)
        self.assertEqual(len(tree_from_leaf[b4][a3]), 1)

        # Check other ancestor methods
        log.debug("ancestors_and_self")
        self.assertEqual(a1.ancestors_and_self()[0], root)
        log.debug("ancestors_and_self")
        self.assertEqual(a1.ancestors_and_self()[1], a1)
        log.debug("self_and_ancestors")
        self.assertEqual(a1.self_and_ancestors()[0], a1)
        log.debug("self_and_ancestors")
        self.assertEqual(a1.self_and_ancestors()[1], root)

        # Check other descendant methods
        log.debug("descendants_and_self")
        self.assertEqual(b4.descendants_and_self()[0], c1)
        log.debug("descendants_and_self")
        self.assertEqual(b4.descendants_and_self()[1], b4)
        log.debug("self_and_descendants")
        self.assertEqual(b4.self_and_descendants()[0], b4)
        log.debug("self_and_descendants")
        self.assertEqual(b4.self_and_descendants()[1], c1)

        # Check clan methods
        log.debug("clan_ids")
        self.assertTrue(all(elem in a1.clan() for elem in [root, a1, b1, b2]))
        log.debug("clan")
        self.assertEqual(a1.clan()[0], root)
        log.debug("clan")
        self.assertEqual(a1.clan()[3], b2)

        # Check distance between nodes
        log.debug("distance")
        self.assertEqual(root.distance(c1), 3)

        # Test additional fields for edge
        self.assertEqual(b3.children.through.objects.filter(child=c1)[0].name, "b3 c1")
        self.assertEqual(b3.descendants_edges().first(), NetworkEdge.objects.get(parent=b3, child=c1))
        self.assertEqual(a1.ancestors_edges().first(), NetworkEdge.objects.get(parent=root, child=a1))
        self.assertTrue(NetworkEdge.objects.get(parent=a1, child=b2) in a1.clan_edges())
        self.assertTrue(NetworkEdge.objects.get(parent=a1, child=b1) in a1.clan_edges())
        self.assertTrue(NetworkEdge.objects.get(parent=root, child=a1) in a1.clan_edges())

        # Test shortest_path
        log.debug("path x2")
        self.assertTrue(
            [p.name for p in root.path(c1)] == ["root", "a3", "b3", "c1"]
            or [p.name for p in c1.path(root, directional=False)]
            == ["root", "a3", "b4", "c1"]
        )

        log.debug("path")
        try:
            [p.name for p in c1.shortest_path(root)]
        except Exception as e:
            self.assertRaises(NodeNotReachableException)

        log.debug("shortest_path x2")
        self.assertTrue(
            [p.name for p in c1.path(root, directional=False)]
            == ["c1", "b3", "a3", "root"]
            or [p.name for p in c1.path(root, directional=False)]
            == ["c1", "b4", "a3", "root"]
        )

        log.debug("get_leaves")
        self.assertEqual([p.name for p in root.leaves()], ["b2", "c1", "c2", "b1"])
        log.debug("get_roots")
        self.assertEqual([p.name for p in c2.roots()], ["root"])

        self.assertTrue(root.is_root())
        self.assertTrue(c1.is_leaf())
        self.assertFalse(c1.is_root())
        self.assertFalse(root.is_leaf())
        self.assertFalse(a1.is_leaf())
        self.assertFalse(a1.is_root())

        # Remove a node and test island
        log.debug("descendants")
        self.assertTrue(c2 in b3.descendants())
        log.debug("ancestors")
        self.assertEqual([p.name for p in c2.ancestors()], ["root", "a3", "b3"])
        c2.remove_parent(b3)
        log.debug("descendants")
        self.assertFalse(c2 in b3.descendants())
        log.debug("ancestors")
        self.assertEqual([p.name for p in c2.ancestors()], [])
        self.assertTrue(c2.is_island())

        # Remove a node and test that it is still connected elsewhere
        log.debug("descendants")
        self.assertTrue(c1 in b3.descendants())
        log.debug("ancestors")
        self.assertEqual([p.name for p in c1.ancestors()], ["root", "a3", "b3", "b4"])
        b3.remove_child(c1)
        log.debug("descendants")
        self.assertFalse(c1 in b3.descendants())
        log.debug("ancestors")
        self.assertEqual([p.name for p in c1.ancestors()], ["root", "a3", "b4"])
        self.assertFalse(c1.is_island())

        """
        Simulate a basic irrigation canal network
        """
        log = logging.getLogger("test_02_canal")

        node_name_list2 = [x for x in range(0, 201)]
        adjacency_list = [
            ["0", "1"],
            ["1", "2"],
            ["2", "3"],
            ["3", "4"],
            ["4", "5"],
            ["5", "6"],
            ["6", "7"],
            ["7", "8"],
            ["8", "9"],
            ["9", "10"],
            ["10", "11"],
            ["11", "12"],
            ["12", "13"],
            ["13", "14"],
            ["14", "15"],
            ["5", "16"],
            ["16", "17"],
            ["17", "18"],
            ["18", "19"],
            ["19", "20"],
            ["10", "21"],
            ["21", "22"],
            ["22", "23"],
            ["23", "24"],
            ["24", "25"],
            ["15", "26"],
            ["26", "27"],
            ["27", "28"],
            ["28", "29"],
            ["29", "30"],
            ["30", "31"],
            ["31", "32"],
            ["32", "33"],
            ["33", "34"],
            ["34", "35"],
            ["35", "36"],
            ["36", "37"],
            ["37", "38"],
            ["38", "39"],
            ["39", "40"],
            ["30", "41"],
            ["41", "42"],
            ["42", "43"],
            ["43", "44"],
            ["44", "45"],
            ["35", "46"],
            ["46", "47"],
            ["47", "48"],
            ["48", "49"],
            ["49", "50"],
            ["25", "51"],
            ["51", "52"],
            ["52", "53"],
            ["53", "54"],
            ["54", "55"],
            ["55", "56"],
            ["56", "57"],
            ["57", "58"],
            ["58", "59"],
            ["59", "60"],
            ["60", "61"],
            ["61", "62"],
            ["62", "63"],
            ["63", "64"],
            ["64", "65"],
            ["55", "66"],
            ["66", "67"],
            ["67", "68"],
            ["68", "69"],
            ["69", "70"],
            ["60", "71"],
            ["71", "72"],
            ["72", "73"],
            ["73", "74"],
            ["74", "75"],
            ["50", "76"],
            ["76", "77"],
            ["77", "78"],
            ["78", "79"],
            ["79", "80"],
            ["80", "81"],
            ["81", "82"],
            ["82", "83"],
            ["83", "84"],
            ["84", "85"],
            ["85", "86"],
            ["86", "87"],
            ["87", "88"],
            ["88", "89"],
            ["89", "90"],
            ["80", "91"],
            ["91", "92"],
            ["92", "93"],
            ["93", "94"],
            ["94", "95"],
            ["85", "96"],
            ["96", "97"],
            ["97", "98"],
            ["98", "99"],
            ["99", "100"],
            ["65", "101"],
            ["101", "102"],
            ["102", "103"],
            ["103", "104"],
            ["104", "105"],
            ["105", "106"],
            ["106", "107"],
            ["107", "108"],
            ["108", "109"],
            ["109", "110"],
            ["110", "111"],
            ["111", "112"],
            ["112", "113"],
            ["113", "114"],
            ["114", "115"],
            ["105", "116"],
            ["116", "117"],
            ["117", "118"],
            ["118", "119"],
            ["119", "120"],
            ["110", "121"],
            ["121", "122"],
            ["122", "123"],
            ["123", "124"],
            ["124", "125"],
            ["75", "126"],
            ["126", "127"],
            ["127", "128"],
            ["128", "129"],
            ["129", "130"],
            ["130", "131"],
            ["131", "132"],
            ["132", "133"],
            ["133", "134"],
            ["134", "135"],
            ["135", "136"],
            ["136", "137"],
            ["137", "138"],
            ["138", "139"],
            ["139", "140"],
            ["130", "141"],
            ["141", "142"],
            ["142", "143"],
            ["143", "144"],
            ["144", "145"],
            ["135", "146"],
            ["146", "147"],
            ["147", "148"],
            ["148", "149"],
            ["149", "150"],
            ["90", "151"],
            ["151", "152"],
            ["152", "153"],
            ["153", "154"],
            ["154", "155"],
            ["155", "156"],
            ["156", "157"],
            ["157", "158"],
            ["158", "159"],
            ["159", "160"],
            ["160", "161"],
            ["161", "162"],
            ["162", "163"],
            ["163", "164"],
            ["164", "165"],
            ["155", "166"],
            ["166", "167"],
            ["167", "168"],
            ["168", "169"],
            ["169", "170"],
            ["160", "171"],
            ["171", "172"],
            ["172", "173"],
            ["173", "174"],
            ["174", "175"],
            ["100", "176"],
            ["176", "177"],
            ["177", "178"],
            ["178", "179"],
            ["179", "180"],
            ["180", "181"],
            ["181", "182"],
            ["182", "183"],
            ["183", "184"],
            ["184", "185"],
            ["185", "186"],
            ["186", "187"],
            ["187", "188"],
            ["188", "189"],
            ["189", "190"],
            ["180", "191"],
            ["191", "192"],
            ["192", "193"],
            ["193", "194"],
            ["194", "195"],
            ["185", "196"],
            ["196", "197"],
            ["197", "198"],
            ["198", "199"],
            ["199", "200"],
        ]

        for n in range(1, 200):
            if n % 5 != 0:
                node_name_list2.append(f"SA{n}")
                node_name_list2.append(f"SB{n}")
                node_name_list2.append(f"SC{n}")

                adjacency_list.append([f"{n}", f"SA{n}"])
                adjacency_list.append([f"SA{n}", f"SB{n}"])
                adjacency_list.append([f"SA{n}", f"SC{n}"])

        # Create and assign nodes to variables
        log.debug("Start creating nodes")
        for node in node_name_list2:
            globals()[f"{node}"] = NetworkNode.objects.create(name=node)
        log.debug("Done creating nodes")


        log.debug("Connect nodes")
        for connection in adjacency_list:
            globals()[f"{connection[0]}"].add_child(globals()[f"{connection[1]}"])

        # Compute descendants of a root node
        canal_root = NetworkNode.objects.get(name="0")
        start_time = time.time()
        log.debug("Descendants: %s" % str(len(canal_root.descendants())))
        execution_time = time.time() - start_time
        log.debug("Execution time in seconds: %s" % str(execution_time))

        # Compute descendants of a leaf node
        canal_leaf = NetworkNode.objects.get(name="200")
        start_time = time.time()
        log.debug("Ancestors: %s" % str(len(canal_leaf.ancestors())))
        execution_time = time.time() - start_time
        log.debug("Execution time in seconds: %s" % str(execution_time))

        # Count number of paths from start to end of graph
        # NOTE: Does not work with current method of returning only a single path
        # start_time = time.time()
        # log.debug(
        #     "Paths through graph: : %s"
        #     % str(
        #         len(
        #             canal_root.path_ids_list(
        #                 canal_leaf, max_depth=n + 1, max_paths=500000000
        #             )
        #         )
        #     )
        # )
        # execution_time = time.time() - start_time
        # log.debug("Execution time in seconds: %s" % str(execution_time))

        # Find distance from root to leaf
        log.debug("Distance: %s" % str(canal_root.distance(canal_leaf, max_depth=100)))
        self.assertEqual(canal_root.distance(canal_leaf, max_depth=100), 60)

        log.debug("Node count: %s" % str(NetworkNode.objects.count()))
        log.debug("Edge count: %s" % str(NetworkEdge.objects.count()))

    def test_03_deep_dag(self):
        """
        Create a deep graph and check that graph operations run in a
        reasonable amount of time (linear in size of graph, not
        exponential).
        """

        def run_test():
            # Using the graph generation algorithm below, the number of potential
            # paths from node 0 doubles for each increase in n.
            # number_of_paths = 2^(n-1)  WRONG!!!
            # When n=22, there are on the order of 1 million paths through the graph
            # from node 0, so results for intermediate nodes need to be cached

            log = logging.getLogger("test_03")

            n = 22  # Keep it an even number


            log.debug("Start creating nodes")
            for i in range(2 * n):
                NetworkNode(pk=i, name=str(i)).save()
            log.debug("Done creating nodes")

            # Create edges
            log.debug("Connect nodes")
            for i in range(0, 2 * n - 2, 2):
                p1 = NetworkNode.objects.get(pk=i)
                p2 = NetworkNode.objects.get(pk=i + 1)
                p3 = NetworkNode.objects.get(pk=i + 2)
                p4 = NetworkNode.objects.get(pk=i + 3)

                p1.add_child(p3)
                p1.add_child(p4)
                p2.add_child(p3)
                p2.add_child(p4)

            # Compute descendants of a root node
            root_node = NetworkNode.objects.get(pk=0)
            start_time = time.time()
            log.debug("Descendants: %s" % str(len(root_node.ancestors())))
            execution_time = time.time() - start_time
            log.debug("Execution time in seconds: %s" % str(execution_time))

            # Compute ancestors of a leaf node
            leaf_node = NetworkNode.objects.get(pk=2 * n - 1)
            start_time = time.time()
            log.debug("Ancestors: %s" % str(len(leaf_node.ancestors())))
            execution_time = time.time() - start_time
            log.debug("Execution time in seconds: %s" % str(execution_time))

            first = NetworkNode.objects.get(name="0")
            last = NetworkNode.objects.get(pk=2 * n - 1)

            # # Count number of paths from start to end of graph
            # # NOTE: Does not work with current method of returning only a single path
            # start_time = time.time()
            # log.debug(
            #     "Paths through graph: %s"
            #     % str(
            #         len(first.path_ids_list(last, max_depth=n + 1, max_paths=500000000))
            #     )
            # )
            # execution_time = time.time() - start_time
            # log.debug("Execution time in seconds: %s" % str(execution_time))

            log.debug("Distance")
            self.assertEqual(first.distance(last, max_depth=n), n - 1)

            log.debug("Node count: %s" % str(NetworkNode.objects.count()))
            log.debug("Edge count: %s" % str(NetworkEdge.objects.count()))

            # Connect the first-created node to the last-created node
            NetworkNode.objects.get(pk=0).add_child(
                NetworkNode.objects.get(pk=2 * n - 1)
            )

            middle = NetworkNode.objects.get(pk=n - 1)
            log.debug("Distance")
            self.assertEqual(first.distance(middle, max_depth=n), n / 2 - 1)

        # Run the test, raising an error if the code times out
        p = multiprocessing.Process(target=run_test)
        p.start()
        p.join(20)  # Seconds allowed to live
        if p.is_alive():
            p.terminate()
            p.join()
            raise RuntimeError("Graph operations take too long!")
