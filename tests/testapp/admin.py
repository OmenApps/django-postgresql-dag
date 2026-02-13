from django.contrib import admin

from .models import *  # noqa: F401, F403


@admin.register(EdgeSet)
class EdgeSetAdmin(admin.ModelAdmin):
    pass


@admin.register(NodeSet)
class NodeSetAdmin(admin.ModelAdmin):
    pass


@admin.register(NetworkEdge)
class NetworkEdgeAdmin(admin.ModelAdmin):
    pass


@admin.register(NetworkNode)
class NetworkNodeAdmin(admin.ModelAdmin):
    pass
