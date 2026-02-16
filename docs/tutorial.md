# Tutorial: Course Prerequisites

This tutorial builds a university course prerequisite system from scratch. By the end, you'll have a working DAG that models courses, their prerequisites, and the relationships between them.

The scenario: a computer science department needs to track which courses must be completed before a student can enroll in more advanced ones. A single course can have multiple prerequisites, and one course can be a prerequisite for many others - a natural DAG structure.

```{mermaid}
flowchart TD
    CS101[Intro to CS] --> CS201[Data Structures]
    CS201 --> CS301[Algorithms]
    CS201 --> CS250[Databases]
    CS301 --> CS350[Operating Systems]
    CS301 --> CS340[Machine Learning]
    CS250 --> CS260[Web Development]
```

## Step 1: Define your models

django-postgresql-dag uses a factory pattern to generate abstract model classes. You provide two models - an Edge and a Node - and the factories wire up the foreign keys and manager methods.

**Order matters**: define the Edge class first (referencing the Node by string name), then the Node class.

```python
# courses/models.py
from django.db import models
from django_postgresql_dag.models import edge_factory, node_factory


class Prerequisite(edge_factory("Course", concrete=False)):
    """An edge representing a prerequisite relationship between courses."""

    name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.parent.name} → {self.child.name}"

    def save(self, *args, **kwargs):
        self.name = f"{self.parent.name} → {self.child.name}"
        super().save(*args, **kwargs)


class Course(node_factory(Prerequisite)):
    """A university course that may have prerequisites."""

    name = models.CharField(max_length=200)
    course_code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.course_code}: {self.name}"
```

What's happening here:

- `edge_factory("Course", concrete=False)` creates an abstract base class with `parent` and `child` ForeignKey fields pointing to the `Course` model. The `concrete=False` argument means the factory produces an abstract model - your `Prerequisite` class provides the concrete table.
- `node_factory(Prerequisite)` creates an abstract base class with a ManyToManyField through `Prerequisite`, plus all the graph traversal methods (`ancestors()`, `descendants()`, `path()`, etc.).

After defining these models, run `makemigrations` and `migrate` as usual.

## Step 2: Create courses and prerequisites

Open a Django shell (`python manage.py shell`) and create some courses:

```python
>>> from courses.models import Course, Prerequisite

# Create courses
>>> intro = Course.objects.create(name="Intro to CS", course_code="CS101")
>>> data_structures = Course.objects.create(name="Data Structures", course_code="CS201")
>>> algorithms = Course.objects.create(name="Algorithms", course_code="CS301")
>>> databases = Course.objects.create(name="Databases", course_code="CS250")
>>> os = Course.objects.create(name="Operating Systems", course_code="CS350")
>>> ml = Course.objects.create(name="Machine Learning", course_code="CS340")
>>> web_dev = Course.objects.create(name="Web Development", course_code="CS260")
```

Now connect them with prerequisite relationships. `add_child` creates an edge from the current node (parent) to the specified node (child):

```python
# Intro to CS is a prerequisite for Data Structures
>>> intro.add_child(data_structures)

# Data Structures is a prerequisite for several courses
>>> data_structures.add_child(algorithms)
>>> data_structures.add_child(databases)

# Algorithms is a prerequisite for more advanced courses
>>> algorithms.add_child(os)
>>> algorithms.add_child(ml)

# Databases is a prerequisite for Web Development
>>> databases.add_child(web_dev)
```

You can also add relationships from the child side using `add_parent`:

```python
# Equivalent to: databases.add_child(web_dev)
# web_dev.add_parent(databases)
```

Each call creates a row in the `Prerequisite` (edge) table. The database now has 7 courses and 6 prerequisite edges.

## Step 3: Query the graph

With the graph built, you can ask questions about prerequisite chains.

**"What do I need to take before Algorithms?"** - use `ancestors()` to find all nodes reachable by following edges upward:

```python
>>> algorithms.ancestors()
<QuerySet [<Course: CS101: Intro to CS>, <Course: CS201: Data Structures>]>
```

**"What courses does Intro to CS unlock (directly or indirectly)?"** - use `descendants()` to find all nodes reachable by following edges downward:

