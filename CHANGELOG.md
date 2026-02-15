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

### Infrastructure

- Extended `BaseQuery` to support graph-wide queries (no instance required) via `node_model`/`edge_model` parameters.
- Added `WeightFieldDoesNotExistException` to `exceptions.py`.
- Added `validate_weight_field()` and `WeightedPathResult` namedtuple to `utils.py`.
- Added 10 new query builder classes to `query_builders.py`.

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
