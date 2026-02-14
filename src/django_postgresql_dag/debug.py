"""On-demand SQL query logging for DAG traversal queries.

Provides a context manager (and decorator) to capture the generated CTE SQL
from DAG operations like ``ancestors()``, ``descendants()``, ``path()``, etc.

Usage::

    from django_postgresql_dag.debug import log_queries

    with log_queries() as log:
        descendants = node.descendants()
        path = node.path(other_node)

    for q in log.queries:
        print(q["query_class"])  # e.g. "DescendantQuery"
        print(q["sql"])          # Full CTE SQL
        print(q["params"])       # Parameter dict
"""

import functools
from contextvars import ContextVar

_dag_query_collector: ContextVar[list | None] = ContextVar("_dag_query_collector", default=None)


class DAGQueryLog:
    """Result object holding captured DAG queries and optionally executed SQL."""

    def __init__(self):
        self.queries: list[dict] = []
        self.executed: list[dict] = []


class log_queries:
    """Context manager and decorator that captures DAG query SQL.

    Args:
        capture_executed: If True, also capture actual executed queries via
            Django's ``CaptureQueriesContext``, populating ``log.executed``.
        print_queries: If True, print captured queries on context exit.

    As a context manager::

        with log_queries() as log:
            node.descendants()
        print(log.queries)

    As a decorator::

        @log_queries(print_queries=True)
        def debug_my_operation():
            node.descendants()
    """

    def __init__(self, capture_executed=False, print_queries=False):
        self.capture_executed = capture_executed
        self.print_queries = print_queries
        self._log = DAGQueryLog()
        self._token = None
        self._capture_context = None

    @property
    def queries(self):
        return self._log.queries

    @property
    def executed(self):
        return self._log.executed

    def __enter__(self):
        collector = []
        self._token = _dag_query_collector.set(collector)

        if self.capture_executed:
            from django.db import connection
            from django.test.utils import CaptureQueriesContext

            self._capture_context = CaptureQueriesContext(connection)
            self._capture_context.__enter__()

        return self._log

    def __exit__(self, exc_type, exc_val, exc_tb):
        collector = _dag_query_collector.get()
        if collector is not None:
            self._log.queries = list(collector)

        _dag_query_collector.reset(self._token)

        if self._capture_context is not None:
            self._capture_context.__exit__(exc_type, exc_val, exc_tb)
            self._log.executed = [
                {"sql": q["sql"], "time": q.get("time", "")} for q in self._capture_context.captured_queries
            ]

        if self.print_queries:
            self._print_output()

        return False

    def _print_output(self):
        if self._log.queries:
            print(f"\n--- DAG Queries ({len(self._log.queries)}) ---")
            for i, q in enumerate(self._log.queries, 1):
                print(f"\n[{i}] {q['query_class']}")
                print(q["sql"])
                if q["params"]:
                    print(f"  params: {q['params']}")

        if self._log.executed:
            print(f"\n--- Executed Queries ({len(self._log.executed)}) ---")
            for i, e in enumerate(self._log.executed, 1):
                print(f"\n[{i}] {e['time']}s: {e['sql'][:200]}")

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper
