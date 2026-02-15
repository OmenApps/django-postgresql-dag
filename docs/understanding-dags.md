# Understanding Directed Acyclic Graphs

## What is a graph?

A graph is a data structure made of two things: **nodes** (also called vertices) and **edges** (connections between nodes). If you've worked with linked lists or trees, you've already used specialized forms of graphs.

A graph becomes interesting when nodes can have multiple connections. Unlike a linked list (one connection per node) or a tree (one parent per node), a general graph places no limits on how nodes connect to each other.

## What makes it "directed" and "acyclic"?

**Directed** means edges have a direction - they go *from* one node *to* another. Think of one-way streets: just because you can get from A to B doesn't mean you can get from B to A.

**Acyclic** means there are no cycles. You can never follow edges and end up back where you started. This constraint is what separates a DAG from a general directed graph, and it's what makes DAGs so useful for modeling dependencies.

Put them together: a **Directed Acyclic Graph (DAG)** is a set of nodes connected by one-way edges, where no path loops back on itself.

## Real-world examples

DAGs show up everywhere:

- **Course prerequisites** - "Data Structures" requires "Intro to CS," and "Algorithms" requires "Data Structures." A course can have multiple prerequisites, and one course can be a prerequisite for many others.
- **Org charts with matrix reporting** - An employee might report to both a functional manager and a project manager. Unlike a tree, a person can have multiple "parents."
- **Build systems** - Target A depends on libraries B and C, which both depend on library D. Make, Bazel, and similar tools all model this as a DAG.
- **Version histories** - Git commits form a DAG. A merge commit has two parents; branches diverge and reconverge without cycles.
- **Task scheduling** - Task C can't start until both A and B finish. The dependency graph is a DAG, and topological sorting gives you a valid execution order.
- **Data pipelines** - Apache Airflow models workflows as DAGs, where each node is a task and edges represent data flow.

## Key terminology

These terms appear throughout the documentation and API:

**Node**
: An entity in the graph. In django-postgresql-dag, nodes are Django model instances.

**Edge**
: A directed connection from a **parent** node to a **child** node. Edges are also Django model instances, stored in a separate table.

**Root**
: A node with no parents (no incoming edges). A DAG can have multiple roots.

**Leaf**
: A node with no children (no outgoing edges). A DAG can have multiple leaves.

**Island**
: A node with no parents *and* no children - completely disconnected from the rest of the graph.

**Ancestor**
: Any node reachable by following edges *upward* (toward roots). Your parent is an ancestor, your parent's parent is an ancestor, and so on.

**Descendant**
: Any node reachable by following edges *downward* (toward leaves). Your child is a descendant, your child's child is a descendant, and so on.

**Clan**
: All ancestors + self + all descendants. The complete vertical slice of the graph centered on a node.

**Sibling**
: Nodes that share at least one parent.

**Partner**
: Nodes that share at least one child.

**Path**
: An ordered sequence of nodes connected by edges, leading from one node to another.

**Depth**
: The length of the longest path from any root to a given node. Root nodes have depth 0.

## DAG vs. tree: when do you need a DAG?

A tree is actually a special case of a DAG - one where every node has at most one parent. If your data fits a strict tree (categories, file systems, single-inheritance class hierarchies), a tree library will be simpler.

You need a DAG when nodes can have **multiple parents**:

- A course can have multiple prerequisites
- A file can belong to multiple categories
- A task can depend on several other tasks
- A component can be used in multiple assemblies

If you find yourself duplicating tree nodes or adding cross-references to work around a tree's single-parent limitation, a DAG is probably the right model.

## How this package works

Several strategies exist for storing graphs in a relational database. Here's how they compare:

**Adjacency list** (store each edge as a row with parent_id and child_id)
: Simple to write, but retrieving all ancestors or descendants requires multiple queries - one per level of depth. For a graph 10 levels deep, that's 10 round trips to the database.

**Nested sets** (assign left/right numbering to encode hierarchy)
: Fast reads, but updates require renumbering large portions of the table. Designed for trees, not DAGs.

**Materialized path** (store the full path as a string, like "/1/4/7/")
: Works for trees but breaks down with multiple parents, since a node would need multiple paths stored.

**Closure table** (pre-compute and store all ancestor-descendant pairs)
: Handles DAGs and is fast for reads, but the closure table can grow quadratically and must be maintained on every insert or delete.

**Recursive CTEs** (what this package uses)
: PostgreSQL's `WITH RECURSIVE` lets you traverse the graph in a single query, no matter how deep it goes. Edges are stored as simple parent/child rows (like an adjacency list), keeping writes fast. Reads are also fast because the recursion happens inside the database engine, not in Python. The tradeoff is that this approach requires PostgreSQL - it won't work with SQLite, MySQL, or other databases.

django-postgresql-dag stores edges in a standard adjacency list table and uses PostgreSQL recursive CTEs for all traversal queries. This gives you the simplicity of adjacency lists for writes, with the performance of a single query for reads. The CTE-based approach handles arbitrary depth, multiple parents, and complex path queries without requiring denormalized data structures.

## Next steps

- [Quickstart Example](quickstart.md) - see the code in action with minimal explanation
- [Tutorial: Course Prerequisites](tutorial.md) - a step-by-step walkthrough building a real DAG
- [Configuration Reference](configuration.md) - installation and setup details
