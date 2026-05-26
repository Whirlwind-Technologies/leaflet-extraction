"""
Extraction Module.

This module provides VLM-based product extraction from leaflet pages
using various vision-language models (Anthropic Claude, OpenAI GPT-4V,
Google Gemini, Azure OpenAI, AWS Bedrock).
"""

from app.core.extraction.vlm_extractor import VLMExtractor
from app.core.extraction.vlm_extractor_service import VLMExtractorService, UserAwareVLMExtractor
from app.core.extraction.prompt_builder import PromptBuilder
from app.core.extraction.reconciliation import (
    ProductReconciler,
    ReconciliationResult,
    reconcile_page_results,
)
from app.core.extraction.schemas import (
    ExtractionResult,
    ExtractedProduct,
    PageExtractionResult,
    ExtractionContext,
    BoundingBox,
    FieldConfidence,
)
from app.core.extraction.multi_provider_client import (
    MultiProviderVLMClient,
    AnthropicClient,
    OpenAIClient,
    GoogleClient,
    AzureOpenAIClient,
    AWSBedrockClient,
    VLMClientError,
    APIError,
    ProviderNotSupportedError,
    BudgetExceededError,
    get_vlm_client_for_user,
)

__all__ = [
    # Main extractor (legacy - uses Anthropic directly)
    "VLMExtractor",
    # VLM Extractor Service (uses org/platform provider settings)
    "VLMExtractorService",
    # Legacy alias for backward compatibility
    "UserAwareVLMExtractor",
    # Multi-provider client
    "MultiProviderVLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "GoogleClient",
    "AzureOpenAIClient",
    "AWSBedrockClient",
    "VLMClientError",
    "APIError",
    "ProviderNotSupportedError",
    "BudgetExceededError",
    "get_vlm_client_for_user",
    # Prompt building
    "PromptBuilder",
    # Reconciliation
    "ProductReconciler",
    "ReconciliationResult",
    "reconcile_page_results",
    # Schemas
    "ExtractionResult",
    "ExtractedProduct",
    "PageExtractionResult",
    "ExtractionContext",
    "BoundingBox",
    "FieldConfidence",
]