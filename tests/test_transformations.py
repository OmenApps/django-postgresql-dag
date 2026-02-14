import json
import uuid
from unittest.mock import patch

from django.test import TestCase

from django_postgresql_dag.exceptions import (
    GraphModelsCannotBeParsedException,
    IncorrectQuerysetTypeException,
    IncorrectUsageException,
)
from django_postgresql_dag.transformations import HAS_NETWORKX, HAS_RUSTWORKX, nx_from_queryset
from django_postgresql_dag.utils import (
    edges_from_nodes_queryset,
    get_instance_characteristics,
    get_queryset_characteristics,
    model_to_dict,
    nodes_from_edges_queryset,
)
from tests.helpers import DAGFixtureMixin
from tests.testapp.models import EdgeSet, FieldTestModel, NetworkEdge, NetworkNode


class NetworkXExportFromDAGTestCase(TestCase):
    """Test NX export with the post-removal state from the original test_basic_dag."""

    def setUp(self):
        if not HAS_NETWORKX:
            self.skipTest("networkx not installed")
        self.root = NetworkNode.objects.create(name="root")
        self.a3 = NetworkNode.objects.create(name="a3")
        self.b4 = NetworkNode.objects.create(name="b4")
        self.c1 = NetworkNode.objects.create(name="c1")

        self.root.add_child(self.a3)
        self.a3.add_child(self.b4)
        self.b4.add_child(self.c1)

    def test_nx_export_with_attributes(self):
        nx_out = nx_from_queryset(
            self.c1.ancestors_and_self(),
            graph_attributes_dict={"test": "test"},
            node_attribute_fields_list=["id", "name"],
            edge_attribute_fields_list=["id", "name"],
        )
        self.assertEqual(nx_out.graph, {"test": "test"})
        self.assertEqual(nx_out.nodes[self.root.pk], {"id": self.root.pk, "name": "root"})
        self.assertEqual(
            nx_out.edges[self.root.pk, self.a3.pk],
            {"id": NetworkEdge.objects.get(parent=self.root, child=self.a3).pk, "name": "root a3"},
        )


class TransformationsTestCase(DAGFixtureMixin, TestCase):
    def setUp(self):
        if not HAS_NETWORKX:
            self.skipTest("networkx not installed")
        super().setUp()

    def test_import_guard_raises(self):
        """Raises ImportError with helpful message when networkx unavailable."""
        from django_postgresql_dag import transformations

        with patch.object(transformations, "nx", None):
            with self.assertRaises(ImportError) as ctx:
                transformations.nx_from_queryset(self.root.clan())
            self.assertIn("pip install", str(ctx.exception))

    def test_nx_from_queryset_digraph(self):
        import networkx as nx

        graph = nx_from_queryset(self.root.clan(), digraph=True)
        self.assertIsInstance(graph, nx.DiGraph)
        self.assertIn(self.root.pk, graph.nodes)

    def test_nx_from_queryset_undirected(self):
        import networkx as nx

        graph = nx_from_queryset(self.root.clan())
        self.assertIsInstance(graph, nx.Graph)
        self.assertNotIsInstance(graph, nx.DiGraph)

    def test_nx_from_queryset_with_attributes(self):
        graph = nx_from_queryset(
            self.root.clan(),
            graph_attributes_dict={"name": "test"},
            node_attribute_fields_list=["name"],
            edge_attribute_fields_list=["name"],
        )
        self.assertEqual(graph.graph["name"], "test")
        self.assertEqual(graph.nodes[self.root.pk]["name"], "root")


