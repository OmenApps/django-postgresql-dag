from django.db import models

from django_postgresql_dag.models import edge_factory, node_factory


class EdgeSet(models.Model):
    """A model designed as a container for a set of edges."""

    name = models.CharField(max_length=100)


class NodeSet(models.Model):
    """A model designed as a container for a set of nodes."""

    name = models.CharField(max_length=100)


class NetworkEdge(edge_factory("NetworkNode", concrete=False)):
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)

    edge_set = models.ForeignKey(EdgeSet, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = f"{self.parent.name} {self.child.name}"
        super().save(*args, **kwargs)

    class Meta:
        app_label = "testapp"


class FieldTestModel(models.Model):
    """Model for testing model_to_dict with various field types."""

    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    uuid_field = models.UUIDField(null=True, blank=True)
    nullable_dt = models.DateTimeField(null=True, blank=True)
    file_field = models.FileField(upload_to="test/", null=True, blank=True)
    image_field = models.ImageField(upload_to="test_images/", null=True, blank=True)

    class Meta:
        app_label = "testapp"


class NetworkNode(node_factory(NetworkEdge)):
    name = models.CharField(max_length=100)

    edge_set = models.ForeignKey(EdgeSet, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "testapp"
