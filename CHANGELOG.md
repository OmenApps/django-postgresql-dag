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
  `query.truncated` flag and log a warning when a walk hits `max_depth` and drops a reachable
  node. Before, a graph deeper than `max_depth` was cut silently. Detection is exact, so a walk
  that returns the whole (sub)graph never false-warns. The returned pk set and the default
  `max_depth` (`20`) are unchanged. Gate the warning with
  `DJANGO_POSTGRESQL_DAG_WARN_ON_TRUNCATION` (default `True`).

### Infrastructure

- **Discriminator-column scoping (`edge_filter=`)**: traversal methods now accept an
  `edge_filter={field: value}` mapping that limits the walk to edges whose column equals the
  value. This scopes on non-ForeignKey columns that `limiting_edges_set_fk` cannot - such as an
  `edge_type` discriminator - so one edge table holding several edge kinds can be traversed one
  kind at a time. Field names are validated and values are bound parameters; unknown fields raise
  `FieldDoesNotExist`. Works on ancestor/descendant/connected-graph and path queries; graph-wide
  and LCA queries ignore it.
- **Consistent connection routing (`using=`)**: traversal methods now accept a `using=<alias>`
  keyword that pins both the pk list and the row hydration to the same database connection.
  Before, they could split across a primary/replica pair, so a write-then-traverse could drop
  rows a lagging replica had not caught up on. Threaded through every pk-list node method -
  ancestor/descendant/connected-graph, `path`/`all_paths`/`weighted_path`/`lowest_common_ancestors`,
  the `*_raw` variants - and `ordered_queryset_from_pks()`. Default (`None`) keeps the old
  behaviour.
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
