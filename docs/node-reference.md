# Node API Reference

Complete reference for all methods available on Node model instances and the Node manager. For practical examples and usage patterns, see [Filtering Graph Traversals](filtering.md) and [Working with Paths and Algorithms](paths-and-algorithms.md).

Many of the examples on this page use the graph from the [Quickstart](quickstart.md):

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
```

## Manager Methods

These are called on `MyNode.objects`.

**roots(self, node=None)**
: Returns a QuerySet of all root nodes (nodes with no parents). If `node` is provided, returns only the roots reachable from that node.

**leaves(self, node=None)**
: Returns a QuerySet of all leaf nodes (nodes with no children). If `node` is provided, returns only the leaves reachable from that node.

**connected_components(self)**
: Returns a list of QuerySets, one per disconnected subgraph. Each QuerySet can be further filtered.

Each returned QuerySet is a disconnected subgraph. Nodes with no edges (islands) form their own component:

```{mermaid}
flowchart TD
    subgraph Component 1
        root --> a1 & a2 & a3
        a1 --> b1
        a2 --> b1
        a3 --> b2
    end
    subgraph Component 2
        island
    end
```

**graph_stats(self)**
: Returns a dict with aggregate metrics: `node_count`, `edge_count`, `root_count`, `leaf_count`, `island_count`, `max_depth`, `avg_depth`, `density`, `component_count`. Runs O(N) queries - suitable for analytics, not hot paths.

**topological_sort(self, max_depth=None)**
: Returns a QuerySet of all nodes in topological order (parents before children). Island nodes are included at the front.

Topological order places every parent before its children. Nodes at the same depth appear in the same tier:

```{mermaid}
flowchart LR
    subgraph "depth 0"
        root
    end
    subgraph "depth 1"
        a1
        a2
        a3
    end
    subgraph "depth 2"
        b1
        b2
        b3
        b4
    end
    subgraph "depth 3"
        c1
        c2
    end
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
```

**critical_path(self, weight_field=None, max_depth=None)**
: Returns a `(QuerySet, total_weight)` tuple for the longest weighted path from any root to any leaf. Without `weight_field`, uses hop count (each edge = 1).

The critical path (green) is the longest path from any root to any leaf. With uniform edge weights of 1, this is root - a3 - b3 - c1 (total weight: 3):

```{mermaid}
flowchart TD
    root ==> a3
    root --> a1 & a2
    a1 --> b1 & b2
    a2 --> b2
    a3 ==> b3
    a3 --> b4
    b3 ==> c1
    b3 --> c2
    b4 --> c1
    style root fill:#4CAF50,color:#fff
    style a3 fill:#4CAF50,color:#fff
    style b3 fill:#4CAF50,color:#fff
    style c1 fill:#4CAF50,color:#fff
```

**transitive_reduction(self, delete=False)**
: Identifies redundant edges (A→C is redundant if C is reachable from A via a path of length >= 2). Returns a QuerySet of redundant edges by default (dry run). With `delete=True`, deletes them and returns the count.

An edge is redundant if the child is already reachable through a longer path. Here, A - C (dashed red) is redundant because C is reachable from A via B. `transitive_reduction()` identifies and optionally deletes these edges:

```{mermaid}
flowchart TD
    A --> B --> C
    A -.->|redundant| C
    linkStyle 2 stroke:#F44336,stroke-width:2px
```

After reduction, reachability is unchanged but the redundant shortcut is removed:

```{mermaid}
flowchart TD
    A --> B --> C
```

## Mutation Methods

**add_child(self, child, \*\*kwargs)**
: Creates an edge from this node to `child`. Extra keyword arguments are passed to the edge model constructor. Supports special kwargs: `disable_circular_check` (default `False`), `allow_duplicate_edges` (default `True`), `allow_redundant_edges` (default from setting or `True`). See [Configuration Reference](configuration.md) for details.

**remove_child(self, child, delete_node=False)**
: Removes the edge to `child`. If `child` is `None`, removes edges to all children. With `delete_node=True`, also deletes the child node(s).

**add_parent(self, parent, \*args, \*\*kwargs)**
: Creates an edge from `parent` to this node. Accepts the same special kwargs as `add_child()`.

**remove_parent(self, parent, delete_node=False)**
: Removes the edge from `parent`. If `parent` is `None`, removes edges from all parents. With `delete_node=True`, also deletes the parent node(s).

## Traversal Methods

All traversal methods accept optional keyword arguments for [filtering](filtering.md): `max_depth`, `edge_type`, `disallowed_edges_queryset`, `allowed_edges_queryset`, `disallowed_nodes_queryset`, `allowed_nodes_queryset`, `limiting_edges_set_fk`.

`b3.ancestors()` returns all nodes reachable by following edges upward (green). The starting node (orange) is not included:

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    style root fill:#4CAF50,color:#fff
    style a3 fill:#4CAF50,color:#fff
    style b3 fill:#FF9800,color:#fff
```

