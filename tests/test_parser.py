"""Tests for ContextBrain API endpoints."""

import pytest
import json
import os

# Test the OpenAPI parser (no DB needed)
from src.utils.openapi_parser import parse_openapi_spec, generate_api_summary


SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_specs")


class TestOpenAPIParser:
    """Test the OpenAPI spec parser."""

    def _load_spec(self, filename: str) -> dict:
        with open(os.path.join(SAMPLE_DIR, filename)) as f:
            return json.load(f)

    def test_parse_eligibility_api(self):
        spec = self._load_spec("member_eligibility_api.json")
        parsed = parse_openapi_spec(spec)

        assert parsed["name"] == "Member Eligibility API"
        assert parsed["version"] == "3.2.0"
        assert parsed["auth_mechanism"] == "HTTP Bearer"
        assert len(parsed["endpoints"]) == 3

    def test_parse_claims_api(self):
        spec = self._load_spec("claims_processing_api.json")
        parsed = parse_openapi_spec(spec)

        assert parsed["name"] == "Claims Processing API"
        assert parsed["auth_mechanism"] == "OAuth2"
        assert len(parsed["endpoints"]) == 3

    def test_parse_provider_api(self):
        spec = self._load_spec("provider_network_api.json")
        parsed = parse_openapi_spec(spec)

        assert parsed["name"] == "Provider Network API"
        assert parsed["auth_mechanism"] == "API Key (header)"
        assert len(parsed["endpoints"]) == 3

    def test_parse_prior_auth_api(self):
        spec = self._load_spec("prior_authorization_api.json")
        parsed = parse_openapi_spec(spec)

        assert parsed["name"] == "Prior Authorization API"
        assert len(parsed["endpoints"]) == 4

    def test_endpoints_have_methods_and_paths(self):
        spec = self._load_spec("member_eligibility_api.json")
        parsed = parse_openapi_spec(spec)

        for ep in parsed["endpoints"]:
            assert ep["method"] in ("GET", "POST", "PUT", "PATCH", "DELETE")
            assert ep["path"].startswith("/")
            assert ep["summary"]

    def test_generate_summary(self):
        spec = self._load_spec("member_eligibility_api.json")
        parsed = parse_openapi_spec(spec)
        summary = generate_api_summary(parsed)

        assert "Member Eligibility API" in summary
        assert "Endpoints:" in summary
        assert "GET" in summary

    def test_request_body_extracted(self):
        spec = self._load_spec("claims_processing_api.json")
        parsed = parse_openapi_spec(spec)

        # Find the POST /claims endpoint
        post_endpoint = next(
            ep for ep in parsed["endpoints"]
            if ep["method"] == "POST" and ep["path"] == "/claims"
        )
        assert post_endpoint["request_schema"] is not None
        assert "properties" in post_endpoint["request_schema"]

    def test_parameters_extracted(self):
        spec = self._load_spec("provider_network_api.json")
        parsed = parse_openapi_spec(spec)

        # Find the search endpoint
        search_endpoint = next(
            ep for ep in parsed["endpoints"]
            if ep["path"] == "/providers/search"
        )
        assert len(search_endpoint["parameters"]) > 0
        param_names = [p["name"] for p in search_endpoint["parameters"]]
        assert "specialty" in param_names
        assert "zipCode" in param_names
