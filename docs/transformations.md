# Exporting and Transforming Graphs

Once you've built your graph, you may want to export it for visualization, analysis with external graph libraries, or serialization. This page covers the export functions for NetworkX, rustworkx, and JSON, as well as the graph hashing utilities.

## Installation

Export functions require optional extras:

```bash
pip install django-postgresql-dag[transforms]
```

This installs `networkx`, `rustworkx`, and `pandas`.

## Common parameters

All export functions accept a queryset of either nodes or edges. The queryset type is detected automatically — pass a nodes queryset and the corresponding edges are looked up, or vice versa.

These parameters are shared across `nx_from_queryset`, `rx_from_queryset`, and `json_from_queryset`:

- `node_attribute_fields_list` — field names to include as attributes on each node
- `edge_attribute_fields_list` — field names to include as attributes on each edge
- `date_strf` — strftime format string for date-like fields (e.g. `"%Y-%m-%d"`)
- `digraph` — `True` for a directed graph, `False` (default) for undirected

## NetworkX export

`nx_from_queryset()` converts a queryset into a NetworkX graph. Node PKs are used directly as NetworkX node identifiers.

```python
>>> from django_postgresql_dag.transformations import nx_from_queryset
>>> from myapp.models import NetworkNode

>>> root = NetworkNode.objects.get(name="root")

# Basic undirected graph from a node's clan
>>> graph = nx_from_queryset(root.clan())
>>> graph.nodes
NodeView((1, 2, 3, 4, 5, 6))

# Directed graph with node and edge attributes
>>> graph = nx_from_queryset(
...     root.clan(),
...     graph_attributes_dict={"name": "my_dag"},
...     node_attribute_fields_list=["name"],
...     edge_attribute_fields_list=["name"],
...     digraph=True,
... )
>>> graph.graph
{'name': 'my_dag'}
>>> graph.nodes[root.pk]
{'name': 'root'}
```

## rustworkx export

`rx_from_queryset()` converts a queryset into a rustworkx graph. Unlike NetworkX, rustworkx uses integer indices internally. The Django PK is always stored in the node data dictionary under the `"pk"` key.

```python
>>> from django_postgresql_dag.transformations import rx_from_queryset
>>> from myapp.models import NetworkNode

>>> root = NetworkNode.objects.get(name="root")

# Directed graph with node attributes
>>> graph = rx_from_queryset(
...     root.clan(),
...     node_attribute_fields_list=["name"],
...     digraph=True,
... )
>>> graph.num_nodes()
6
>>> graph[0]
{'pk': 1, 'name': 'root'}

# Graph-level attributes
>>> graph = rx_from_queryset(
...     root.clan(),
...     graph_attributes={"name": "my_dag", "version": 2},
... )
>>> graph.attrs
{'name': 'my_dag', 'version': 2}
```

The PK is always present in node data, even without `node_attribute_fields_list`:

```python
>>> graph = rx_from_queryset(root.clan())
>>> graph[0]
{'pk': 1}
```

### Using rustworkx algorithms

Once you have a rustworkx graph, you get access to fast Rust-backed algorithms:

```python
>>> import rustworkx as rx
>>> from django_postgresql_dag.transformations import rx_from_queryset

>>> graph = rx_from_queryset(root.clan(), digraph=True)

# Topological sort (returns list of node indices)
>>> rx.topological_sort(graph)
[0, 1, 2, 3, 4, 5]

# All-pairs shortest path lengths
>>> rx.all_pairs_dijkstra_shortest_paths(graph, lambda _: 1.0)

# Transitive reduction
>>> reduced = rx.transitive_reduction(graph)
```

### Mapping indices back to Django objects

Since rustworkx uses integer indices, you may want to map results back to model instances:

```python
>>> graph = rx_from_queryset(root.clan(), digraph=True)

# Build an index-to-PK lookup
>>> index_to_pk = {idx: graph[idx]["pk"] for idx in graph.node_indices()}

# After a topological sort, get the actual node objects
>>> sorted_indices = rx.topological_sort(graph)
>>> sorted_pks = [index_to_pk[i] for i in sorted_indices]
>>> NetworkNode.objects.filter(pk__in=sorted_pks)
```

## JSON serialization

`json_from_queryset()` builds a rustworkx graph from a queryset and serializes it to a JSON string. All attribute values are stringified for JSON compatibility.

```python
>>> import json
>>> from django_postgresql_dag.transformations import json_from_queryset
>>> from myapp.models import NetworkNode

>>> root = NetworkNode.objects.get(name="root")

>>> result = json_from_queryset(
...     root.clan(),
...     graph_attributes={"name": "my_dag"},
...     node_attribute_fields_list=["name"],
...     edge_attribute_fields_list=["name"],
...     digraph=True,
... )
>>> parsed = json.loads(result)
>>> parsed["directed"]
True
>>> parsed["attrs"]
{'name': 'my_dag'}
>>> parsed["nodes"][0]["data"]
{'pk': '1', 'name': 'root'}
>>> parsed["links"][0]["data"]
{'name': 'root a1'}
```

The output follows the node-link JSON format with these top-level keys:

- `directed` — whether the graph is directed
- `multigraph` — whether the graph allows multiple edges
- `attrs` — graph-level attributes
- `nodes` — list of node objects, each with `id` (index) and `data` dict
- `links` — list of edge objects, each with `source`, `target`, `id`, and `data` dict

By default, `digraph=False` produces undirected output:

```python
>>> parsed = json.loads(json_from_queryset(root.clan()))
>>> parsed["directed"]
False
```

## Graph hashing

These functions use NetworkX's Weisfeiler-Lehman algorithm to compute structural hashes of DAG subgraphs. Useful for comparing graph structures, caching, and change detection.

`graph_hash()` returns a hash string for a queryset:

```python
>>> from django_postgresql_dag.transformations import graph_hash
>>> h = graph_hash(root.clan())
>>> h
'a1b2c3d4e5f6...'
```

`subgraph_hashes()` returns per-node hashes as `{node_pk: [hash_str, ...]}`:

```python
>>> from django_postgresql_dag.transformations import subgraph_hashes
>>> hashes = subgraph_hashes(root.clan())
>>> hashes[root.pk]
['abc123...', 'def456...', ...]
```

`graphs_are_isomorphic()` compares two querysets by their graph hash:

```python
>>> from django_postgresql_dag.transformations import graphs_are_isomorphic
>>> graphs_are_isomorphic(node_a.clan(), node_b.clan())
True
```

WL hashing is not collision-free — hash equality is necessary but not sufficient for true isomorphism.

These functions also have node-level convenience methods that use lazy imports (so NetworkX isn't required at import time):

```python
node.graph_hash(scope="connected")       # -> str
node.subgraph_hashes(scope="connected")  # -> dict
```

Scope options: `"connected"`, `"descendants"`, `"ancestors"`, `"clan"`.

## Utility functions

These functions are used internally by the export functions, but can be useful when working with querysets directly.

**`edges_from_nodes_queryset(nodes_queryset)`** — Given a queryset of nodes, returns a queryset of all edges where both parent and child are in the provided nodes.

**`nodes_from_edges_queryset(edges_queryset)`** — Given a queryset of edges, returns a queryset of all nodes that appear as a parent or child in the provided edges.

**`model_to_dict(instance, fields=None, date_strf=None)`** — Converts a model instance to a dictionary for the specified fields. Handles ForeignKeys, ManyToMany fields (with `__` subfield lookup), dates, UUIDs, file fields, and callable methods.