`a3.descendants()` returns all nodes reachable by following edges downward (green):

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    style a3 fill:#FF9800,color:#fff
    style b3 fill:#4CAF50,color:#fff
    style b4 fill:#4CAF50,color:#fff
    style c1 fill:#4CAF50,color:#fff
    style c2 fill:#4CAF50,color:#fff
```

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
: Returns a list of descendants ordered from furthest (leaves) to nearest, with self appended at the end. Mirrors the ordering of `ancestors_and_self()` (furthest-first, converging toward self).

**clan(self, \*\*kwargs)**
: Returns a QuerySet of all ancestors, self, and all descendants.

`b3.clan()` returns ancestors (green), self (orange), and descendants (green) - the complete vertical slice through b3:

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    style root fill:#4CAF50,color:#fff
    style a3 fill:#4CAF50,color:#fff
    style b3 fill:#FF9800,color:#fff
    style c1 fill:#4CAF50,color:#fff
    style c2 fill:#4CAF50,color:#fff
```

**clan_count(self)**
: Returns the total number of clan nodes.

**siblings(self)**
: Returns a QuerySet of nodes that share a parent with this node, excluding self.

`a1.siblings()` returns nodes that share a parent with a1 (green). Since root is parent of a1, a2, and a3, the siblings are a2 and a3:

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    style a1 fill:#FF9800,color:#fff
    style a2 fill:#4CAF50,color:#fff
    style a3 fill:#4CAF50,color:#fff
```

**siblings_count(self)**
: Returns the count of sibling nodes.

**siblings_with_self(self)**
: Returns a QuerySet of siblings including self.

**partners(self)**
: Returns a QuerySet of nodes that share a child with this node, excluding self.

`a1.partners()` returns nodes that share a child with a1 (green). Both a1 and a2 are parents of b2, so a2 is a partner:

```{mermaid}
flowchart TD
    a1 --> b2
    a2 --> b2
    style a1 fill:#FF9800,color:#fff
    style a2 fill:#4CAF50,color:#fff
```

**partners_count(self)**
: Returns the count of partner nodes.

**partners_with_self(self)**
: Returns a QuerySet of partners including self.

**connected_graph(self, \*\*kwargs)**
: Returns a QuerySet of all nodes connected in any direction to this node. Supports all [filter kwargs](filtering.md) including `max_depth`, `disallowed_nodes_queryset`, `allowed_nodes_queryset`, `disallowed_edges_queryset`, `allowed_edges_queryset`, and `limiting_edges_set_fk`.

**connected_graph_node_count(self, \*\*kwargs)**
: Returns the count of nodes in the connected graph.

## Path Methods

**path(self, ending_node, \*\*kwargs)**
: Returns a QuerySet of the shortest path from self to `ending_node`. Sorted root-side toward leaf-side regardless of direction. Raises `NodeNotReachableException` if no path exists. Accepts `directional` (default `True`) - set to `False` to search in both directions.

`root.path(c1)` returns the shortest path (green). Here, root - a3 - b3 - c1 and root - a3 - b4 - c1 are both 3 hops; `path()` returns one:

```{mermaid}
flowchart TD
    root ==> a3
    root --> a1 & a2
    a1 --> b1 & b2
    a2 --> b2
    a3 ==> b3
    a3 --> b4
    b3 ==> c1
    b3 --> c2
    b4 --> c1
    style root fill:#4CAF50,color:#fff
    style a3 fill:#4CAF50,color:#fff
    style b3 fill:#4CAF50,color:#fff
    style c1 fill:#4CAF50,color:#fff
