'''
A class to model hierarchies of objects following Directed Acyclic Graph structure.

The graph traversal queries use Postgresql's recursive CTEs to fetch an entire tree
of related node ids in a single query. These queries also topologically sort the ids
by generation.

Inspired by:
https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/
https://github.com/elpaso/django-dag
https://github.com/stdbrouw/django-treebeard-dag
'''

from django.db import models, connection
from django.db.models import Case, When
from django.core.exceptions import ValidationError


ANCESTOR_QUERY = '''
WITH RECURSIVE traverse(id, depth) AS (
    SELECT first.parent_id, 1
        FROM {relationship_table} AS first
        LEFT OUTER JOIN {relationship_table} AS second
        ON first.parent_id = second.child_id
    WHERE first.child_id = %(id)s
UNION
    SELECT DISTINCT parent_id, traverse.depth + 1
        FROM traverse
        INNER JOIN {relationship_table}
        ON {relationship_table}.child_id = traverse.id
)
SELECT id FROM traverse
GROUP BY id
ORDER BY MAX(depth) DESC, id ASC
'''

DESCENDANT_QUERY = '''
 WITH RECURSIVE traverse(id, depth) AS (
     SELECT first.child_id, 1
         FROM {relationship_table} AS first
         LEFT OUTER JOIN {relationship_table} AS second
         ON first.child_id = second.parent_id
     WHERE first.parent_id = %(id)s
 UNION
     SELECT DISTINCT child_id, traverse.depth + 1
         FROM traverse
         INNER JOIN {relationship_table}
         ON {relationship_table}.parent_id = traverse.id
)
SELECT id FROM traverse
GROUP BY id
ORDER BY MAX(depth), id ASC
'''

def filter_order(queryset, field_names, values):
    'Filter queryset where field_name in values, order results in the same order as values'
    if not isinstance(field_names, list):
        field_names = [field_names]
    case = []
    for pos, value in enumerate(values):
        when_condition = {field_names[0]: value, 'then': pos}
        case.append(When(**when_condition))
    order_by = Case(*case)
    filter_condition = {field_name + '__in': values
                        for field_name in field_names}
    return queryset.filter(**filter_condition).order_by(order_by)


def node_factory(edge_model, children_null=True, base_model=models.Model):
    edge_model_table = edge_model._meta.db_table

    class Node(base_model):
        children  = models.ManyToManyField(
                'self',
                blank = children_null,
                symmetrical = False,
                through = edge_model,
                related_name = 'parents')

        class Meta:
            abstract = True

        def add_child(self, descendant, **kwargs):
            kwargs.update({'parent' : self, 'child' : descendant })
            disable_check = kwargs.pop('disable_circular_check', False)
            cls = self.children.through(**kwargs)
            return cls.save(disable_circular_check=disable_check)

        def remove_child(self, descendant):
            self.children.through.objects.get(parent = self, child = descendant).delete()

        def add_parent(self, parent, *args, **kwargs):
            return parent.add_child(self, **kwargs)

        def remove_parent(self, parent):
            parent.children.through.objects.get(parent = parent, child = self).delete()

        def filter_order_ids(self, ids):
            return filter_order(self.__class__.objects, 'pk', ids)

        def ancestor_ids(self):
            with connection.cursor() as cursor:
                cursor.execute(ANCESTOR_QUERY.format(relationship_table=edge_model_table), {'id': self.id})
                return [row[0] for row in cursor.fetchall()]

        def self_and_ancestor_ids(self):
            return self.ancestor_ids() + [self.id]

        def ancestors(self):
            return self.filter_order_ids(self.ancestor_ids())

        def self_and_ancestors(self):
            return self.filter_order_ids(self.self_and_ancestor_ids())

        def descendant_ids(self):
            with connection.cursor() as cursor:
                cursor.execute(DESCENDANT_QUERY.format(relationship_table=edge_model_table), {'id': self.id})
                return [row[0] for row in cursor.fetchall()]

        def self_and_descendant_ids(self):
            return [self.id] + self.descendant_ids()

        def descendants(self):
            return self.filter_order_ids(self.descendant_ids())

        def self_and_descendants(self):
            return self.filter_order_ids(self.self_and_descendant_ids())

        def clan_ids(self):
            return self.ancestor_ids() + self.self_and_descendant_ids()

        def clan(self):
            return self.filter_order_ids(self.clan_ids())

        @staticmethod
        def circular_checker(parent, child):
            if child.id in parent.self_and_ancestor_ids():
                raise ValidationError('The object is an ancestor.')

    return Node


class EdgeManager(models.Manager):
    def descendants(self, node):
        return filter_order(self.model.objects, 'parent_id', node.self_and_descendant_ids())

    def ancestors(self, node):
        return filter_order(self.model.objects, 'child_id', node.self_and_ancestor_ids())

    def clan(self, node):
        return filter_order(self.model.objects, ['parent_id', 'child_id'], node.clan_ids())


def edge_factory(node_model, child_to_field='id', parent_to_field='id', concrete=True, base_model=models.Model):
    if isinstance(node_model, str):
        try:
            node_model_name = node_model.split('.')[1]
        except IndexError:
            node_model_name = node_model
    else:
        node_model_name = node_model._meta.model_name

    class Edge(base_model):
        parent = models.ForeignKey(
            node_model,
            related_name = '%s_child' % node_model_name,
            to_field = parent_to_field,
            on_delete=models.CASCADE)
        child = models.ForeignKey(
            node_model,
            related_name = '%s_parent' % node_model_name,
            to_field = child_to_field,
            on_delete=models.CASCADE)

        objects = EdgeManager()

        class Meta:
            abstract = not concrete

        def save(self, *args, **kwargs):
            if not kwargs.pop('disable_circular_check', False):
                self.parent.__class__.circular_checker(self.parent, self.child)
            super(Edge, self).save(*args, **kwargs) # Call the 'real' save() method.

    return Edge
