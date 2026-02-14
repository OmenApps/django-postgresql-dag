import time

from django.test import TestCase

from tests.helpers import (
    CheckLongTestCaseMixin,
    DAGFixtureMixin,
    TenNodeDAGFixtureMixin,
    log,
)
from tests.testapp.models import NetworkEdge, NetworkNode


class PartialDAGTreeTestCase(TestCase):
    """Tests descendants_tree with a minimal partial DAG (root -> a1 -> b1 only)."""

    def setUp(self):
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.b1 = NetworkNode.objects.create(name="b1")

        self.root.add_child(self.a1)
        self.b1.add_parent(self.a1)

    def test_descendants_tree_initial(self):
        tree = self.root.descendants_tree()
        self.assertIn(self.a1, tree)
        self.assertEqual(len(tree), 1)
        self.assertIn(self.b1, tree[self.a1])
        self.assertEqual(tree[self.a1][self.b1], {})


class TraversalTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Core traversal tests using the full 10-node DAG."""

    def test_descendants_excludes_self(self):
        root_descendants = self.root.descendants()
        self.assertNotIn(self.root, root_descendants)
        self.assertTrue(all(elem in root_descendants for elem in [self.a1, self.b1]))

    def test_descendants_full_graph(self):
        root_descendants = self.root.descendants()
        self.assertNotIn(self.root, root_descendants)
        self.assertTrue(
            all(elem in root_descendants for elem in [self.a1, self.a2, self.a3, self.b1, self.b3, self.b4, self.c1])
        )

    def test_ancestors_excludes_self(self):
        c1_ancestors = self.c1.ancestors()
        self.assertNotIn(self.c1, c1_ancestors)
        self.assertTrue(all(elem in c1_ancestors for elem in [self.root, self.a3, self.b3, self.b4]))

    def test_descendants_tree(self):
        tree_from_root = self.root.descendants_tree()
        self.assertIn(self.a1, tree_from_root)
        self.assertIn(self.a2, tree_from_root)
        self.assertIn(self.a3, tree_from_root)
        self.assertIn(self.b2, tree_from_root[self.a1])
        self.assertIn(self.b1, tree_from_root[self.a1])
        self.assertIn(self.b2, tree_from_root[self.a2])
        self.assertIn(self.b3, tree_from_root[self.a3])
        self.assertIn(self.b4, tree_from_root[self.a3])
        self.assertIn(self.c2, tree_from_root[self.a3][self.b3])
        self.assertIn(self.c1, tree_from_root[self.a3][self.b3])
        self.assertIn(self.c1, tree_from_root[self.a3][self.b4])

        self.assertEqual(len(tree_from_root), 3)
        self.assertEqual(len(tree_from_root[self.a3]), 2)
        self.assertEqual(len(tree_from_root[self.a3][self.b4]), 1)

    def test_ancestors_tree(self):
        tree_from_leaf = self.c1.ancestors_tree()
        self.assertIn(self.b3, tree_from_leaf)
        self.assertIn(self.a3, tree_from_leaf[self.b3])
        self.assertIn(self.b4, tree_from_leaf)
        self.assertIn(self.a3, tree_from_leaf[self.b4])
        self.assertIn(self.root, tree_from_leaf[self.b4][self.a3])

        self.assertEqual(len(tree_from_leaf), 2)
        self.assertEqual(len(tree_from_leaf[self.b3]), 1)
        self.assertEqual(len(tree_from_leaf[self.b4]), 1)
        self.assertEqual(len(tree_from_leaf[self.b4][self.a3]), 1)

    def test_ancestors_and_self_ordering(self):
        self.assertEqual(self.a1.ancestors_and_self()[0], self.root)
        self.assertEqual(self.a1.ancestors_and_self()[1], self.a1)
        self.assertEqual(self.a1.self_and_ancestors()[0], self.a1)
        self.assertEqual(self.a1.self_and_ancestors()[1], self.root)

    def test_descendants_and_self_ordering(self):
        self.assertEqual(self.b4.descendants_and_self()[0], self.c1)
        self.assertEqual(self.b4.descendants_and_self()[1], self.b4)
        self.assertEqual(self.b4.self_and_descendants()[0], self.b4)
        self.assertEqual(self.b4.self_and_descendants()[1], self.c1)

    def test_clan(self):
        self.assertTrue(all(elem in self.a1.clan() for elem in [self.root, self.a1, self.b1, self.b2]))
        self.assertEqual(self.a1.clan()[0], self.root)
        self.assertEqual(self.a1.clan()[3], self.b2)


class NodeCountMethodsTestCase(DAGFixtureMixin, TestCase):
    def test_ancestors_count(self):
        self.assertEqual(self.root.ancestors_count(), 0)
        self.assertEqual(self.a1.ancestors_count(), 1)
        self.assertEqual(self.b1.ancestors_count(), 3)  # root, a1, a2

    def test_descendants_count(self):
        self.assertEqual(self.root.descendants_count(), 5)  # a1, a2, a3, b1, b2
        self.assertEqual(self.b1.descendants_count(), 0)

    def test_clan_count(self):
        # a1 ancestors: root. a1 descendants: b1. clan = root + a1 + b1 = 3
        self.assertEqual(self.a1.clan_count(), 3)

    def test_siblings_count(self):
        self.assertEqual(self.a1.siblings_count(), 2)  # a2, a3
        self.assertEqual(self.root.siblings_count(), 0)

    def test_partners_count(self):
        # a1 and a2 share child b1
        self.assertEqual(self.a1.partners_count(), 1)  # a2
        self.assertEqual(self.a3.partners_count(), 0)


class SiblingsPartnersTestCase(DAGFixtureMixin, TestCase):
    def test_siblings(self):
        siblings = self.a1.siblings()
        self.assertIn(self.a2, siblings)
        self.assertIn(self.a3, siblings)
        self.assertNotIn(self.a1, siblings)

    def test_siblings_with_self(self):
        siblings = self.a1.siblings_with_self()
        self.assertIn(self.a1, siblings)
        self.assertIn(self.a2, siblings)
        self.assertIn(self.a3, siblings)

    def test_partners(self):
        partners = self.a1.partners()
        self.assertIn(self.a2, partners)
        self.assertNotIn(self.a1, partners)

    def test_partners_with_self(self):
        partners = self.a1.partners_with_self()
        self.assertIn(self.a1, partners)
        self.assertIn(self.a2, partners)


class IrrigationCanalTestCase(CheckLongTestCaseMixin, TestCase):
    """Simulate a basic irrigation canal network for performance testing."""

    def test_irrigation_canal_network(self):
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

        # Create nodes as a lookup dict
        nodes = {}
        log.debug("Start creating nodes")
        for node in node_name_list2:
            nodes[f"{node}"] = NetworkNode.objects.create(name=node)
        log.debug("Done creating nodes")

        log.debug("Connect nodes")
        for connection in adjacency_list:
            nodes[f"{connection[0]}"].add_child(nodes[f"{connection[1]}"])

        # Compute descendants of a root node
        canal_root = NetworkNode.objects.get(name="0")
        start_time = time.time()
        log.debug(f"Descendants: {len(canal_root.descendants())}")
        execution_time = time.time() - start_time
        log.debug(f"Execution time in seconds: {execution_time}")

        # Compute descendants of a leaf node
        canal_leaf = NetworkNode.objects.get(name="200")
        start_time = time.time()
        log.debug(f"Ancestors: {len(canal_leaf.ancestors(max_depth=200))}")
        execution_time = time.time() - start_time
        log.debug(f"Execution time in seconds: {execution_time}")

        # Check if path exists from canal_root to canal_leaf
        log.debug(f"Path Exists: {canal_root.path_exists(canal_leaf, max_depth=200)}")
        self.assertTrue(canal_root.path_exists(canal_leaf, max_depth=200), True)

        # Find distance from root to leaf
        log.debug(f"Distance: {canal_root.distance(canal_leaf, max_depth=200)}")
        self.assertEqual(canal_root.distance(canal_leaf, max_depth=200), 60)

        log.debug(f"Node count: {NetworkNode.objects.count()}")
        log.debug(f"Edge count: {NetworkEdge.objects.count()}")


class DeepDagTestCase(CheckLongTestCaseMixin, TestCase):
    def setUp(self):
        # Using the graph generation algorithm below, the number of potential
        # paths from node 0 doubles for each increase in n.
        # When n=22, there are many paths through the graph from node 0,
        # so results for intermediate nodes need to be cached

        self.n = 22  # Keep it an even number

        log.debug("Start creating nodes")
        for i in range(2 * self.n):
            NetworkNode(pk=i, name=str(i)).save()
        log.debug("Done creating nodes")

        # Create edges
        log.debug("Connect nodes")
        for i in range(0, 2 * self.n - 2, 2):
            p1 = NetworkNode.objects.get(pk=i)
            p2 = NetworkNode.objects.get(pk=i + 1)
            p3 = NetworkNode.objects.get(pk=i + 2)
            p4 = NetworkNode.objects.get(pk=i + 3)

            p1.add_child(p3)
            p1.add_child(p4)
            p2.add_child(p3)
            p2.add_child(p4)

    def test_deep_dag(self):
        """Create a deep graph and check that graph operations run in a reasonable amount of time.

        Operations should be linear in size of graph, not exponential.
        """

        def run_test():
            # Compute descendants of a root node
            root_node = NetworkNode.objects.get(pk=0)
            start_time = time.time()
            log.debug(f"Descendants: {len(root_node.ancestors())}")
            execution_time = time.time() - start_time
            log.debug(f"Execution time in seconds: {execution_time}")

            # Compute ancestors of a leaf node
            leaf_node = NetworkNode.objects.get(pk=2 * self.n - 1)
            start_time = time.time()
            log.debug(f"Ancestors: {len(leaf_node.ancestors())}")
            execution_time = time.time() - start_time
            log.debug(f"Execution time in seconds: {execution_time}")

            first = NetworkNode.objects.get(name="0")
            last = NetworkNode.objects.get(name=str(2 * self.n - 1))

            path_exists = first.path_exists(last, max_depth=self.n)
            log.debug(f"Path exists: {path_exists}")
            self.assertTrue(path_exists, True)
            self.assertEqual(first.distance(last, max_depth=self.n), self.n - 1)

            log.debug(f"Node count: {NetworkNode.objects.count()}")
            log.debug(f"Edge count: {NetworkEdge.objects.count()}")

            # Connect the first-created node to the last-created node
            NetworkNode.objects.get(pk=0).add_child(NetworkNode.objects.get(pk=2 * self.n - 1))

            middle = NetworkNode.objects.get(pk=self.n - 1)
            distance = first.distance(middle, max_depth=self.n)
            log.debug(f"Distance: {distance}")
            self.assertEqual(distance, self.n / 2 - 1)

        # Run the test, raising an error if the code times out
        run_test()
