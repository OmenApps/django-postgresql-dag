from django.dispatch import Signal

pre_edge_create = Signal()
post_edge_create = Signal()
pre_edge_delete = Signal()
post_edge_delete = Signal()