class UtilsTestCase(TestCase):
    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")
        self.n2 = NetworkNode.objects.create(name="n2")
        self.n1.add_child(self.n2)

    def test_get_instance_characteristics_node(self):
        node_model, edge_model, instance_type = get_instance_characteristics(self.n1)
        self.assertEqual(node_model, NetworkNode)
        self.assertEqual(edge_model, NetworkEdge)
        self.assertEqual(instance_type, "node")

    def test_get_instance_characteristics_edge(self):
        edge = NetworkEdge.objects.first()
        node_model, edge_model, instance_type = get_instance_characteristics(edge)
        self.assertEqual(node_model, NetworkNode)
        self.assertEqual(edge_model, NetworkEdge)
        self.assertEqual(instance_type, "edge")

    def test_get_instance_characteristics_error(self):
        with self.assertRaises(GraphModelsCannotBeParsedException):
            get_instance_characteristics(EdgeSet.objects.create(name="x"))

    def test_get_queryset_characteristics_nodes(self):
        node_model, edge_model, qs_type = get_queryset_characteristics(NetworkNode.objects.all())
        self.assertEqual(qs_type, "nodes_queryset")

    def test_get_queryset_characteristics_edges(self):
        node_model, edge_model, qs_type = get_queryset_characteristics(NetworkEdge.objects.all())
        self.assertEqual(qs_type, "edges_queryset")

    def test_get_queryset_characteristics_error(self):
        with self.assertRaises(GraphModelsCannotBeParsedException):
            get_queryset_characteristics(EdgeSet.objects.all())

    def test_edges_from_nodes_queryset(self):
        nodes_qs = NetworkNode.objects.all()
        edges = edges_from_nodes_queryset(nodes_qs)
        self.assertTrue(edges.exists())

    def test_edges_from_nodes_queryset_wrong_type(self):
        with self.assertRaises(IncorrectQuerysetTypeException):
            edges_from_nodes_queryset(NetworkEdge.objects.all())

    def test_nodes_from_edges_queryset(self):
        edges_qs = NetworkEdge.objects.all()
        nodes = nodes_from_edges_queryset(edges_qs)
        self.assertIn(self.n1, nodes)
        self.assertIn(self.n2, nodes)

    def test_nodes_from_edges_queryset_wrong_type(self):
        with self.assertRaises(IncorrectQuerysetTypeException):
            nodes_from_edges_queryset(NetworkNode.objects.all())


class ModelToDictTestCase(TestCase):
    def setUp(self):
        self.n1 = NetworkNode.objects.create(name="n1")

    def test_model_to_dict_basic(self):
        result = model_to_dict(self.n1, fields=["id", "name"])
        self.assertEqual(result["name"], "n1")
        self.assertEqual(result["id"], self.n1.pk)

    def test_model_to_dict_no_fields_raises(self):
        with self.assertRaises(IncorrectUsageException):
            model_to_dict(self.n1)

    def test_model_to_dict_editable_field(self):
        """Test model_to_dict with editable fields (edge_set_id)"""
        result = model_to_dict(self.n1, fields=["name", "edge_set"])
        self.assertEqual(result["name"], "n1")

    def test_model_to_dict_method_field(self):
        """Fields that are methods on the model should be called"""
        result = model_to_dict(self.n1, fields=["is_root", "name"])
        self.assertIn("is_root", result)

    def test_model_to_dict_m2m_field(self):
        """M2M fields should return list of PKs"""
        n2 = NetworkNode.objects.create(name="n2_m2m")
        self.n1.add_child(n2)
        result = model_to_dict(self.n1, fields=["children"])
        self.assertIn(n2.pk, result["children"])

    def test_model_to_dict_m2m_subfield(self):
        """M2M fields with __ subfield lookup should use that field"""
        n2 = NetworkNode.objects.create(name="n2_sub")
        self.n1.add_child(n2)
        result = model_to_dict(self.n1, fields=["children__name"])
        self.assertIn("n2_sub", result["children"])

    def test_model_to_dict_m2m_unsaved_instance(self):
        """M2M on unsaved instance returns empty list"""
        unsaved = NetworkNode(name="unsaved")
        result = model_to_dict(unsaved, fields=["children"])
        self.assertEqual(result["children"], [])

    def test_model_to_dict_attribute_field(self):
        """Fields that are attributes should be returned"""
        result = model_to_dict(self.n1, fields=["pk"])
        self.assertEqual(result["pk"], self.n1.pk)


