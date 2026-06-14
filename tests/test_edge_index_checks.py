"""Tests for the info-level system check that flags edge models missing the
performance-improving composite indexes (Feature 1.1 DX follow-up)."""

from types import SimpleNamespace

from django.core.checks import Info
from django.test import SimpleTestCase

from django_postgresql_dag.checks import (
    DAG_EDGE_INDEX_FIELDS_ATTR,
    _check_models,
    _missing_index_field_tuples,
    check_dag_edge_indexes,
)
from tests.testapp.models import NetworkEdge

REQUIRED = (("parent", "child"), ("child", "parent"))


def _fake_index(*fields):
    return SimpleNamespace(fields=list(fields))


def _fake_edge(label, index_field_lists, *, is_edge=True, abstract=False, proxy=False, parents=()):
    meta = SimpleNamespace(
        label=label,
        abstract=abstract,
        proxy=proxy,
        indexes=[_fake_index(*fields) for fields in index_field_lists],
        get_parent_list=lambda: list(parents),
    )
    model = SimpleNamespace(_meta=meta)
    if is_edge:
        setattr(model, DAG_EDGE_INDEX_FIELDS_ATTR, REQUIRED)
    return model


class MissingIndexFieldTuplesTestCase(SimpleTestCase):
    def test_both_present_returns_empty(self):
        model = _fake_edge("app.E", [["parent", "child"], ["child", "parent"]])
        self.assertEqual(_missing_index_field_tuples(model), [])

    def test_only_parent_child_present_reports_the_other(self):
        model = _fake_edge("app.E", [["parent", "child"]])
        self.assertEqual(_missing_index_field_tuples(model), [("child", "parent")])

    def test_neither_present_reports_both(self):
        model = _fake_edge("app.E", [])
        self.assertEqual(_missing_index_field_tuples(model), [("parent", "child"), ("child", "parent")])

    def test_superset_prefix_index_counts_as_coverage(self):
        # A (parent, child, x) index serves (parent, child) as a left-prefix.
        model = _fake_edge("app.E", [["parent", "child", "x"], ["child", "parent", "y"]])
        self.assertEqual(_missing_index_field_tuples(model), [])

    def test_non_edge_model_returns_empty(self):
        model = _fake_edge("app.Plain", [], is_edge=False)
        self.assertEqual(_missing_index_field_tuples(model), [])


class CheckModelsTestCase(SimpleTestCase):
    def test_uncovered_edge_yields_one_info_message(self):
        model = _fake_edge("app.E", [])
        messages = _check_models([model])
        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertIsInstance(msg, Info)
        self.assertEqual(msg.id, "django_postgresql_dag.I001")
        self.assertIn("(parent, child)", msg.msg)
        self.assertIn("(child, parent)", msg.msg)
        self.assertTrue(msg.hint)

    def test_covered_edge_yields_no_message(self):
        model = _fake_edge("app.E", [["parent", "child"], ["child", "parent"]])
        self.assertEqual(_check_models([model]), [])

    def test_non_edge_model_skipped(self):
        self.assertEqual(_check_models([_fake_edge("app.Plain", [], is_edge=False)]), [])

    def test_abstract_and_proxy_skipped(self):
        self.assertEqual(_check_models([_fake_edge("app.A", [], abstract=True)]), [])
        self.assertEqual(_check_models([_fake_edge("app.P", [], proxy=True)]), [])

    def test_mti_child_skipped_when_parent_is_edge(self):
        parent = _fake_edge("app.Base", [["parent", "child"], ["child", "parent"]])
        child = _fake_edge("app.Child", [], parents=[parent])
        self.assertEqual(_check_models([child]), [])


class RealProjectIntegrationTestCase(SimpleTestCase):
    def test_networkedge_is_not_flagged(self):
        # NetworkEdge inherits the composites via its subclassing Meta, so it must
        # not be flagged - guards against false positives on a correctly-configured model.
        self.assertEqual(_missing_index_field_tuples(NetworkEdge), [])

    def test_registered_check_reports_no_edge_index_issues_for_project(self):
        messages = check_dag_edge_indexes(app_configs=None)
        i001 = [m for m in messages if m.id == "django_postgresql_dag.I001"]
        self.assertEqual(i001, [])
