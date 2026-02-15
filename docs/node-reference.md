# Node API Reference

Complete reference for all methods available on Node model instances and the Node manager. For practical examples and usage patterns, see [Filtering Graph Traversals](filtering.md) and [Working with Paths and Algorithms](paths-and-algorithms.md).

## Manager Methods

These are called on `MyNode.objects`.

**roots(self, node=None)**
: Returns a QuerySet of all root nodes (nodes with no parents). If `node` is provided, returns only the roots reachable from that node.

**leaves(self, node=None)**
: Returns a QuerySet of all leaf nodes (nodes with no children). If `node` is provided, returns only the leaves reachable from that node.

**connected_components(self)**
: Returns a list of QuerySets, one per disconnected subgraph. Each QuerySet can be further filtered.

**graph_stats(self)**
: Returns a dict with aggregate metrics: `node_count`, `edge_count`, `root_count`, `leaf_count`, `island_count`, `max_depth`, `avg_depth`, `density`, `component_count`. Runs O(N) queries — suitable for analytics, not hot paths.

**topological_sort(self, max_depth=None)**
: Returns a QuerySet of all nodes in topological order (parents before children). Island nodes are included at the front.

**critical_path(self, weight_field=None, max_depth=None)**
: Returns a `(QuerySet, total_weight)` tuple for the longest weighted path from any root to any leaf. Without `weight_field`, uses hop count (each edge = 1).

**transitive_reduction(self, delete=False)**
: Identifies redundant edges (A→C is redundant if C is reachable from A via a path of length >= 2). Returns a QuerySet of redundant edges by default (dry run). With `delete=True`, deletes them and returns the count.

## Mutation Methods

**add_child(self, child, \*\*kwargs)**
: Creates an edge from this node to `child`. Extra keyword arguments are passed to the edge model constructor.

**remove_child(self, child, delete_node=False)**
: Removes the edge to `child`. If `child` is `None`, removes edges to all children. With `delete_node=True`, also deletes the child node(s).

**add_parent(self, parent, \*args, \*\*kwargs)**
: Creates an edge from `parent` to this node.

**remove_parent(self, parent, delete_node=False)**
: Removes the edge from `parent`. If `parent` is `None`, removes edges from all parents. With `delete_node=True`, also deletes the parent node(s).

## Traversal Methods

All traversal methods accept optional keyword arguments for [filtering](filtering.md): `max_depth`, `edge_type`, `disallowed_edges_queryset`, `allowed_edges_queryset`.

**ancestors(self, \*\*kwargs)**
: Returns a QuerySet of all nodes reachable by following edges toward roots.

**ancestors_count(self)**
: Returns the total number of ancestor nodes.

**self_and_ancestors(self, \*\*kwargs)**
: Returns a list starting with self, followed by ancestors.

**ancestors_and_self(self, \*\*kwargs)**
: Returns a QuerySet of ancestors with self appended.

**descendants(self, \*\*kwargs)**
: Returns a QuerySet of all nodes reachable by following edges toward leaves.

**descendants_count(self)**
: Returns the total number of descendant nodes.

**self_and_descendants(self, \*\*kwargs)**
: Returns a QuerySet starting with self, followed by descendants.

**descendants_and_self(self, \*\*kwargs)**
: Returns a list of descendants with self appended.

**clan(self, \*\*kwargs)**
: Returns a QuerySet of all ancestors, self, and all descendants.

**clan_count(self)**
: Returns the total number of clan nodes.

**siblings(self)**
: Returns a QuerySet of nodes that share a parent with this node, excluding self.

**siblings_count(self)**
: Returns the count of sibling nodes.

**siblings_with_self(self)**
: Returns a QuerySet of siblings including self.

**partners(self)**
: Returns a QuerySet of nodes that share a child with this node, excluding self.

**partners_count(self)**
: Returns the count of partner nodes.

**partners_with_self(self)**
: Returns a QuerySet of partners including self.

**connected_graph(self, \*\*kwargs)**
: Returns a QuerySet of all nodes connected in any direction to this node.

**connected_graph_node_count(self, \*\*kwargs)**
: Returns the count of nodes in the connected graph.

## Path Methods

**path(self, ending_node, \*\*kwargs)**
: Returns a QuerySet of the shortest path from self to `ending_node`. Sorted root-side toward leaf-side regardless of direction. Raises `NodeNotReachableException` if no path exists. Accepts `directional` (default `True`) — set to `False` to search in both directions.

