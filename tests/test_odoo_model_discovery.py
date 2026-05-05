from odoo_model_discovery import (
    build_doc_url,
    build_fields_get_request,
    build_ir_model_fields_request,
    build_ir_model_request,
    describe_discovery_steps,
    validate_required_fields,
)


def test_build_doc_url():
    assert build_doc_url("https://sandbox.example.test/") == "https://sandbox.example.test/doc"


def test_build_fields_get_request_shape():
    request = build_fields_get_request("project.task")

    assert request.path == "/json/2/project.task/fields_get"
    assert request.body()["attributes"] == [
        "string",
        "type",
        "required",
        "readonly",
        "relation",
    ]


def test_build_ir_model_metadata_request_shapes():
    model_request = build_ir_model_request("project.task")
    fields_request = build_ir_model_fields_request("project.task")

    assert model_request.path == "/json/2/ir.model/search_read"
    assert model_request.body()["domain"] == [["model", "=", "project.task"]]
    assert fields_request.path == "/json/2/ir.model.fields/search_read"
    assert fields_request.body()["domain"] == [["model", "=", "project.task"]]


def test_validate_required_fields_reports_missing_fields():
    result = validate_required_fields(
        {"name": {"type": "char"}, "description": {"type": "html"}},
        ["name", "project_id"],
    )

    assert result["verified"] is False
    assert result["missing_fields"] == ["project_id"]
    assert result["available_fields"] == ["description", "name"]


def test_validate_required_fields_passes_when_fields_exist():
    result = validate_required_fields({"name": {}, "project_id": {}}, ["name"])

    assert result["verified"] is True
    assert result["missing_fields"] == []


def test_discovery_steps_are_read_only_guidance():
    steps = describe_discovery_steps("https://sandbox.example.test", "project.task")

    assert any("/doc" in step for step in steps)
    assert any("fields_get" in step for step in steps)
    assert all("create" not in step.lower() for step in steps)