```python
>>> intro.descendants()
<QuerySet [<Course: CS201: Data Structures>, <Course: CS301: Algorithms>, <Course: CS250: Databases>, <Course: CS350: Operating Systems>, <Course: CS340: Machine Learning>, <Course: CS260: Web Development>]>
```

**"What are the immediate next courses after Data Structures?"** - use `max_depth=1` to limit traversal to direct children:

```python
>>> data_structures.descendants(max_depth=1)
<QuerySet [<Course: CS301: Algorithms>, <Course: CS250: Databases>]>
```

**"Show me everything connected to Data Structures"** - `clan()` returns all ancestors, self, and all descendants:

```python
>>> data_structures.clan()
<QuerySet [<Course: CS101: Intro to CS>, <Course: CS201: Data Structures>, <Course: CS301: Algorithms>, <Course: CS250: Databases>, <Course: CS350: Operating Systems>, <Course: CS340: Machine Learning>, <Course: CS260: Web Development>]>
```

**"Which courses share a prerequisite with Databases?"** - `siblings()` returns nodes with the same parent:

```python
>>> databases.siblings()
<QuerySet [<Course: CS301: Algorithms>]>
```

Both Databases and Algorithms require Data Structures, so they're siblings.

## Step 4: Find paths

**"What's the prerequisite chain from Intro to CS to Operating Systems?"** - `path()` returns the shortest path:

```python
>>> intro.path(os)
<QuerySet [<Course: CS101: Intro to CS>, <Course: CS201: Data Structures>, <Course: CS301: Algorithms>, <Course: CS350: Operating Systems>]>
```

**"How many courses is that?"** - `distance()` returns the hop count:

```python
>>> intro.distance(os)
3
```

**"Can I go from Operating Systems back to Intro to CS?"** - by default, `path()` only searches downward. To search in both directions, set `directional=False`:

```python
>>> os.path(intro)
# Raises NodeNotReachableException - no downward path exists

>>> os.path(intro, directional=False)
<QuerySet [<Course: CS350: Operating Systems>, <Course: CS301: Algorithms>, <Course: CS201: Data Structures>, <Course: CS101: Intro to CS>]>
```

## Step 5: Check relationships

Predicate methods return boolean values and are useful for validation logic - for example, checking whether a student has completed the necessary prerequisites.

```python
# Is Intro to CS a root? (no prerequisites)
>>> intro.is_root()
True

# Is Operating Systems a leaf? (nothing requires it)
>>> os.is_leaf()
True

# Is any course completely disconnected?
>>> intro.is_island()
False

# Does completing Intro to CS eventually lead to Machine Learning?
>>> intro.is_ancestor_of(ml)
True

# Is Operating Systems downstream of Data Structures?
>>> os.is_descendant_of(data_structures)
True
```

**Finding roots and leaves for a specific node:**

```python
# What are the foundational courses for Machine Learning?
>>> ml.roots()
{<Course: CS101: Intro to CS>}

# What final courses can I reach from Data Structures?
>>> data_structures.leaves()
{<Course: CS350: Operating Systems>, <Course: CS340: Machine Learning>, <Course: CS260: Web Development>}
```

## Step 6: Visualize the structure

`descendants_tree()` returns a nested dictionary showing the graph structure:

```python
>>> intro.descendants_tree()
{
    <Course: CS201: Data Structures>: {
        <Course: CS301: Algorithms>: {
            <Course: CS350: Operating Systems>: {},
            <Course: CS340: Machine Learning>: {},
        },
        <Course: CS250: Databases>: {
            <Course: CS260: Web Development>: {},
        },
    },
}
```

And `ancestors_tree()` goes in the other direction:

```python
>>> os.ancestors_tree()
{
    <Course: CS301: Algorithms>: {
        <Course: CS201: Data Structures>: {
            <Course: CS101: Intro to CS>: {},
        },
    },
}
```

## Next steps

Now that you have a working DAG, here are some things to explore:

- [Filtering Graph Traversals](filtering.md) - limit queries by edge type, depth, or specific edges
- [Working with Paths and Algorithms](paths-and-algorithms.md) - weighted paths, topological sort, LCA, and more
- [Exporting and Transforming Graphs](transformations.md) - convert your graph to NetworkX, rustworkx, or JSON
- [Node API Reference](node-reference.md) - complete list of all node methods
- [Edge API Reference](edge-reference.md) - complete list of all edge manager methods
