# Changelog

## [Unreleased]

### New features

- **Topological sort**: `NodeManager.topological_sort()` returns all nodes in topological order (parents before children). Per-node: `node.topological_descendants()`.
- **Depth annotation**: `node.ancestors_with_depth()` and `node.descendants_with_depth()` return `(node, depth)` tuples exposing CTE-computed depth.
- **All-paths enumeration**: `node.all_paths(target)` and `node.all_paths_as_pk_lists(target)` return every path between two nodes, not just the shortest. Supports `max_results` limit.
- **Lowest Common Ancestor (LCA)**: `node.lowest_common_ancestors(other)` returns a QuerySet of the deepest shared ancestors. Handles multiple LCAs in diamond patterns.
- **Weighted shortest path**: `node.weighted_path(target, weight_field="weight")` finds the minimum-weight path using a CTE that sums edge weights. Also: `weighted_path_raw()`, `weighted_distance()`.
- **Critical path**: `NodeManager.critical_path(weight_field=None)` finds the longest weighted path through the entire DAG. Without a weight field, counts hops.
- **Transitive reduction**: `NodeManager.transitive_reduction()` and `EdgeManager.redundant_edges()` identify and optionally delete redundant edges (A->C is redundant if A->B->...->C exists).
- **Graph hashing**: `graph_hash()`, `subgraph_hashes()`, and `graphs_are_isomorphic()` in `transformations.py` use NetworkX Weisfeiler-Lehman hashing. Node-level convenience methods: `node.graph_hash()`, `node.subgraph_hashes()`.
- **Loud truncation signal**: ancestor, descendant, and connected-graph walks now set a
  `query.truncated` flag and log a warning when a walk hits `max_depth` and drops rows beyond
  it. Before, a graph deeper than `max_depth` was cut silently. The returned pk set and the
  default `max_depth` (`20`) are unchanged. Raise the `django_postgresql_dag` logger above
  `WARNING` to silence the notice.

### Infrastructure

- Extended `BaseQuery` to support graph-wide queries (no instance required) via `node_model`/`edge_model` parameters.
- Added `WeightFieldDoesNotExistException` to `exceptions.py`.
- Added `validate_weight_field()` and `WeightedPathResult` namedtuple to `utils.py`.
- Added 10 new query builder classes to `query_builders.py`.

### Performance

- **Edge indexes**: `edge_factory` now adds composite indexes `(parent, child)` and
  `(child, parent)` to the edge table so the planner can use them for the
  ancestor/descendant CTE self-joins. **Action required on upgrade:** run `makemigrations`
  for each concrete Edge model. **If your Edge model defines its own `Meta`, it must now
  subclass the factory `Meta` (`class Meta(EdgeBase.Meta)`), or the indexes are silently
  dropped - no error and no migration.** Verify with:
  `python -c "from myapp.models import MyEdge; assert {tuple(i.fields) for i in MyEdge._meta.indexes} >= {('parent','child'),('child','parent')}"`.
  The new indexes are additive over Django's single-column FK indexes (small extra write
  cost on `add_child`); see the Edge Reference for the `db_index=False` opt-in and the
  `AddIndexConcurrently` zero-downtime option. Warrants at least a minor version bump.
- **Edge index system check**: an info-level Django system check (`django_postgresql_dag.I001`)
  runs on `manage.py check` and `runserver` and flags any concrete edge model missing an index
  covering `(parent, child)` or `(child, parent)` - usually an Edge `Meta` that does not subclass
  the factory `Meta`. The message names the missing index(es) and how to add them. It is
  coverage-based (a model with its own equivalent indexes is not flagged) and informational only.
- **PK-only marshaling**: unfiltered traversals (`ancestors`, `descendants`, `clan`,
  `connected_graph`, `*_and_self`, `topological_descendants`) and the manager methods
  (`topological_sort`, `transitive_reduction`, `redundant_edges`) now read result PKs
  through a raw cursor (`BaseQuery.pk_list()`) instead of building a throwaway
  `RawQuerySet`, saving one full result-set instantiation per call. Query count, public
  APIs, and results are unchanged.

## [0.3.1] - 2021-09-15

### Potential breaking changes


### Other changes

- Fix implicit type cast issue encountered in connected graph searches. Works for `pkid` of types AutoField, BigAutoField, and UUIDField.
- Update version number.


## [0.3.0] - 2021-09-15

### Potential breaking changes


### Other changes

- Fix implicit array cast issue encountered in path searches. Works for `pkid` of types AutoField, BigAutoField, and UUIDField.
- Update version number.
