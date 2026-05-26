"""
Multi-Provider VLM Client Module.

This module provides a unified interface for multiple VLM providers
(Anthropic Claude, OpenAI GPT-4V, Google Gemini, Azure OpenAI, AWS Bedrock).

Supports both:
- Organization VLM Providers (VLMProvider) - user-configured
- Platform VLM Providers (PlatformVLMProvider) - admin-configured system fallback

Example Usage:
    from app.core.extraction.multi_provider_client import MultiProviderVLMClient
    from app.models.vlm_provider import VLMProvider

    client = MultiProviderVLMClient(provider)
    result = await client.extract_from_image(image_data, prompt)
"""

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Union, Protocol, runtime_checkable

from PIL import Image
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.models.vlm_provider import VLMProvider, VLMProviderType, DEFAULT_MODELS
from app.models.platform_vlm_provider import PlatformVLMProvider, PlatformVLMProviderType, PLATFORM_DEFAULT_MODELS


@runtime_checkable
class VLMProviderProtocol(Protocol):
    """Protocol for VLM provider interface - works with both VLMProvider and PlatformVLMProvider."""
    provider_type: Any
    model_name: str
    max_tokens: int
    temperature: float
    api_endpoint: Optional[str]
    config: Optional[dict]

    def get_api_key(self) -> str: ...
    def check_budget(self) -> bool: ...
    def record_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None: ...

logger = logging.getLogger(__name__)


def _openai_needs_max_completion_tokens(model_name: str) -> bool:
    """
    Check if an OpenAI model requires max_completion_tokens instead of max_tokens.

    Newer OpenAI models (o1, o3, o4, gpt-5+) use max_completion_tokens.
    Older models (gpt-4, gpt-4o, gpt-4-turbo, gpt-4.1) use max_tokens.
    """
    model_lower = model_name.lower()

    # o-series models (o1, o3, o4) always need max_completion_tokens
    if model_lower.startswith(('o1', 'o3', 'o4')):
        return True

    # GPT-5+ models need max_completion_tokens
    if model_lower.startswith('gpt-5') or model_lower.startswith('gpt-6'):
        return True

    # Default to max_tokens for older models (gpt-4, gpt-4o, gpt-4-turbo, gpt-4.1)
    return False


def _openai_requires_default_temperature(model_name: str) -> bool:
    """
    Check if an OpenAI model rejects non-default temperature values.

    Newer reasoning-tier models (o1, o3, o4, gpt-5+) only support the default
    temperature (1). Sending temperature=0 yields a 400 invalid_request_error.
    For these models we omit the temperature parameter so the API uses its default.
    """
    model_lower = model_name.lower()

    if model_lower.startswith(('o1', 'o3', 'o4')):
        return True

    if model_lower.startswith('gpt-5') or model_lower.startswith('gpt-6'):
        return True

    return False


class VLMClientError(Exception):
    """Base exception for VLM client errors."""
    pass


class APIError(VLMClientError):
    """Error from the VLM API."""
    pass


class ProviderNotSupportedError(VLMClientError):
    """Provider type is not supported."""
    pass


class BudgetExceededError(VLMClientError):
    """Monthly budget limit exceeded."""
    pass


class InsufficientCreditsError(VLMClientError):
    """API provider has insufficient credits/balance."""
    pass


class ExtractionResult:
    """Result from VLM extraction."""
    
    def __init__(
        self,
        content: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        cost: float,
        latency_ms: int,
    ):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.cost = cost
        self.latency_ms = latency_ms


class BaseVLMClient(ABC):
    """Abstract base class for VLM clients."""

    def __init__(self, provider: Union[VLMProvider, PlatformVLMProvider]):
        self.provider = provider
        self.api_key = provider.get_api_key()
        self.model = provider.model_name
        self.max_tokens = provider.max_tokens
        self.temperature = provider.temperature
        self.endpoint = getattr(provider, 'api_endpoint', None)
        self._is_platform_provider = isinstance(provider, PlatformVLMProvider)

    @abstractmethod
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        """Extract data from image using VLM."""
        pass

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        # Get the appropriate defaults based on provider type
        if self._is_platform_provider:
            defaults = PLATFORM_DEFAULT_MODELS.get(self.provider.provider_type, {})
        else:
            defaults = DEFAULT_MODELS.get(self.provider.provider_type, {})

        input_cost = defaults.get("input_cost_per_1m", 3.0)
        output_cost = defaults.get("output_cost_per_1m", 15.0)

        return (input_tokens * input_cost / 1_000_000) + (output_tokens * output_cost / 1_000_000)


