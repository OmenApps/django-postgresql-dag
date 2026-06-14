"""Tests for cursor-based PK extraction that skips model instantiation (Feature 2.4)."""

from django.test import TestCase

from django_postgresql_dag.debug import log_queries
from django_postgresql_dag.query_builders import AncestorQuery, DescendantQuery
from tests.helpers import TenNodeDAGFixtureMixin


class PkListTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_pk_list_matches_id_list_for_ancestors(self):
        self.assertEqual(AncestorQuery(instance=self.c1).pk_list(), AncestorQuery(instance=self.c1).id_list())

    def test_pk_list_matches_id_list_for_descendants(self):
        self.assertEqual(DescendantQuery(instance=self.root).pk_list(), DescendantQuery(instance=self.root).id_list())

    def test_pk_list_returns_plain_list_of_pks(self):
        result = DescendantQuery(instance=self.root).pk_list()
        self.assertIsInstance(result, list)
        # NetworkNode uses an integer PK, so the cursor returns ints here. pk_list()
        # itself is PK-type-agnostic (the library also supports UUID/Char PKs); this
        # int assertion is specific to the test app, not a pk_list() contract.
        self.assertTrue(all(isinstance(pk, int) for pk in result))

    def test_pk_list_records_exactly_one_collector_entry(self):
        with log_queries() as log:
            DescendantQuery(instance=self.root).pk_list()
        self.assertEqual(len(log.queries), 1)
        self.assertEqual(log.queries[0]["query_class"], "DescendantQuery")


class NodeMethodParityTestCase(TenNodeDAGFixtureMixin, TestCase):
    def test_ancestors_unchanged(self):
        # c1's ancestors must be exactly root, a3, b3, b4 (per the fixture).
        names = set(self.c1.ancestors().values_list("name", flat=True))
        self.assertEqual(names, {"root", "a3", "b3", "b4"})

    def test_descendants_unchanged(self):
        names = set(self.root.descendants().values_list("name", flat=True))
        self.assertEqual(names, {"a1", "a2", "a3", "b1", "b2", "b3", "b4", "c1", "c2"})

    def test_clan_includes_self_ancestors_descendants(self):
        names = set(self.b3.clan().values_list("name", flat=True))
        self.assertEqual(names, {"root", "a3", "b3", "c1", "c2"})

    def test_ancestors_and_self_order(self):
        result = list(self.c1.ancestors_and_self().values_list("name", flat=True))
        self.assertEqual(result[-1], "c1")  # self appended last

    def test_descendants_and_self_order(self):
        result = list(self.root.descendants_and_self().values_list("name", flat=True))
        self.assertEqual(result[-1], "root")  # self appended last

    def test_connected_graph_unchanged(self):
        names = set(self.root.connected_graph().values_list("name", flat=True))
        self.assertTrue({"a1", "c1", "c2"}.issubset(names))

    def test_clan_records_two_collector_entries(self):
        with log_queries() as log:
            list(self.b3.clan())
        # clan runs one ancestor CTE + one descendant CTE; the final pk__in requery
        # is a normal ORM query, not a DAG-collector entry.
        self.assertEqual(len(log.queries), 2)
        self.assertEqual({q["query_class"] for q in log.queries}, {"AncestorQuery", "DescendantQuery"})

    def test_descendants_runs_no_extra_db_queries(self):
        # One CTE (cursor) + one pk__in requery when the queryset is evaluated.
        with self.assertNumQueries(2):
            list(self.root.descendants())