class ModelToDictFieldTypesTestCase(TestCase):
    """Tests for model_to_dict field-type branches using FieldTestModel."""

    def setUp(self):
        self.obj = FieldTestModel.objects.create(name="test_obj")

    def test_datetime_field_timestamp(self):
        """DateTimeField without date_strf returns dt.timestamp()."""
        result = model_to_dict(self.obj, fields=["created_at"])
        self.assertIsInstance(result["created_at"], float)

    def test_datetime_field_formatted(self):
        """DateTimeField with date_strf returns formatted string."""
        result = model_to_dict(self.obj, fields=["created_at"], date_strf="%Y-%m-%d")
        self.assertRegex(result["created_at"], r"^\d{4}-\d{2}-\d{2}$")

    def test_uuid_field_with_value(self):
        """UUIDField with a value returns str(uuid)."""
        test_uuid = uuid.uuid4()
        self.obj.uuid_field = test_uuid
        self.obj.save()
        self.obj.refresh_from_db()
        result = model_to_dict(self.obj, fields=["uuid_field"])
        self.assertEqual(result["uuid_field"], str(test_uuid))

    def test_uuid_field_none(self):
        """UUIDField with None returns None."""
        result = model_to_dict(self.obj, fields=["uuid_field"])
        self.assertIsNone(result["uuid_field"])

    def test_nullable_datetime_field_none(self):
        """DateTimeField with null=True and no value returns None."""
        result = model_to_dict(self.obj, fields=["nullable_dt"])
        self.assertIsNone(result["nullable_dt"])

    def test_file_field_none(self):
        """FileField with no file returns None."""
        result = model_to_dict(self.obj, fields=["file_field"])
        self.assertIn("file_field", result)
        self.assertIsNone(result["file_field"])

    def test_image_field_none(self):
        """ImageField with no image returns None."""
        result = model_to_dict(self.obj, fields=["image_field"])
        self.assertIn("image_field", result)
        self.assertIsNone(result["image_field"])


class ModelToDictM2MBranchesTestCase(DAGFixtureMixin, TestCase):
    """Tests for model_to_dict M2M branches that require mocking."""

    def test_m2m_cached_queryset(self):
        """M2M value_from_object returning an evaluated queryset (has _result_cache)."""
        qs = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.a2.pk])
        list(qs)  # Force evaluation to populate _result_cache
        with patch.object(
            type(NetworkNode._meta.get_field("children")),
            "value_from_object",
            return_value=qs,
        ):
            result = model_to_dict(self.root, fields=["children"])
        self.assertEqual(set(result["children"]), {self.a1.pk, self.a2.pk})

    def test_m2m_uncached_queryset_plain(self):
        """M2M value_from_object returning an unevaluated queryset, plain field."""
        qs = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.a2.pk])
        with patch.object(
            type(NetworkNode._meta.get_field("children")),
            "value_from_object",
            return_value=qs,
        ):
            result = model_to_dict(self.root, fields=["children"])
        self.assertEqual(set(result["children"]), {self.a1.pk, self.a2.pk})

    def test_m2m_uncached_queryset_subfield(self):
        """M2M value_from_object returning an unevaluated queryset, with subfield."""
        qs = NetworkNode.objects.filter(pk__in=[self.a1.pk, self.a2.pk])
        with patch.object(
            type(NetworkNode._meta.get_field("children")),
            "value_from_object",
            return_value=qs,
        ):
            result = model_to_dict(self.root, fields=["children__name"])
        self.assertEqual(set(result["children"]), {"a1", "a2"})


