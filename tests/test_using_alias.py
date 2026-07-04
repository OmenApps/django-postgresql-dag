"""Tests that the ``using=`` alias pins both halves of a traversal to one connection.

On a primary/replica deployment the pk list runs on the primary cursor while the row hydration
routes through the read router. Passing ``using=<alias>`` forces both onto the same connection so a
write-then-traverse stays read-consistent. The test suite runs a single database, so these tests
prove the plumbing (the alias reaches the cursor and the hydration queryset) rather than replica lag.
"""

from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from django_postgresql_dag.query_builders import DescendantQuery
from tests.testapp.models import NetworkNode


class UsingAliasTestCase(TestCase):
    def setUp(self):
        self.root = NetworkNode.objects.create(name="root")
        self.a = NetworkNode.objects.create(name="a")
        self.b = NetworkNode.objects.create(name="b")
        self.root.add_child(self.a)
        self.a.add_child(self.b)

    def test_query_stores_using_alias(self):
        """The alias is captured on the query object."""
        query = DescendantQuery(instance=self.root, using="default")
        self.assertEqual(query.using, "default")

    def test_pk_list_runs_on_named_alias(self):
        """The recursive CTE executes on the named connection when ``using`` is set."""
        with CaptureQueriesContext(connections["default"]) as captured:
            DescendantQuery(instance=self.root, using="default").pk_list()
        self.assertTrue(any("RECURSIVE traverse" in query["sql"] for query in captured.captured_queries))

    def test_descendants_hydration_pinned_to_alias(self):
        """The node method's hydration queryset is bound to the requested alias."""
        queryset = self.root.descendants(using="default")
        self.assertEqual(queryset.db, "default")

    def test_descendants_default_hydration_uses_router(self):
        """Without ``using`` the hydration queryset falls back to the router's chosen alias."""
        queryset = self.root.descendants()
        # Single-DB test setup: the router resolves reads to ``default``.
        self.assertEqual(queryset.db, "default")

    def test_write_then_traverse_sees_new_edge(self):
        """A node connected in the same transaction is visible to a pinned descendant walk."""
        c = NetworkNode.objects.create(name="c")
        self.b.add_child(c)
        descendants = self.root.descendants(using="default")
        self.assertIn(c, descendants)

    def test_using_alias_returns_same_pks_as_default(self):
        """Pinning the connection does not change the result set."""
        default_pks = set(self.root.descendants().values_list("pk", flat=True))
        pinned_pks = set(self.root.descendants(using="default").values_list("pk", flat=True))
        self.assertEqual(default_pks, pinned_pks)
