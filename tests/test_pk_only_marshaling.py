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