**path_exists(self, ending_node, \*\*kwargs)**
: Returns `True` if a path exists from self to `ending_node`. Accepts `directional`.

**distance(self, ending_node, \*\*kwargs)**
: Returns the shortest hop count to `ending_node`.

**all_paths(self, ending_node, directional=True, max_results=None, \*\*kwargs)**
: Returns a list of QuerySets, each representing one path. Unlike `path()`, returns all paths, not just the shortest.

**all_paths_as_pk_lists(self, ending_node, directional=True, max_results=None, \*\*kwargs)**
: Returns a list of PK lists — lightweight alternative to `all_paths()`.

**weighted_path(self, ending_node, weight_field="weight", \*\*kwargs)**
: Returns a `(QuerySet, total_weight)` tuple for the minimum-weight path. The edge model must have the specified weight field. Raises `NodeNotReachableException` or `WeightFieldDoesNotExistException`.

**weighted_path_raw(self, ending_node, weight_field="weight", directional=True, \*\*kwargs)**
: Returns a `WeightedPathResult(nodes, total_weight)` namedtuple with raw PK list.

**weighted_distance(self, ending_node, weight_field="weight", \*\*kwargs)**
: Returns the total weight of the minimum-weight path.

## Predicate Methods

**is_root(self)**
: Returns `True` if this node has children but no parents.

**is_leaf(self)**
: Returns `True` if this node has parents but no children.

**is_island(self)**
: Returns `True` if this node has no parents and no children.

**is_ancestor_of(self, ending_node, \*\*kwargs)**
: Returns `True` if self is an ancestor of `ending_node`. Accepts `directional`.

**is_descendant_of(self, ending_node, \*\*kwargs)**
: Returns `True` if self is a descendant of `ending_node`. Accepts `directional`.

**is_sibling_of(self, ending_node)**
: Returns `True` if self and `ending_node` share a parent.

**is_partner_of(self, ending_node)**
: Returns `True` if self and `ending_node` share a child.

## Tree Methods

**descendants_tree(self)**
: Returns a nested dict representing the descendant tree. Each key is a node, each value is a dict of that node's children.

**ancestors_tree(self)**
: Returns a nested dict representing the ancestor tree. Each key is a node, each value is a dict of that node's parents.

## Edge Query Methods

**descendants_edges(self)**
: Returns a QuerySet of descendant edges, topologically sorted from root-side to leaf-side.

**ancestors_edges(self)**
: Returns a QuerySet of ancestor edges, topologically sorted from root-side to leaf-side.

**clan_edges(self)**
: Returns a QuerySet of all edges associated with this node.

## Root and Leaf Methods

**roots(self)**
: Returns a set of all root nodes reachable from this node.

**leaves(self)**
: Returns a set of all leaf nodes reachable from this node.

## Depth and Topological Methods

**node_depth(self)**
: Returns the longest path distance from any root to this node. Returns 0 for root and island nodes.

**ancestors_with_depth(self, \*\*kwargs)**
: Returns a list of `(ancestor_node, depth)` tuples, where depth is the longest path distance from the ancestor to this node.

**descendants_with_depth(self, \*\*kwargs)**
: Returns a list of `(descendant_node, depth)` tuples, where depth is the longest path distance from this node to the descendant.

**topological_descendants(self, \*\*kwargs)**
: Returns a QuerySet of self followed by all descendants in topological order.

## Lowest Common Ancestor

**lowest_common_ancestors(self, other, \*\*kwargs)**
: Returns a QuerySet of the lowest common ancestor(s) between this node and `other`. DAGs can have multiple LCAs. Returns empty QuerySet if nodes are disconnected.

## Graph Hashing

Requires NetworkX. See [Exporting and Transforming Graphs](transformations.md) for background.

**graph_hash(self, scope="connected", \*\*kwargs)**
: Returns a Weisfeiler-Lehman graph hash string. Scope options: `"connected"`, `"descendants"`, `"ancestors"`, `"clan"`.

**subgraph_hashes(self, scope="connected", \*\*kwargs)**
: Returns a dict of `{node_pk: [hash_str, ...]}` for WL subgraph hashes. Requires NetworkX >= 3.3.
