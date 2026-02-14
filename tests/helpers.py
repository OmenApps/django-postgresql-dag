import logging
import time

from tests.testapp.models import EdgeSet, NetworkEdge, NetworkNode

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("django_postgresql_log.testapp")

node_name_list = ["root", "a1", "a2", "a3", "b1", "b2", "b3", "b4", "c1", "c2"]


class SlowTestException(Exception):
    pass


class CheckLongTestCaseMixin:
    def _callTestMethod(self, method):
        start = time.time()

        result = super()._callTestMethod(method)

        limit_seconds = 30
        time_taken = time.time() - start
        if time_taken > limit_seconds:
            raise SlowTestException(f"This test took {time_taken:.2f}s, more than the limit of {limit_seconds}s.")

        return result


class DAGFixtureMixin:
    """Shared fixture building a small DAG:

    root -> a1 -> b1
         -> a2 -> b1
         -> a3 -> b2
    island (disconnected)
    """

    def setUp(self):
        self.root = NetworkNode.objects.create(name="root")
        self.a1 = NetworkNode.objects.create(name="a1")
        self.a2 = NetworkNode.objects.create(name="a2")
        self.a3 = NetworkNode.objects.create(name="a3")
        self.b1 = NetworkNode.objects.create(name="b1")
        self.b2 = NetworkNode.objects.create(name="b2")
        self.island = NetworkNode.objects.create(name="island")

        self.root.add_child(self.a1)
        self.root.add_child(self.a2)
        self.root.add_child(self.a3)
        self.a1.add_child(self.b1)
        self.a2.add_child(self.b1)
        self.a3.add_child(self.b2)


class TenNodeDAGFixtureMixin:
    """Shared fixture building a 10-node DAG:

    root -> a1 -> b1
         -> a1 -> b2
         -> a2 -> b2
         -> a3 -> b3 -> c1
                     -> c2
              -> b4 -> c1
    """

    def setUp(self):
        for name in node_name_list:
            NetworkNode.objects.create(name=name)

        self.root = NetworkNode.objects.get(name="root")
        self.a1 = NetworkNode.objects.get(name="a1")
        self.a2 = NetworkNode.objects.get(name="a2")
        self.a3 = NetworkNode.objects.get(name="a3")
        self.b1 = NetworkNode.objects.get(name="b1")
        self.b2 = NetworkNode.objects.get(name="b2")
        self.b3 = NetworkNode.objects.get(name="b3")
        self.b4 = NetworkNode.objects.get(name="b4")
        self.c1 = NetworkNode.objects.get(name="c1")
        self.c2 = NetworkNode.objects.get(name="c2")

        self.root.add_child(self.a1)
        self.a1.add_child(self.b1)
        self.root.add_child(self.a2)
        self.a3.add_parent(self.root)
        self.a3.add_child(self.b3)
        self.a3.add_child(self.b4)
        self.b3.add_child(self.c1)
        self.a1.add_child(self.b2)
        self.a2.add_child(self.b2)
        self.b3.add_child(self.c2)
        self.b4.add_child(self.c1)


class PathFilterFixtureMixin:
    """Fixture for path query filter tests.

    Creates a DAG with an alternate path so disallow/allow filters
    can block one path while leaving another viable:

        root -> mid1 -> leaf
             -> mid2 -> leaf
    """

    def setUp(self):
        self.edge_set = EdgeSet.objects.create(name="path_set")
        self.root = NetworkNode.objects.create(name="root")
        self.mid1 = NetworkNode.objects.create(name="mid1")
        self.mid2 = NetworkNode.objects.create(name="mid2")
        self.leaf = NetworkNode.objects.create(name="leaf")

        self.root.add_child(self.mid1)
        self.root.add_child(self.mid2)
        self.mid1.add_child(self.leaf)
        self.mid2.add_child(self.leaf)

        # Assign all edges to edge_set
        NetworkEdge.objects.all().update(edge_set=self.edge_set)