class RustworkXExportTestCase(DAGFixtureMixin, TestCase):
    """Tests for rx_from_queryset()."""

    def setUp(self):
        if not HAS_RUSTWORKX:
            self.skipTest("rustworkx not installed")
        super().setUp()

    def test_import_guard_raises(self):
        """Raises ImportError with helpful message when rustworkx unavailable."""
        from django_postgresql_dag import transformations

        with patch.object(transformations, "rx", None):
            with self.assertRaises(ImportError) as ctx:
                transformations.rx_from_queryset(self.root.clan())
            self.assertIn("pip install", str(ctx.exception))

    def test_creates_pydigraph(self):
        import rustworkx as rx

        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan(), digraph=True)
        self.assertIsInstance(graph, rx.PyDiGraph)

    def test_creates_pygraph_by_default(self):
        import rustworkx as rx

        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan())
        self.assertIsInstance(graph, rx.PyGraph)
        self.assertNotIsInstance(graph, rx.PyDiGraph)

    def test_node_attributes_populated(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan(), node_attribute_fields_list=["name"])
        node_names = {graph[idx]["name"] for idx in graph.node_indices()}
        self.assertIn("root", node_names)
        self.assertIn("a1", node_names)

    def test_edge_attributes_populated(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan(), edge_attribute_fields_list=["name"], digraph=True)
        edge_data_list = [graph.get_edge_data(src, tgt) for src, tgt in graph.edge_list()]
        edge_names = {d["name"] for d in edge_data_list}
        self.assertTrue(len(edge_names) > 0)

    def test_graph_attributes_stored(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        attrs = {"name": "test_graph", "version": 1}
        graph = rx_from_queryset(self.root.clan(), graph_attributes=attrs)
        self.assertEqual(graph.attrs, attrs)

    def test_works_with_edges_queryset(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        edges_qs = NetworkEdge.objects.filter(
            parent__in=self.root.clan(),
            child__in=self.root.clan(),
        )
        graph = rx_from_queryset(edges_qs, digraph=True)
        self.assertTrue(graph.num_nodes() > 0)
        self.assertTrue(graph.num_edges() > 0)

    def test_pk_always_present(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan())
        for idx in graph.node_indices():
            self.assertIn("pk", graph[idx])

    def test_pk_present_with_attributes(self):
        from django_postgresql_dag.transformations import rx_from_queryset

        graph = rx_from_queryset(self.root.clan(), node_attribute_fields_list=["name"])
        for idx in graph.node_indices():
            data = graph[idx]
            self.assertIn("pk", data)
            self.assertIn("name", data)


class JsonFromQuerysetTestCase(DAGFixtureMixin, TestCase):
    """Tests for json_from_queryset()."""

    def setUp(self):
        if not HAS_RUSTWORKX:
            self.skipTest("rustworkx not installed")
        super().setUp()

    def test_import_guard_raises(self):
        from django_postgresql_dag import transformations

        with patch.object(transformations, "rx", None):
            with self.assertRaises(ImportError) as ctx:
                transformations.json_from_queryset(self.root.clan())
            self.assertIn("pip install", str(ctx.exception))

    def test_returns_valid_json(self):
        from django_postgresql_dag.transformations import json_from_queryset

        result = json_from_queryset(self.root.clan())
        parsed = json.loads(result)
        self.assertIsInstance(parsed, dict)

    def test_json_contains_nodes_and_links(self):
        from django_postgresql_dag.transformations import json_from_queryset

        parsed = json.loads(json_from_queryset(self.root.clan()))
        self.assertIn("nodes", parsed)
        self.assertIn("links", parsed)
        self.assertTrue(len(parsed["nodes"]) > 0)
        self.assertTrue(len(parsed["links"]) > 0)

    def test_attributes_in_json(self):
        from django_postgresql_dag.transformations import json_from_queryset

        result = json_from_queryset(
            self.root.clan(),
            graph_attributes={"name": "test"},
            node_attribute_fields_list=["name"],
        )
        parsed = json.loads(result)
        self.assertEqual(parsed["attrs"]["name"], "test")
        node_names = {n["data"].get("name") for n in parsed["nodes"]}
        self.assertIn("root", node_names)

    def test_undirected_json_by_default(self):
        from django_postgresql_dag.transformations import json_from_queryset

        parsed = json.loads(json_from_queryset(self.root.clan()))
        self.assertFalse(parsed.get("directed", True))

    def test_directed_json(self):
        from django_postgresql_dag.transformations import json_from_queryset

        parsed = json.loads(json_from_queryset(self.root.clan(), digraph=True))
        self.assertTrue(parsed.get("directed", False))

    def test_date_strf_passthrough(self):
        from django_postgresql_dag.transformations import json_from_queryset

        result = json_from_queryset(self.root.clan(), node_attribute_fields_list=["name"], date_strf="%Y-%m-%d")
        parsed = json.loads(result)
        self.assertTrue(len(parsed["nodes"]) > 0)