class AnthropicClient(BaseVLMClient):
    """Anthropic Claude client."""
    
    def __init__(self, provider: VLMProvider):
        super().__init__(provider)
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
    )
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        import time
        start = time.time()
        
        # Ensure image is base64
        if isinstance(image_data, bytes):
            b64_data = base64.b64encode(image_data).decode()
        else:
            b64_data = image_data
        
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            
            latency = int((time.time() - start) * 1000)
            cost = self.calculate_cost(
                message.usage.input_tokens,
                message.usage.output_tokens
            )
            
            return ExtractionResult(
                content=message.content[0].text,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                model=message.model,
                cost=cost,
                latency_ms=latency,
            )
        except Exception as e:
            error_str = str(e)
            logger.error(f"Anthropic API error: {e}")
            
            # Detect specific billing/credit errors
            if "credit balance is too low" in error_str.lower():
                raise InsufficientCreditsError(
                    "Your Anthropic API credit balance is too low. "
                    "Please add credits at https://console.anthropic.com/settings/billing"
                )
            elif "rate limit" in error_str.lower():
                raise APIError(f"Rate limit exceeded. Please try again later.")
            elif "invalid_api_key" in error_str.lower() or "authentication" in error_str.lower():
                raise APIError(f"Invalid API key. Please check your Anthropic API key.")
            else:
                raise APIError(f"Anthropic API error: {error_str}")


class OpenAIClient(BaseVLMClient):
    """OpenAI GPT-4 Vision client."""
    
    def __init__(self, provider: VLMProvider):
        super().__init__(provider)
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        import time
        start = time.time()
        
        # Ensure image is base64
        if isinstance(image_data, bytes):
            b64_data = base64.b64encode(image_data).decode()
        else:
            b64_data = image_data
        
        try:
            # Newer OpenAI models (o1, o3, o4, gpt-5+) use max_completion_tokens
            token_param = (
                {"max_completion_tokens": self.max_tokens}
                if _openai_needs_max_completion_tokens(self.model)
                else {"max_tokens": self.max_tokens}
            )
            # Newer OpenAI models (o1, o3, o4, gpt-5+) only support default temperature
            temp_param = (
                {}
                if _openai_requires_default_temperature(self.model)
                else {"temperature": self.temperature}
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                **token_param,
                **temp_param,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64_data}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            
            latency = int((time.time() - start) * 1000)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = self.calculate_cost(input_tokens, output_tokens)
            
            return ExtractionResult(
                content=response.choices[0].message.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=response.model,
                cost=cost,
                latency_ms=latency,
            )
        except Exception as e:
            error_str = str(e)
            logger.error(f"OpenAI API error: {e}")
            
            # Detect specific billing/credit errors
            if "insufficient_quota" in error_str.lower() or "billing" in error_str.lower():
                raise InsufficientCreditsError(
                    "Your OpenAI API has insufficient quota. "
                    "Please check your billing at https://platform.openai.com/account/billing"
                )
            elif "rate limit" in error_str.lower():
                raise APIError(f"Rate limit exceeded. Please try again later.")
            elif "invalid_api_key" in error_str.lower() or "authentication" in error_str.lower():
                raise APIError(f"Invalid API key. Please check your OpenAI API key.")
            else:
                raise APIError(f"OpenAI API error: {error_str}")


class GoogleClient(BaseVLMClient):
    """Google Gemini client."""
    
    def __init__(self, provider: VLMProvider):
        super().__init__(provider)
        self._model = None
    
    @property
    def model_instance(self):
        if self._model is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError("google-generativeai package required")
        return self._model
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        import time
        start = time.time()
        
        try:
            # Convert to PIL Image
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data
            
            image = Image.open(BytesIO(image_bytes))
            
            # Generate content
            response = await asyncio.to_thread(
                self.model_instance.generate_content,
                [prompt, image],
                generation_config={
                    "max_output_tokens": self.max_tokens,
                    "temperature": self.temperature,
                }
            )
            
            latency = int((time.time() - start) * 1000)
            
            # Estimate tokens (Gemini doesn't always return token counts)
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 1000
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 500
            cost = self.calculate_cost(input_tokens, output_tokens)
            
            return ExtractionResult(
                content=response.text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model,
                cost=cost,
                latency_ms=latency,
            )
        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise APIError(f"Google API error: {str(e)}")


