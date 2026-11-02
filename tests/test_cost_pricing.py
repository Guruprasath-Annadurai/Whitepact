"""Tests for the model pricing catalog (cost/models.py) — in particular
the Azure OpenAI entries, since get_pricing()'s exact-match vs.
provider-fallback distinction matters more there than anywhere else in
the catalog (an Azure deployment is rarely named exactly "gpt-4o")."""

from __future__ import annotations

from responsibleai.cost.models import MODEL_CATALOG, get_pricing


class TestAzureOpenAIPricing:
    def test_exact_deployment_name_match(self):
        pricing = get_pricing("azure-openai", "gpt-4o")
        assert pricing.provider == "azure-openai"
        assert pricing.input_cost_per_million == 2.50
        assert pricing.output_cost_per_million == 10.00

    def test_mirrors_public_openai_pricing(self):
        azure = get_pricing("azure-openai", "gpt-4o")
        openai = get_pricing("openai", "gpt-4o")
        assert azure.input_cost_per_million == openai.input_cost_per_million
        assert azure.output_cost_per_million == openai.output_cost_per_million

    def test_unknown_deployment_name_falls_back_to_provider(self):
        # A real Azure customer names their own deployment (e.g. "prod-gpt4o")
        # -- this must not silently return $0 pricing for a real deployment.
        pricing = get_pricing("azure-openai", "prod-gpt4o-custom-deployment")
        assert pricing.provider == "azure-openai"
        assert pricing.input_cost_per_million > 0

    def test_cost_for_computes_a_real_number(self):
        pricing = get_pricing("azure-openai", "gpt-4o")
        cost = pricing.cost_for(input_tokens=2000, output_tokens=800)
        assert cost > 0

    def test_case_insensitive_lookup(self):
        pricing = get_pricing("Azure-OpenAI", "GPT-4o")
        assert pricing.provider == "azure-openai"


class TestCatalogIntegrity:
    def test_every_azure_openai_entry_has_an_openai_counterpart(self):
        # Not a hard requirement going forward, but true today and worth
        # catching if it silently stops being true (a rate divergence
        # someone forgot to intend).
        for key, pricing in MODEL_CATALOG.items():
            if not key.startswith("azure-openai/"):
                continue
            openai_key = key.replace("azure-openai/", "openai/", 1)
            assert openai_key in MODEL_CATALOG, f"{key} has no openai counterpart"
            counterpart = MODEL_CATALOG[openai_key]
            assert pricing.input_cost_per_million == counterpart.input_cost_per_million
            assert pricing.output_cost_per_million == counterpart.output_cost_per_million
