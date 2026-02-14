# Transformations

Provides utilities for converting django-postgresql-dag querysets into graph library objects and serialization formats. You can export to NetworkX graphs, rustworkx graphs, or JSON — making it straightforward to leverage external graph algorithms on your DAG data.

## Installation

The transformation functions require optional extras depending on which backend you want to use.

```bash
pip install django-postgresql-dag[transforms]
```

This installs `networkx`, `rustworkx`, and `pandas`.

## Common Parameters

All export functions accept a queryset of either nodes or edges. The queryset type is detected automatically — if you pass a nodes queryset, the corresponding edges are looked up, and vice versa.

The following parameters are shared across `nx_from_queryset`, `rx_from_queryset`, and `dag_to_json`:

- `node_attribute_fields_list`: a list of field name strings to include as attributes on each node
- `edge_attribute_fields_list`: a list of field name strings to include as attributes on each edge
- `date_strf`: if any fields are date-like, a strftime format string to apply (e.g. `"%Y-%m-%d"`)
- `digraph`: boolean controlling whether to create a directed or undirected graph

## NetworkX Export

**nx_from_queryset(queryset, graph_attributes_dict=None, node_attribute_fields_list=None, edge_attribute_fields_list=None, date_strf=None, digraph=False)**

Provided a queryset of nodes or edges, returns a NetworkX graph. By default returns an undirected `nx.Graph`; set `digraph=True` for an `nx.DiGraph`.

Graph-level attributes are passed as a dictionary and unpacked as keyword arguments to the NetworkX graph constructor.

```python
>>> from django_postgresql_dag.transformations import nx_from_queryset
>>> from myapp.models import NetworkNode

>>> root = NetworkNode.objects.get(name="root")

# Basic export — undirected graph from a node's clan
>>> graph = nx_from_queryset(root.clan())
>>> graph.nodes
NodeView((1, 2, 3, 4, 5, 6))

# Directed graph with attributes
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

Node PKs are used directly as NetworkX node identifiers, so you can look up node data with `graph.nodes[node.pk]`.

## rustworkx Export

**rx_from_queryset(queryset, graph_attributes=None, node_attribute_fields_list=None, edge_attribute_fields_list=None, date_strf=None, digraph=False)**

Provided a queryset of nodes or edges, returns a rustworkx graph. By default returns an undirected `rx.PyGraph`; set `digraph=True` for an `rx.PyDiGraph`.

Unlike NetworkX, rustworkx uses integer node indices (0, 1, 2, ...) internally. The Django PK is always stored in the node data dictionary under the `"pk"` key, so you can map back to your Django models.

Graph-level attributes can be any Python object and are stored as `graph.attrs`.

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

# Graph attributes
>>> graph = rx_from_queryset(
...     root.clan(),
...     graph_attributes={"name": "my_dag", "version": 2},
... )
>>> graph.attrs
{'name': 'my_dag', 'version': 2}
```

The PK is always present in node data, even if no `node_attribute_fields_list` is provided:

```python
>>> graph = rx_from_queryset(root.clan())
>>> graph[0]
{'pk': 1}
```

### Working with rustworkx algorithms

Once you have a rustworkx graph, you have access to fast Rust-backed graph algorithms:

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

## JSON Serialization

**json_from_queryset(queryset, graph_attributes=None, node_attribute_fields_list=None, edge_attribute_fields_list=None, date_strf=None, digraph=False)**

Builds a rustworkx graph from a queryset and serializes it to a JSON string using `rx.node_link_json()`. This is a convenience function that combines `rx_from_queryset()` with JSON serialization. All attribute values are stringified for JSON compatibility.

Requires the `rustworkx` extra.

```python
>>> import json
>>> from django_postgresql_dag.transformations import json_from_queryset
>>> from myapp.models import NetworkNode

>>> root = NetworkNode.objects.get(name="root")

# Directed JSON output
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

The output follows the node-link JSON format with the following top-level keys:

- `directed`: boolean indicating whether the graph is directed
- `multigraph`: boolean indicating whether the graph allows multiple edges
- `attrs`: graph-level attributes (from `graph_attributes`)
- `nodes`: list of node objects, each with an `id` (index) and `data` dict
- `links`: list of edge objects, each with `source`, `target`, `id`, and `data` dict

By default, `digraph=False` produces undirected output, matching the convention of the other export functions:

```python
>>> parsed = json.loads(json_from_queryset(root.clan()))
>>> parsed["directed"]
False
```

## Utility Functions

The following utility functions are also available and used internally by the export functions. They can be useful when working directly with querysets.

**edges_from_nodes_queryset(nodes_queryset)**

Provided a QuerySet of nodes, returns a QuerySet of all Edge instances where both the parent and child are within the provided nodes.

**nodes_from_edges_queryset(edges_queryset)**

Provided a QuerySet of edges, returns a QuerySet of all Node instances that appear as a parent or child in the provided edges.

**model_to_dict(instance, fields=None, date_strf=None)**

Converts a model instance to a dictionary for the specified fields. Handles standard fields, ForeignKey fields, ManyToMany fields (with optional subfield lookup via `__` notation), date/datetime fields, UUID fields, file/image fields, and callable methods on the instance.
