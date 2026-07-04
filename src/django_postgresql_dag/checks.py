"""Warning-level system check that surfaces edge models which silently did not
receive ``edge_factory``'s performance-improving composite indexes.

Adding ``indexes`` to the abstract Edge ``Meta`` only propagates to a concrete
child whose ``Meta`` subclasses the factory's (or that declares no ``Meta`` at
all). A child with its own non-subclassing ``Meta`` - or one whose ``Meta``
inherits from a different base (e.g. django-auto-prefetch) - silently drops the
indexes, with no error and no migration. This check turns that silent no-op into
an actionable ``Warning`` message.

The check is coverage-based: it only flags a model that actually lacks an index
covering ``(parent, child)`` or ``(child, parent)``. A model that already
declares its own equivalent indexes (under any name) is considered covered and
is not flagged.
"""

from django.apps import apps
from django.core.checks import Tags, Warning, register

# Class attribute stamped onto every model produced by ``edge_factory``. Its value
# is the tuple of index field-tuples the factory tries to provide. Concrete
# subclasses inherit it, which is how the check recognises an edge model.
DAG_EDGE_INDEX_FIELDS_ATTR = "_dag_edge_index_field_tuples"


def _existing_index_field_tuples(model):
    """Return the field-name tuples of every index declared on the model."""
    return [tuple(index.fields) for index in model._meta.indexes]


def _missing_index_field_tuples(model):
    """Return the required index field-tuples not covered by the model's indexes.

    A target tuple is covered when some declared index has it as a left-prefix, so
    ``(parent, child, x)`` covers ``(parent, child)``. Returns ``[]`` for anything
    that is not an edge-factory model.
    """
    required = getattr(model, DAG_EDGE_INDEX_FIELDS_ATTR, None)
    if not required:
        return []
    existing = _existing_index_field_tuples(model)
    missing = []
    for target in required:
        target = tuple(target)
        if not any(fields[: len(target)] == target for fields in existing):
            missing.append(target)
    return missing


def _is_checkable_edge_model(model):
    """Whether this model is a concrete edge model whose own table should carry the indexes."""
    if getattr(model, DAG_EDGE_INDEX_FIELDS_ATTR, None) is None:
        return False
    meta = model._meta
    if meta.abstract or meta.proxy:
        return False
    # Multi-table-inheritance child: the composite indexes live on the parent's
    # table, not this one, so checking this model would be a false positive.
    if any(getattr(parent, DAG_EDGE_INDEX_FIELDS_ATTR, None) is not None for parent in meta.get_parent_list()):
        return False
    return True


def _format_tuple(field_tuple):
    return "(" + ", ".join(field_tuple) + ")"


def _check_models(models):
    """Build the list of ``Warning`` messages for the given models. Pure - easy to unit test."""
    messages = []
    for model in models:
        if not _is_checkable_edge_model(model):
            continue
        missing = _missing_index_field_tuples(model)
        if not missing:
            continue
        missing_str = ", ".join(_format_tuple(field_tuple) for field_tuple in missing)
        messages.append(
            Warning(
                f"DAG edge model '{model._meta.label}' is missing the composite index(es) "
                f"{missing_str} that speed up ancestor/descendant traversals.",
                hint=(
                    "edge_factory declares these indexes on its abstract Edge Meta, but this model did "
                    "not inherit them because its Meta does not subclass the factory's (or inherits a "
                    "different base's Meta). Make its Meta subclass the factory Meta, e.g. "
                    "`class Meta(EdgeBase.Meta): ...`, or add models.Index(fields=['parent', 'child']) and "
                    "models.Index(fields=['child', 'parent']) to Meta.indexes, then run makemigrations. "
                    "See the Edge Reference 'Edge table indexes' section."
                ),
                obj=model,
                # Promoted from Info to Warning so a Meta override that silently drops the indexes is
                # noticed (a missing covering index only shows up as extra heap I/O per recursion level,
                # never a failure, so an Info was too quiet). The id keeps its historical "I001" so any
                # existing SILENCED_SYSTEM_CHECKS entry still silences it.
                id="django_postgresql_dag.I001",
            )
        )
    return messages


@register(Tags.models)
def check_dag_edge_indexes(app_configs=None, **kwargs):
    """System check: flag concrete edge models missing the composite indexes."""
    if app_configs is None:
        models = apps.get_models()
    else:
        models = [model for app_config in app_configs for model in app_config.get_models()]
    return _check_models(models)
