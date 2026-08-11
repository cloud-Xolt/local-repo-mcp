from __future__ import annotations

import asyncio
from types import SimpleNamespace

from mcp.server import MCPServer

from tools.contracts import EXPECTED_TOOL_NAMES, contract_problems, schema_value
from tools.patches import register_patch_tools
from tools.reads import register_read_tools
from tools.tests import register_test_tools


def _listed_tools():
    server = MCPServer("contract-test")
    context = SimpleNamespace(mcp=server)
    register_read_tools(context)  # type: ignore[arg-type]
    register_patch_tools(context)  # type: ignore[arg-type]
    register_test_tools(context)  # type: ignore[arg-type]
    return asyncio.run(server.list_tools())


def test_all_public_tools_have_concrete_input_and_output_contracts() -> None:
    tools = _listed_tools()
    assert {tool.name for tool in tools} == EXPECTED_TOOL_NAMES
    assert contract_problems(list(tools)) == []

    for tool in tools:
        input_schema = schema_value(tool, "input_schema", "inputSchema")
        output_schema = schema_value(tool, "output_schema", "outputSchema")
        assert input_schema["type"] == "object"
        assert output_schema["type"] == "object"
        assert isinstance(output_schema.get("properties"), dict)


def test_optional_collection_inputs_are_optional_without_null_union() -> None:
    tools = {tool.name: tool for tool in _listed_tools()}
    schema = schema_value(
        tools["repo_run_test"], "input_schema", "inputSchema"
    )
    command_keys = schema["properties"]["command_keys"]

    assert command_keys["type"] == "array"
    assert command_keys["items"]["type"] == "string"
    assert "anyOf" not in command_keys
    assert "command_keys" not in schema.get("required", [])


def test_verification_tool_publishes_useful_output_schema() -> None:
    tools = {tool.name: tool for tool in _listed_tools()}
    schema = schema_value(
        tools["repo_run_test"], "output_schema", "outputSchema"
    )
    properties = schema["properties"]

    assert {"status", "success", "repository", "duration_ms"} <= set(properties)
    assert properties["success"]["type"] == "boolean"
    repository_schema = properties["repository"]
    assert repository_schema.get("type") == "object" or "$ref" in repository_schema
