from django.test import TestCase

from django_postgresql_dag.debug import DAGQueryLog, _dag_query_collector, log_queries
from tests.helpers import TenNodeDAGFixtureMixin


class LogQueriesContextManagerTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Tests for the log_queries context manager."""

    def test_captures_descendant_query(self):
        with log_queries() as log:
            list(self.root.descendants())

        self.assertEqual(len(log.queries), 1)
        self.assertEqual(log.queries[0]["query_class"], "DescendantQuery")
        self.assertIn("WITH RECURSIVE", log.queries[0]["sql"])
        self.assertIn("pk", log.queries[0]["params"])

    def test_captures_ancestor_query(self):
        with log_queries() as log:
            list(self.c1.ancestors())

        self.assertEqual(len(log.queries), 1)
        self.assertEqual(log.queries[0]["query_class"], "AncestorQuery")
        self.assertIn("WITH RECURSIVE", log.queries[0]["sql"])

    def test_captures_connected_graph_query(self):
        with log_queries() as log:
            list(self.root.connected_graph())

        self.assertEqual(len(log.queries), 1)
        self.assertEqual(log.queries[0]["query_class"], "ConnectedGraphQuery")
        self.assertIn("WITH RECURSIVE", log.queries[0]["sql"])

    def test_captures_path_query(self):
        with log_queries() as log:
            list(self.root.path(self.c1))

        self.assertGreaterEqual(len(log.queries), 1)
        query_classes = [q["query_class"] for q in log.queries]
        self.assertTrue(
            "DownwardPathQuery" in query_classes or "UpwardPathQuery" in query_classes,
        )

    def test_captures_node_depth(self):
        with log_queries() as log:
            self.c1.node_depth()

        depth_queries = [q for q in log.queries if q["query_class"] == "node_depth"]
        self.assertEqual(len(depth_queries), 1)
        self.assertIn("WITH RECURSIVE", depth_queries[0]["sql"])
        self.assertEqual(depth_queries[0]["params"]["pk"], self.c1.pk)

    def test_captures_multiple_queries(self):
        with log_queries() as log:
            list(self.root.descendants())
            list(self.c1.ancestors())

        self.assertEqual(len(log.queries), 2)
        self.assertEqual(log.queries[0]["query_class"], "DescendantQuery")
        self.assertEqual(log.queries[1]["query_class"], "AncestorQuery")

    def test_no_capture_outside_context(self):
        list(self.root.descendants())
        with log_queries() as log:
            pass

        self.assertEqual(len(log.queries), 0)

    def test_contextvar_reset_after_exit(self):
        with log_queries():
            self.assertIsNotNone(_dag_query_collector.get(None))

        self.assertIsNone(_dag_query_collector.get(None))

    def test_empty_block_produces_empty_results(self):
        with log_queries() as log:
            pass

        self.assertEqual(log.queries, [])
        self.assertEqual(log.executed, [])

    def test_result_is_dag_query_log(self):
        with log_queries() as log:
            pass

        self.assertIsInstance(log, DAGQueryLog)

    def test_capture_executed(self):
        with log_queries(capture_executed=True) as log:
            list(self.root.descendants())

        self.assertGreaterEqual(len(log.executed), 1)
        self.assertTrue(any("sql" in e for e in log.executed))
        self.assertTrue(any("time" in e for e in log.executed))

    def test_print_queries(self):
        """Smoke test that print_queries=True doesn't raise."""
        with log_queries(print_queries=True) as log:
            list(self.root.descendants())

        self.assertGreaterEqual(len(log.queries), 1)

    def test_print_queries_with_capture_executed(self):
        """Exercises the executed-queries print branch in _print_output."""
        with log_queries(print_queries=True, capture_executed=True) as log:
            list(self.root.descendants())

        self.assertGreaterEqual(len(log.queries), 1)
        self.assertGreaterEqual(len(log.executed), 1)

    def test_queries_contain_params(self):
        with log_queries() as log:
            list(self.root.descendants())

        params = log.queries[0]["params"]
        self.assertIn("pk", params)
        self.assertIn("max_depth", params)


class LogQueriesDecoratorTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Tests for the log_queries decorator form."""

    def test_decorator_form(self):
        @log_queries(print_queries=False)
        def my_operation():
            list(self.root.descendants())

        # The decorator doesn't expose the log object, but it should not raise
        my_operation()

    def test_decorator_returns_value(self):
        @log_queries()
        def my_operation():
            return list(self.root.descendants())

        result = my_operation()
        self.assertGreater(len(result), 0)

    def test_decorator_instance_properties(self):
        """Access queries/executed properties on the log_queries instance itself."""
        lq = log_queries()

        @lq
        def my_operation():
            list(self.root.descendants())

        my_operation()
        self.assertGreaterEqual(len(lq.queries), 1)
        self.assertEqual(lq.executed, [])


class LogQueriesIsolationTestCase(TenNodeDAGFixtureMixin, TestCase):
    """Tests that log_queries blocks are properly isolated."""

    def test_separate_blocks_dont_leak(self):
        with log_queries() as log1:
            list(self.root.descendants())

        with log_queries() as log2:
            list(self.c1.ancestors())

        self.assertEqual(len(log1.queries), 1)
        self.assertEqual(log1.queries[0]["query_class"], "DescendantQuery")
        self.assertEqual(len(log2.queries), 1)
        self.assertEqual(log2.queries[0]["query_class"], "AncestorQuery")