```

**path_exists(self, ending_node, \*\*kwargs)**
: Returns `True` if a path exists from self to `ending_node`. Accepts `directional`.

**distance(self, ending_node, \*\*kwargs)**
: Returns the shortest hop count to `ending_node`.

**all_paths(self, ending_node, directional=True, max_results=None, \*\*kwargs)**
: Returns a list of QuerySets, each representing one path. Unlike `path()`, returns all paths, not just the shortest.

`root.all_paths(c1)` returns both paths: root - a3 - b3 - c1 (green) and root - a3 - b4 - c1 (blue):

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    linkStyle 2 stroke:#4CAF50,stroke-width:3px
    linkStyle 6 stroke:#4CAF50,stroke-width:3px
    linkStyle 8 stroke:#4CAF50,stroke-width:3px
    linkStyle 7 stroke:#2196F3,stroke-width:3px
    linkStyle 10 stroke:#2196F3,stroke-width:3px
```

**all_paths_as_pk_lists(self, ending_node, directional=True, max_results=None, \*\*kwargs)**
: Returns a list of PK lists - lightweight alternative to `all_paths()`.

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

`a3.descendants_tree()` returns a nested dict mirroring this subgraph. Each node maps to a dict of its children:

```{mermaid}
flowchart TD
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    style a3 fill:#FF9800,color:#fff
```

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

Depth is the longest path distance from any root to a node. Roots have depth 0:

```{mermaid}
flowchart TD
    root["root (depth 0)"] --> a1["a1 (depth 1)"] & a2["a2 (depth 1)"] & a3["a3 (depth 1)"]
    a1 --> b1["b1 (depth 2)"] & b2["b2 (depth 2)"]
    a2 --> b2
    a3 --> b3["b3 (depth 2)"] & b4["b4 (depth 2)"]
    b3 --> c1["c1 (depth 3)"] & c2["c2 (depth 3)"]
    b4 --> c1
```

**ancestors_with_depth(self, \*\*kwargs)**
: Returns a list of `(ancestor_node, depth)` tuples, where depth is the longest path distance from the ancestor to this node. Supports [filter kwargs](filtering.md): `disallowed_nodes_queryset`, `allowed_nodes_queryset`, `disallowed_edges_queryset`, `allowed_edges_queryset`, `limiting_edges_set_fk`.

**descendants_with_depth(self, \*\*kwargs)**
: Returns a list of `(descendant_node, depth)` tuples, where depth is the longest path distance from this node to the descendant. Supports the same [filter kwargs](filtering.md) as `ancestors_with_depth()`.

**topological_descendants(self, \*\*kwargs)**
: Returns a QuerySet of self followed by all descendants in topological order.

## Lowest Common Ancestor

**lowest_common_ancestors(self, other, \*\*kwargs)**
: Returns a QuerySet of the lowest common ancestor(s) between this node and `other`. DAGs can have multiple LCAs. Returns empty QuerySet if nodes are disconnected.

`b1.lowest_common_ancestors(b3)` returns root (orange) - the deepest node that is an ancestor of both b1 and b3 (blue):

```{mermaid}
flowchart TD
    root --> a1 & a2 & a3
    a1 --> b1 & b2
    a2 --> b2
    a3 --> b3 & b4
    b3 --> c1 & c2
    b4 --> c1
    style b1 fill:#2196F3,color:#fff
    style b3 fill:#2196F3,color:#fff
    style root fill:#FF9800,color:#fff
```

Unlike trees, DAGs can have multiple LCAs. Here, m and n (blue) share two LCAs: p1 and p2 (orange), because neither is an ancestor of the other:

```{mermaid}
flowchart TD
    p1 --> m & n
    p2 --> m & n
    style m fill:#2196F3,color:#fff
    style n fill:#2196F3,color:#fff
    style p1 fill:#FF9800,color:#fff
    style p2 fill:#FF9800,color:#fff
```

## Graph Hashing

Requires NetworkX. See [Exporting and Transforming Graphs](transformations.md) for background.

**graph_hash(self, scope="connected", \*\*kwargs)**
: Returns a Weisfeiler-Lehman graph hash string. Scope options: `"connected"`, `"descendants"`, `"ancestors"`, `"clan"`.

**subgraph_hashes(self, scope="connected", \*\*kwargs)**
: Returns a dict of `{node_pk: [hash_str, ...]}` for WL subgraph hashes. Requires NetworkX >= 3.3.
