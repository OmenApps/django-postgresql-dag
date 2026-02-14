"""Functions for transforming RawQuerySet or other outputs of django-postgresql-dag to alternate formats."""

import inspect
from itertools import chain

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Case, When
from django.db.models.fields import DateTimeField, UUIDField
from django.db.models.fields.files import FileField, ImageField
from django.db.models.fields.related import ManyToManyField

from .exceptions import GraphModelsCannotBeParsedException, IncorrectQuerysetTypeException, IncorrectUsageException


def _ordered_filter(queryset, field_names, values):
    """Filter the provided queryset for 'field_name__in values' for each given field_name in [field_names].

    Orders results in the same order as provided values.

        For instance
            _ordered_filter(self.__class__.objects, "pk", pks)
        returns a queryset of the current class, with instances where the 'pk' field matches a pk in pks.
    """
    if not isinstance(field_names, list):
        field_names = [field_names]
    case = []
    for pos, value in enumerate(values):
        when_condition = {field_names[0]: value, "then": pos}
        case.append(When(**when_condition))
    order_by = Case(*case)
    filter_condition = {field_name + "__in": values for field_name in field_names}
    return queryset.filter(**filter_condition).order_by(order_by)


def get_instance_characteristics(instance):
    """Return a tuple of the node & edge model classes and the instance_type for the provided instance."""
    try:
        # Assume a queryset of nodes was provided
        _NodeModel = instance._meta.model
        _EdgeModel = instance._meta.model._meta.get_field("parents").through
        instance_type = "node"
    except FieldDoesNotExist:
        try:
            # Assume a queryset of edges was provided
            _EdgeModel = instance._meta.model
            _NodeModel = instance._meta.model._meta.get_field("parent").related_model
            instance_type = "edge"
        except FieldDoesNotExist:
            raise GraphModelsCannotBeParsedException
    return (_NodeModel, _EdgeModel, instance_type)


def get_queryset_characteristics(queryset):
    """Return a tuple of the node & edge model classes and the queryset type for the provided queryset."""
    try:
        # Assume a queryset of nodes was provided
        _NodeModel = queryset.model
        _EdgeModel = queryset.model._meta.get_field("parents").through
        queryset_type = "nodes_queryset"
    except FieldDoesNotExist:
        try:
            # Assume a queryset of edges was provided
            _EdgeModel = queryset.model
            _NodeModel = queryset.model._meta.get_field("parent").related_model
            queryset_type = "edges_queryset"
        except FieldDoesNotExist:
            raise GraphModelsCannotBeParsedException
    return (_NodeModel, _EdgeModel, queryset_type)


def model_to_dict(instance, fields=None, date_strf=None):
    """Return a dictionary of {field_name: field_value} for a given model instance.

    e.g.: model_to_dict(myqueryset.first(), fields=["id",])

    For DateTimeFields, a formatting string can be provided.

    Adapted from: https://ziwon.github.io/post/using_custom_model_to_dict_in_django/
    """

    if not fields:
        raise IncorrectUsageException("fields list must be provided")

    opts = instance._meta
    data = {}
    __fields = list(map(lambda a: a.split("__")[0], fields or []))

    for f in chain(opts.concrete_fields, opts.private_fields, opts.many_to_many):
        is_editable = getattr(f, "editable", False)

        if fields and f.name not in __fields:
            continue

        if isinstance(f, DateTimeField):
            dt = f.value_from_object(instance)
            if dt is None:
                data[f.name] = None
            else:
                # Format based on format string provided, otherwise return a timestamp
                data[f.name] = dt.strftime(date_strf) if date_strf else dt.timestamp()

        elif isinstance(f, ImageField):
            image = f.value_from_object(instance)
            data[f.name] = image.url if image else None

        elif isinstance(f, FileField):
            file = f.value_from_object(instance)
            data[f.name] = file.url if file else None

        elif isinstance(f, ManyToManyField):
            if instance.pk is None:
                data[f.name] = []
            else:
                m2m_value = f.value_from_object(instance)
                if isinstance(m2m_value, list):
                    try:
                        m2m_field = list(filter(lambda a: f.name in a and a.find("__") != -1, fields))[0]
                        key = m2m_field[len(f.name) + 2 :]
                        data[f.name] = [getattr(item, key) if hasattr(item, key) else item for item in m2m_value]
                    except IndexError:
                        data[f.name] = [item.pk if hasattr(item, "pk") else item for item in m2m_value]
                elif hasattr(m2m_value, "_result_cache") and m2m_value._result_cache is not None:
                    data[f.name] = [item.pk for item in m2m_value]  # type: ignore[union-attr]
                else:
                    try:
                        m2m_field = list(filter(lambda a: f.name in a and a.find("__") != -1, fields))[0]
                        key = m2m_field[len(f.name) + 2 :]
                        data[f.name] = list(m2m_value.values_list(key, flat=True))
                    except IndexError:
                        data[f.name] = list(m2m_value.values_list("pk", flat=True))
            continue

        elif isinstance(f, UUIDField):
            uuid = f.value_from_object(instance)
            data[f.name] = str(uuid) if uuid else None

        # ToDo: Process other model fields

        elif is_editable:
            data[f.name] = f.value_from_object(instance)

    funcs = set(__fields) - set(list(data.keys()))
    for func in funcs:
        obj = getattr(instance, func)
        if inspect.ismethod(obj):
            data[func] = obj()
        else:
            data[func] = obj
    return data


def edges_from_nodes_queryset(nodes_queryset):
    """Given an Edge Model and a QuerySet or RawQuerySet of nodes, returns a queryset of the associated edges."""
    _NodeModel, _EdgeModel, queryset_type = get_queryset_characteristics(nodes_queryset)

    if queryset_type == "nodes_queryset":
        return _ordered_filter(_EdgeModel.objects, ["parent", "child"], nodes_queryset)
    raise IncorrectQuerysetTypeException


def nodes_from_edges_queryset(edges_queryset):
    """Given a Node Model and a QuerySet or RawQuerySet of edges, returns a queryset of the associated nodes."""
    _NodeModel, _EdgeModel, queryset_type = get_queryset_characteristics(edges_queryset)

    if queryset_type == "edges_queryset":
        parent_pks = edges_queryset.values_list("parent_id", flat=True)
        child_pks = edges_queryset.values_list("child_id", flat=True)
        all_pks = set(parent_pks) | set(child_pks)
        return _NodeModel.objects.filter(pk__in=all_pks)
    raise IncorrectQuerysetTypeException