class AzureOpenAIClient(BaseVLMClient):
    """Azure OpenAI client."""
    
    def __init__(self, provider: VLMProvider):
        super().__init__(provider)
        self._client = None
        
        # Azure requires endpoint
        if not self.endpoint:
            raise ValueError("Azure OpenAI requires api_endpoint to be set")
    
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import AsyncAzureOpenAI
                self._client = AsyncAzureOpenAI(
                    api_key=self.api_key,
                    api_version="2024-02-15-preview",
                    azure_endpoint=self.endpoint,
                )
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        import time
        start = time.time()
        
        if isinstance(image_data, bytes):
            b64_data = base64.b64encode(image_data).decode()
        else:
            b64_data = image_data
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,  # This is the deployment name in Azure
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64_data}",
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            
            latency = int((time.time() - start) * 1000)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = self.calculate_cost(input_tokens, output_tokens)
            
            return ExtractionResult(
                content=response.choices[0].message.content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=response.model,
                cost=cost,
                latency_ms=latency,
            )
        except Exception as e:
            logger.error(f"Azure OpenAI API error: {e}")
            raise APIError(f"Azure OpenAI API error: {str(e)}")


class AWSBedrockClient(BaseVLMClient):
    """AWS Bedrock client for Claude models."""
    
    def __init__(self, provider: VLMProvider):
        super().__init__(provider)
        self._client = None
        
        # Get AWS credentials from config if available
        self.config = provider.config or {}
        self.region = self.config.get("aws_region", "us-east-1")
    
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region,
                    aws_access_key_id=self.config.get("aws_access_key_id"),
                    aws_secret_access_key=self.config.get("aws_secret_access_key"),
                )
            except ImportError:
                raise ImportError("boto3 package required: pip install boto3")
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def extract(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        import time
        start = time.time()
        
        if isinstance(image_data, bytes):
            b64_data = base64.b64encode(image_data).decode()
        else:
            b64_data = image_data
        
        try:
            # Bedrock uses Anthropic's message format for Claude
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            }
            
            response = await asyncio.to_thread(
                self.client.invoke_model,
                modelId=self.model,
                body=json.dumps(body),
            )
            
            result = json.loads(response["body"].read())
            
            latency = int((time.time() - start) * 1000)
            input_tokens = result.get("usage", {}).get("input_tokens", 0)
            output_tokens = result.get("usage", {}).get("output_tokens", 0)
            cost = self.calculate_cost(input_tokens, output_tokens)
            
            return ExtractionResult(
                content=result["content"][0]["text"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self.model,
                cost=cost,
                latency_ms=latency,
            )
        except Exception as e:
            logger.error(f"AWS Bedrock API error: {e}")
            raise APIError(f"AWS Bedrock API error: {str(e)}")


class MultiProviderVLMClient:
    """
    Unified interface for multiple VLM providers.

    Handles provider selection, budget checking, and usage tracking.
    Supports both organization-level (VLMProvider) and platform-level (PlatformVLMProvider).

    Example:
        >>> provider = get_user_default_provider(user)
        >>> client = MultiProviderVLMClient(provider)
        >>> result = await client.extract_from_image(image_bytes, prompt)
        >>> print(f"Cost: ${result.cost:.4f}")
    """

    # Client class mapping for organization VLM providers
    ORG_CLIENTS = {
        VLMProviderType.ANTHROPIC: AnthropicClient,
        VLMProviderType.OPENAI: OpenAIClient,
        VLMProviderType.GOOGLE: GoogleClient,
        VLMProviderType.AZURE_OPENAI: AzureOpenAIClient,
        VLMProviderType.AWS_BEDROCK: AWSBedrockClient,
    }

    # Client class mapping for platform VLM providers
    PLATFORM_CLIENTS = {
        PlatformVLMProviderType.ANTHROPIC: AnthropicClient,
        PlatformVLMProviderType.OPENAI: OpenAIClient,
        PlatformVLMProviderType.GOOGLE: GoogleClient,
        PlatformVLMProviderType.AZURE_OPENAI: AzureOpenAIClient,
        PlatformVLMProviderType.AWS_BEDROCK: AWSBedrockClient,
    }

    # Legacy alias for backwards compatibility
    CLIENTS = ORG_CLIENTS

    def __init__(self, provider: Union[VLMProvider, PlatformVLMProvider]):
        """
        Initialize with a VLM provider configuration.

        Args:
            provider: VLM provider database model (VLMProvider or PlatformVLMProvider)

        Raises:
            ProviderNotSupportedError: If provider type not supported
            BudgetExceededError: If budget exceeded
        """
        self.provider = provider
        self._is_platform_provider = isinstance(provider, PlatformVLMProvider)

        # Select appropriate client mapping
        if self._is_platform_provider:
            clients = self.PLATFORM_CLIENTS
            provider_type_name = provider.provider_type.value if hasattr(provider.provider_type, 'value') else str(provider.provider_type)
        else:
            clients = self.ORG_CLIENTS
            provider_type_name = provider.provider_type.value if hasattr(provider.provider_type, 'value') else str(provider.provider_type)

        if provider.provider_type not in clients:
            raise ProviderNotSupportedError(
                f"Provider type {provider_type_name} not supported"
            )

        # Check budget
        if not provider.check_budget():
            budget = getattr(provider, 'monthly_budget', None) or getattr(provider, 'daily_budget', None)
            raise BudgetExceededError(
                f"Budget limit exceeded (limit: ${budget})" if budget else "Budget limit exceeded"
            )

        # Initialize the appropriate client
        client_class = clients[provider.provider_type]
        self._client = client_class(provider)

        logger.info(
            f"MultiProviderVLMClient initialized: "
            f"{provider_type_name} / {provider.model_name} "
            f"({'platform' if self._is_platform_provider else 'organization'} provider)"
        )
    
    async def extract_from_image(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> ExtractionResult:
        """
        Extract data from an image using the configured VLM.
        
        Args:
            image_data: Image as bytes or base64 string
            prompt: Extraction prompt
            media_type: Image MIME type
            
        Returns:
            ExtractionResult with content and usage stats
            
        Raises:
            APIError: If API call fails
            BudgetExceededError: If this request would exceed budget
        """
        # Check budget before request
        if not self.provider.check_budget():
            raise BudgetExceededError("Monthly budget exceeded")
        
        # Make the extraction request
        result = await self._client.extract(image_data, prompt, media_type)
        
        # Record usage on the provider
        self.provider.record_usage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=result.cost,
        )
        
        logger.info(
            f"Extraction completed: {result.input_tokens} in / "
            f"{result.output_tokens} out / ${result.cost:.4f} / "
            f"{result.latency_ms}ms"
        )
        
        return result
    
    async def test_connection(self, test_prompt: str = "Say 'Hello' in one word.") -> Dict[str, Any]:
        """
        Test the connection to the VLM provider with a simple text prompt.

        Args:
            test_prompt: Simple prompt to test the connection

        Returns:
            Dict with success, content, tokens, cost, and error fields
        """
        import time

        try:
            start = time.time()

            # For Anthropic
            if hasattr(self._client, 'client') and hasattr(self._client.client, 'messages'):
                from anthropic import AsyncAnthropic
                message = await self._client.client.messages.create(
                    model=self._client.model,
                    max_tokens=100,
                    temperature=0,
                    messages=[{"role": "user", "content": test_prompt}],
                )
                latency = int((time.time() - start) * 1000)
                return {
                    "success": True,
                    "content": message.content[0].text,
                    "tokens": message.usage.input_tokens + message.usage.output_tokens,
                    "cost": self._client.calculate_cost(
                        message.usage.input_tokens,
                        message.usage.output_tokens
                    ),
                    "latency_ms": latency,
                }

            # For OpenAI-style clients (OpenAI, Azure)
            elif hasattr(self._client, 'client') and hasattr(self._client.client, 'chat'):
                # Newer OpenAI models (o1, o3, o4, gpt-5+) use max_completion_tokens
                token_param = (
                    {"max_completion_tokens": 100}
                    if _openai_needs_max_completion_tokens(self._client.model)
                    else {"max_tokens": 100}
                )
                # Newer OpenAI models (o1, o3, o4, gpt-5+) only support default temperature
                temp_param = (
                    {}
                    if _openai_requires_default_temperature(self._client.model)
                    else {"temperature": 0}
                )
                response = await self._client.client.chat.completions.create(
                    model=self._client.model,
                    **token_param,
                    **temp_param,
                    messages=[{"role": "user", "content": test_prompt}],
                )
                latency = int((time.time() - start) * 1000)
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                return {
                    "success": True,
                    "content": response.choices[0].message.content,
                    "tokens": input_tokens + output_tokens,
                    "cost": self._client.calculate_cost(input_tokens, output_tokens),
                    "latency_ms": latency,
                }

            # For Google Gemini
            elif hasattr(self._client, 'model_instance'):
                response = await asyncio.to_thread(
                    self._client.model_instance.generate_content,
                    test_prompt,
                    generation_config={"max_output_tokens": 100, "temperature": 0}
                )
                latency = int((time.time() - start) * 1000)
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) or 10
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) or 5
                return {
                    "success": True,
                    "content": response.text,
                    "tokens": input_tokens + output_tokens,
                    "cost": self._client.calculate_cost(input_tokens, output_tokens),
                    "latency_ms": latency,
                }

            # For AWS Bedrock
            elif hasattr(self._client, 'client') and hasattr(self._client, 'region'):
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": test_prompt}],
                }
                response = await asyncio.to_thread(
                    self._client.client.invoke_model,
                    modelId=self._client.model,
                    body=json.dumps(body),
                )
                result = json.loads(response["body"].read())
                latency = int((time.time() - start) * 1000)
                input_tokens = result.get("usage", {}).get("input_tokens", 0)
                output_tokens = result.get("usage", {}).get("output_tokens", 0)
                return {
                    "success": True,
                    "content": result["content"][0]["text"],
                    "tokens": input_tokens + output_tokens,
                    "cost": self._client.calculate_cost(input_tokens, output_tokens),
                    "latency_ms": latency,
                }

            else:
                return {
                    "success": False,
                    "content": "",
                    "tokens": 0,
                    "cost": 0.0,
                    "error": "Unknown client type - cannot test connection",
                }

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            error_str = str(e).lower()

            # Provide friendly error messages for common issues
            friendly_error = str(e)

            if "model" in error_str and ("not found" in error_str or "does not exist" in error_str or "not exist" in error_str):
                friendly_error = (
                    f"Model '{self._client.model}' was not found. "
                    f"Please check the model name is correct. "
                    f"Valid models include: gpt-4.1, gpt-4.1-mini, gpt-4o-2025-03-26, o3, o4-mini, claude-sonnet-4-5-20250929, gemini-2.5-pro"
                )
            elif "invalid_api_key" in error_str or "invalid api key" in error_str or "incorrect api key" in error_str:
                friendly_error = (
                    "Invalid API key. Please check that your API key is correct and has not expired."
                )
            elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                friendly_error = (
                    "Authentication failed. Please verify your API key is valid and has the necessary permissions."
                )
            elif "rate limit" in error_str or "rate_limit" in error_str or "429" in error_str:
                friendly_error = (
                    "Rate limit exceeded. Please wait a moment and try again, or check your API plan limits."
                )
            elif "insufficient" in error_str or "quota" in error_str or "credit" in error_str or "billing" in error_str:
                friendly_error = (
                    "Insufficient credits or quota. Please check your billing status and add credits if needed."
                )
            elif "timeout" in error_str or "timed out" in error_str:
                friendly_error = (
                    "Connection timed out. The API server may be slow or unreachable. Please try again."
                )
            elif "connection" in error_str and ("refused" in error_str or "failed" in error_str or "error" in error_str):
                friendly_error = (
                    "Could not connect to the API server. Please check your network connection and API endpoint."
                )
            elif "permission" in error_str or "forbidden" in error_str or "403" in error_str:
                friendly_error = (
                    "Permission denied. Your API key may not have access to this model or feature."
                )

            return {
                "success": False,
                "content": "",
                "tokens": 0,
                "cost": 0.0,
                "error": friendly_error,
            }

    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported provider types."""
        return [p.value for p in cls.CLIENTS.keys()]

    @classmethod
    def is_provider_supported(cls, provider_type: VLMProviderType) -> bool:
        """Check if a provider type is supported."""
        return provider_type in cls.CLIENTS


def get_vlm_client_for_user(
    db_session,
    user_id,
    provider_id: Optional[str] = None,
) -> MultiProviderVLMClient:
    """
    Get VLM client for a user.
    
    Uses specified provider or falls back to user's default provider.
    
    Args:
        db_session: Database session
        user_id: User ID
        provider_id: Optional specific provider ID
        
    Returns:
        Configured MultiProviderVLMClient
        
    Raises:
        ValueError: If no provider configured
    """
    from sqlalchemy import select
    from app.models.user import User
    
    # Get user
    result = db_session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise ValueError(f"User not found: {user_id}")
    
    # Get provider
    if provider_id:
        result = db_session.execute(
            select(VLMProvider).where(
                VLMProvider.id == provider_id,
                VLMProvider.user_id == user_id,
                VLMProvider.is_active == True,
            )
        )
        provider = result.scalar_one_or_none()
    else:
        # Get default provider
        provider = user.get_default_vlm_provider()
    
    if provider is None:
        raise ValueError("No active VLM provider configured for user")
    
    return MultiProviderVLMClient(provider)