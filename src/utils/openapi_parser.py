"""Utility to parse OpenAPI/Swagger specs into structured API + endpoint data."""

from typing import Any


def parse_openapi_spec(spec: dict) -> dict[str, Any]:
    """
    Parse an OpenAPI 3.x or Swagger 2.x spec into a normalized structure.

    Returns:
        {
            "name": str,
            "version": str,
            "description": str,
            "base_url": str,
            "auth_mechanism": str | None,
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/v1/members/{id}",
                    "summary": "...",
                    "parameters": [...],
                    "request_schema": {...},
                    "response_schema": {...}
                }
            ]
        }
    """
    info = spec.get("info", {})
    is_openapi3 = spec.get("openapi", "").startswith("3")

    # Extract base URL
    base_url = _extract_base_url(spec, is_openapi3)

    # Extract auth mechanism
    auth = _extract_auth_mechanism(spec, is_openapi3)

    # Extract all endpoints
    endpoints = _extract_endpoints(spec, is_openapi3)

    return {
        "name": info.get("title", "Untitled API"),
        "version": info.get("version", "1.0.0"),
        "description": info.get("description", ""),
        "base_url": base_url,
        "auth_mechanism": auth,
        "endpoints": endpoints,
    }


def _extract_base_url(spec: dict, is_openapi3: bool) -> str:
    """Extract base URL from spec."""
    if is_openapi3:
        servers = spec.get("servers", [])
        if servers:
            return servers[0].get("url", "")
    else:
        # Swagger 2.x
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        schemes = spec.get("schemes", ["https"])
        if host:
            return f"{schemes[0]}://{host}{base_path}"
    return ""


def _extract_auth_mechanism(spec: dict, is_openapi3: bool) -> str | None:
    """Determine the primary auth mechanism from the spec."""
    if is_openapi3:
        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
    else:
        security_schemes = spec.get("securityDefinitions", {})

    if not security_schemes:
        return None

    # Return the first/primary auth type
    for name, scheme in security_schemes.items():
        scheme_type = scheme.get("type", "")
        if scheme_type == "oauth2":
            return "OAuth2"
        elif scheme_type == "apiKey":
            return f"API Key ({scheme.get('in', 'header')})"
        elif scheme_type == "http":
            return f"HTTP {scheme.get('scheme', 'bearer').title()}"
        elif scheme_type == "openIdConnect":
            return "OpenID Connect"

    return None


def _extract_endpoints(spec: dict, is_openapi3: bool) -> list[dict]:
    """Extract all endpoints from the spec."""
    endpoints = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if method not in path_item:
                continue

            operation = path_item[method]
            endpoint = {
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary", "")
                    or operation.get("description", "")
                    or f"{method.upper()} {path}",
                "parameters": _extract_parameters(operation, path_item, is_openapi3),
                "request_schema": _extract_request_body(operation, is_openapi3),
                "response_schema": _extract_response_schema(operation, is_openapi3),
            }
            endpoints.append(endpoint)

    return endpoints


def _extract_parameters(operation: dict, path_item: dict, is_openapi3: bool) -> list[dict]:
    """Extract parameters (path, query, header) for an endpoint."""
    params = []
    # Path-level + operation-level parameters
    all_params = (path_item.get("parameters", []) or []) + (operation.get("parameters", []) or [])

    for param in all_params:
        params.append({
            "name": param.get("name", ""),
            "in": param.get("in", ""),
            "required": param.get("required", False),
            "description": param.get("description", ""),
            "schema": param.get("schema", {}),
        })

    return params


def _extract_request_body(operation: dict, is_openapi3: bool) -> dict | None:
    """Extract request body schema."""
    if is_openapi3:
        request_body = operation.get("requestBody", {})
        if not request_body:
            return None
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        return json_content.get("schema")
    else:
        # Swagger 2.x — body parameter
        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                return param.get("schema")
    return None


def _extract_response_schema(operation: dict, is_openapi3: bool) -> dict | None:
    """Extract the primary success response schema."""
    responses = operation.get("responses", {})
    # Look for 200 or 201 response
    for code in ("200", "201", 200, 201):
        if str(code) in responses or code in responses:
            response = responses.get(str(code)) or responses.get(code, {})
            if is_openapi3:
                content = response.get("content", {})
                json_content = content.get("application/json", {})
                return json_content.get("schema")
            else:
                return response.get("schema")
    return None


def generate_api_summary(parsed: dict) -> str:
    """Generate a human-readable summary of a parsed API for embedding."""
    lines = [
        f"API: {parsed['name']} (v{parsed['version']})",
        f"Description: {parsed['description']}" if parsed["description"] else "",
        f"Base URL: {parsed['base_url']}" if parsed["base_url"] else "",
        f"Auth: {parsed['auth_mechanism']}" if parsed["auth_mechanism"] else "",
        "",
        "Endpoints:",
    ]

    for ep in parsed["endpoints"]:
        lines.append(f"  {ep['method']} {ep['path']} — {ep['summary']}")

    return "\n".join(line for line in lines if line is not None)
