"""
VLM Extractor Service Module.

This module provides a VLM extractor service that intelligently selects providers from:
1. Organization VLM providers (org-managed keys) - HIGHEST PRIORITY (if configured)
2. Platform VLM providers (admin-managed keys) - FALLBACK (system-wide)

Provider Selection Logic:
- If organization has configured their own VLM providers, use those
- Otherwise, fall back to admin-level platform VLM providers
- No environment variable fallback (ANTHROPIC_API_KEY removed)

Features comprehensive monitoring, audit logging, budget tracking, and failover.

Example Usage:
    from app.core.extraction.vlm_extractor_service import VLMExtractorService

    extractor = VLMExtractorService(db_session, user_id)
    result = await extractor.extract_page(image_data, page_number, total_pages)

Legacy Import (deprecated):
    from app.core.extraction.vlm_extractor_service import UserAwareVLMExtractor
"""

import asyncio
import base64
import json
import logging
import re
import time
import uuid
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.extraction.prompt_builder import PromptBuilder, get_prompt_builder
from app.core.extraction.schemas import (
    BoundingBox,
    ExtractionContext,
    ExtractionResult,
    ExtractedProduct,
    FieldConfidence,
    PageExtractionResult,
)
from app.core.extraction.multi_provider_client import (
    MultiProviderVLMClient,
    VLMClientError,
    APIError,
    BudgetExceededError,
    ProviderNotSupportedError,
)
from app.models.vlm_provider import VLMProvider, VLMProviderType
from app.models.platform_vlm_provider import PlatformVLMProvider
from app.models.user import User
# Lazy-load PaddleOCR to avoid circular imports
# Check availability at runtime instead of import time
def _is_paddle_ocr_available() -> bool:
    """Check if PaddleOCR is available (lazy check to avoid circular imports)."""
    try:
        from app.core.image_processing.paddle_ocr_detector import is_paddle_ocr_available
        return is_paddle_ocr_available()
    except ImportError:
        return False

def _get_paddle_ocr_detector():
    """Get PaddleOCR detector (lazy import)."""
    from app.core.image_processing.paddle_ocr_detector import get_paddle_ocr_detector
    return get_paddle_ocr_detector()

# Services imported in __init__ to avoid circular imports

logger = logging.getLogger(__name__)


class VLMExtractorService:
    """
    VLM Extractor Service with intelligent provider selection and comprehensive monitoring.

    Provider Selection Priority:
    1. Organization VLM providers (org-configured keys) - HIGHEST PRIORITY if configured
    2. Platform VLM providers (admin-managed keys) - FALLBACK for system-wide usage

    Organizations can configure their own VLM providers for dedicated usage and budget control.
    If no organization provider is configured, the system falls back to admin-level platform
    providers managed through the admin dashboard.

    Features:
    - Automatic failover between providers
    - Comprehensive audit logging
    - Budget monitoring with alerts
    - Usage tracking per organization
    - Real-time cost calculation

    Attributes:
        db: Database session
        user_id: User ID for provider lookup
        prompt_builder: Prompt builder instance
        platform_service: Platform provider management
        audit_service: Audit logging service
        budget_service: Budget monitoring service

    Example:
        >>> extractor = VLMExtractorService(db, user_id)
        >>> result = await extractor.extract_page(image_bytes, 1, 12)
        >>> print(f"Found {len(result.products)} products")
        >>> print(f"Cost: ${extractor.total_cost:.4f}")
        >>> print(f"Provider: {extractor.provider_info['type']}")
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        """
        Initialize the enhanced user-aware VLM extractor.

        Args:
            db: Database session
            user_id: User ID for provider lookup
            prompt_builder: Optional custom prompt builder
        """
        self.db = db
        self.user_id = user_id
        self.prompt_builder = prompt_builder or get_prompt_builder()

        # Initialize services (imported here to avoid circular imports)
        from app.services.platform_vlm_service import PlatformVLMProviderService
        from app.services.vlm_audit_service import VLMAuditService
        from app.services.budget_monitoring_service import BudgetMonitoringService

        self.platform_service = PlatformVLMProviderService(db)
        self.audit_service = VLMAuditService(db)
        self.budget_service = BudgetMonitoringService(db)

        # Track usage across extractions
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

        # Current provider state
        self._current_provider_type = None  # 'organization', 'platform', or 'fallback'
        self._organization_provider: Optional[VLMProvider] = None
        self._platform_provider: Optional[PlatformVLMProvider] = None
        self._client: Optional[MultiProviderVLMClient] = None
        self._user: Optional[User] = None

        # Load user and determine provider strategy
        self._load_user_and_providers()

    def _load_user_and_providers(self):
        """Load user information and determine provider selection strategy."""
        try:
            from uuid import UUID

            # Ensure user_id is proper UUID type
            if isinstance(self.user_id, str):
                user_uuid = UUID(self.user_id)
            else:
                user_uuid = self.user_id

            logger.info(f"Loading providers for user: {user_uuid}")

            # Get user with organization info
            user_result = self.db.execute(
                select(User).where(User.id == user_uuid)
            )
            self._user = user_result.scalar_one_or_none()

            if not self._user:
                logger.error(f"User {user_uuid} not found")
                self._current_provider_type = None
                return

            logger.info(f"User organization: {self._user.default_organization_id}")

            # PRIORITY ORDER:
            # 1. Try organization-level providers first (user's own API keys)
            if self._user.default_organization_id:
                logger.info("Checking for organization-level VLM providers")
                self._load_organization_provider()

            # 2. If no organization provider, fall back to platform providers (admin-managed)
            if self._current_provider_type is None:
                logger.info("No organization providers, trying platform providers")
                self._load_platform_provider()

            # 3. If still no provider, set to None (no fallback to env variable)
            if self._current_provider_type is None:
                logger.warning(
                    "No VLM providers available. Configure organization providers in Settings "
                    "or contact admin to set up platform providers."
                )

        except Exception as e:
            logger.error(f"Error loading user providers: {e}", exc_info=True)
            self._current_provider_type = None

    def _load_organization_provider(self):
        """Try to load and initialize organization VLM provider."""
        try:
            org_id = self._user.default_organization_id

            # Get organization's active VLM provider
            result = self.db.execute(
                select(VLMProvider).where(
                    VLMProvider.organization_id == org_id,
                    VLMProvider.is_active.is_(True),
                ).order_by(
                    VLMProvider.is_default.desc(),
                    VLMProvider.created_at.desc()
                ).limit(1)
            )
            provider = result.scalar_one_or_none()

            if not provider:
                logger.info(f"No active organization provider for user {self.user_id}")
                return

            # Check budget
            if not provider.check_budget():
                logger.warning(f"Organization provider budget exceeded for user {self.user_id}")
                return

            # Try to initialize client
            try:
                self._organization_provider = provider
                self._client = MultiProviderVLMClient(provider)
                self._current_provider_type = 'organization'

                logger.info(
                    f"Using organization provider override: {provider.provider_type.value} / "
                    f"{provider.model_name} (id: {provider.id})"
                )

                # Log successful provider selection
                self.audit_service.log_provider_selection(
                    user_id=self._user.id,
                    organization_id=org_id,
                    provider_type='organization',
                    provider_id=provider.id,
                    model_name=provider.model_name,
                    selection_reason="Organization provider override - configured by organization"
                )

            except (ProviderNotSupportedError, BudgetExceededError) as e:
                logger.warning(f"Failed to initialize organization provider: {e}")

        except Exception as e:
            logger.error(f"Error loading organization provider: {e}", exc_info=True)

    def _load_platform_provider(self):
        """Try to load and initialize platform VLM provider with failover."""
        try:
            org_id = self._user.default_organization_id if self._user else None

            # Get best available platform provider
            provider = self.platform_service.get_best_provider(organization_id=org_id)

            if not provider:
                logger.info(f"No platform providers available for user {self.user_id}")
                return

            # Try to initialize client
            try:
                self._platform_provider = provider
                self._client = MultiProviderVLMClient(provider)
                self._current_provider_type = 'platform'

                logger.info(
                    f"Using platform provider: {provider.provider_type.value} / "
                    f"{provider.model_name} (priority: {provider.priority})"
                )

                # Log successful provider selection
                self.audit_service.log_provider_selection(
                    user_id=self._user.id,
                    organization_id=org_id,
                    provider_type='platform',
                    platform_provider_id=provider.id,
                    model_name=provider.model_name,
                    selection_reason="Platform provider selected with failover capability"
                )

            except Exception as e:
                logger.warning(f"Failed to initialize platform provider {provider.id}: {e}")

                # Mark provider as failed and try failover
                self.platform_service.mark_provider_failed(provider.id, str(e))

                # Try next provider
                next_provider = self.platform_service.get_best_provider(
                    organization_id=org_id,
                    exclude_failed=True
                )

                if next_provider and next_provider.id != provider.id:
                    logger.info(f"Attempting failover to provider {next_provider.id}")
                    self._platform_provider = next_provider
                    try:
                        self._client = MultiProviderVLMClient(next_provider)
                        self._current_provider_type = 'platform'

                        logger.info(f"Failover successful to: {next_provider.provider_type.value}")

                        # Log failover
                        self.audit_service.log_provider_failover(
                            user_id=self._user.id,
                            organization_id=org_id,
                            failed_provider_id=provider.id,
                            failover_provider_id=next_provider.id,
                            failure_reason=str(e)
                        )

                    except Exception as failover_error:
                        logger.error(f"Failover also failed: {failover_error}")
                        self.platform_service.mark_provider_failed(next_provider.id, str(failover_error))

        except Exception as e:
            logger.error(f"Error loading platform provider: {e}", exc_info=True)

    def _check_provider_available(self) -> bool:
        """Check if any VLM provider is available for extraction."""
        return self._current_provider_type is not None and self._client is not None

    async def extract_page(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
    ) -> PageExtractionResult:
        """
        Extract products from a single page image using card-first pipeline.

        Pipeline:
        1. Prepare image (resize for VLM)
        2. Detect card regions on the prepared image
        3. Annotate image with numbered colored boxes
        4. Send annotated image to VLM with card extraction prompt
        5. VLM returns products with region_numbers
        6. Map region numbers to detected card bounding boxes
        7. Scale bounding boxes to original image dimensions

        Args:
            image_data: Image as bytes or base64 string
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context
            image_format: Image format (png, jpg, etc.)

        Returns:
            PageExtractionResult with extracted products
        """
        start_time = time.time()
        session_id = f"{context.leaflet_id if context else 'unknown'}_page_{page_number}_{int(time.time())}"

        # Step 1: Prepare image and get dimensions (both original and prepared/resized)
        base64_image, media_type, orig_width, orig_height, prep_width, prep_height = (
            await self._prepare_image_with_dimensions(image_data, image_format)
        )
        prepared_bytes = base64.b64decode(base64_image)

        # Update context with PREPARED dimensions
        if context is not None:
            context = ExtractionContext(
                leaflet_id=context.leaflet_id,
                leaflet_uuid=context.leaflet_uuid,
                retailer=context.retailer,
                country=context.country,
                language=context.language,
                currency=context.currency,
                page_count=context.page_count,
                previous_page_notes=context.previous_page_notes,
                has_previous_page=context.has_previous_page,
                has_next_page=context.has_next_page,
                image_width=prep_width,
                image_height=prep_height,
                request_ip=context.request_ip,
            )
        else:
            context = ExtractionContext(
                leaflet_id="unknown",
                page_count=total_pages,
                image_width=prep_width,
                image_height=prep_height,
            )

        logger.info(
            f"[CARD-FIRST] Extracting page {page_number}: original {orig_width}x{orig_height}, "
            f"prepared {prep_width}x{prep_height}"
        )

        # Step 2: Detect card regions on the prepared image
        from app.core.image_processing.card_detector import detect_card_regions
        regions = detect_card_regions(prepared_bytes)
        logger.info(
            f"[CARD-FIRST] Page {page_number}: detected {len(regions)} card regions"
        )

        # Step 3: Annotate image with numbered region boxes
        from app.core.image_processing.card_annotator import annotate_page_with_regions
        annotated_bytes = annotate_page_with_regions(prepared_bytes, regions)
        annotated_b64 = base64.b64encode(annotated_bytes).decode()

        # Step 3b: Save debug annotated image (for visual inspection of grid/regions)
        try:
            from app.config import settings
            if settings.debug:
                leaflet_id_str = context.leaflet_id if context else "unknown"
                debug_key = f"leaflets/{leaflet_id_str}/debug/page_{page_number:03d}_annotated.jpg"
                from app.utils.storage import get_storage
                storage = get_storage()
                await storage.upload_file(annotated_bytes, debug_key, content_type="image/jpeg")
                logger.info(f"[CARD-FIRST] Saved debug annotated image: {debug_key}")
        except Exception as e:
            logger.debug(f"[CARD-FIRST] Failed to save debug image: {e}")

        # Step 4: Build card extraction prompt
        prompt = self.prompt_builder.build_card_extraction_prompt(
            page_number=page_number,
            total_pages=total_pages,
            num_regions=len(regions),
            context=context,
        )

        # Get the appropriate client
        client = self._get_current_client()

        # Make the extraction request with audit logging
        try:
            # Log extraction start
            self.audit_service.log_extraction_request(
                user_id=self._user.id if self._user else None,
                organization_id=self._user.default_organization_id if self._user else None,
                session_id=session_id,
                leaflet_id=context.leaflet_uuid if context else None,
                page_number=page_number,
                provider_type=self._current_provider_type,
                provider_id=self._get_current_provider_id(),
                model_name=self._get_current_model_name(),
                image_size_bytes=len(annotated_bytes),
                request_ip=context.request_ip if context else None,
            )

            # Step 5: Send annotated image to VLM
            result = await client.extract_from_image(
                image_data=annotated_b64,
                prompt=prompt,
                media_type="image/jpeg",
            )

            # Track usage
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            # Usage is already recorded on the provider by
            # MultiProviderVLMClient.extract_from_image() -> provider.record_usage().
            # Commit the ORM-level changes to persist them.
            if self._current_provider_type in ('organization', 'platform'):
                self.db.commit()

            # Parse the response
            parsed_result = self._parse_response(
                {
                    "content": result.content,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
                page_number,
                image_width=prep_width,
                image_height=prep_height,
            )

            # Step 6: Assign bounding boxes from detected regions
            region_map = {r["id"]: r for r in regions}
            scale_x = orig_width / prep_width if prep_width > 0 else 1.0
            scale_y = orig_height / prep_height if prep_height > 0 else 1.0

            assigned_count = 0
            for product in parsed_result.products:
                region_nums = getattr(product, '_region_numbers', [])
                if region_nums:
                    # Collect bounding boxes for all matched regions
                    matched_regions = [region_map[n] for n in region_nums if n in region_map]
                    if matched_regions:
                        # Single region -> use its bbox
                        # Multiple regions -> compute union bbox
                        x = min(r["x"] for r in matched_regions)
                        y = min(r["y"] for r in matched_regions)
                        x2 = max(r["x"] + r["width"] for r in matched_regions)
                        y2 = max(r["y"] + r["height"] for r in matched_regions)
                        # Scale to original dimensions
                        product.bounding_box = BoundingBox(
                            x=max(0, int(x * scale_x)),
                            y=max(0, int(y * scale_y)),
                            width=max(1, int((x2 - x) * scale_x)),
                            height=max(1, int((y2 - y) * scale_y)),
                        )
                        assigned_count += 1
                        logger.debug(
                            f"[CARD-FIRST] Product '{product.product_name[:30]}' -> "
                            f"regions {region_nums} -> bbox "
                            f"({product.bounding_box.x},{product.bounding_box.y},"
                            f"{product.bounding_box.width}x{product.bounding_box.height})"
                        )

            logger.info(
                f"[CARD-FIRST] Page {page_number}: assigned {assigned_count}/{len(parsed_result.products)} "
                f"products to card regions (scale: {scale_x:.2f}x, {scale_y:.2f}y)"
            )

            # Set processing time
            parsed_result.processing_time_ms = int((time.time() - start_time) * 1000)

            # Log successful extraction
            self.audit_service.log_extraction_success(
                session_id=session_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=result.cost,
                processing_time_ms=parsed_result.processing_time_ms,
                products_found=parsed_result.product_count,
                user_id=self.user_id,
                leaflet_id=context.leaflet_uuid if context else None,
                request_ip=context.request_ip if context else None,
                response_metadata={
                    'avg_confidence': sum(p.confidence_score for p in parsed_result.products) / len(parsed_result.products) if parsed_result.products else 0,
                    'page_notes': parsed_result.page_notes,
                    'continuation_detected': parsed_result.continuation_detected,
                    'extraction_method': 'card_first',
                    'regions_detected': len(regions),
                    'regions_assigned': assigned_count,
                }
            )

            logger.info(
                f"[CARD-FIRST] Extracted {parsed_result.product_count} products from page {page_number} "
                f"using {self._current_provider_type} provider in {parsed_result.processing_time_ms}ms "
                f"(cost: ${result.cost:.4f})"
            )

            return parsed_result

        except BudgetExceededError as e:
            logger.error(f"Budget exceeded during extraction: {e}")

            # Log budget exceeded
            self.audit_service.log_extraction_failure(
                session_id=session_id,
                error_category='budget_exceeded',
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
                request_ip=context.request_ip if context else None,
            )

            # Trigger budget monitoring
            if self._user and self._user.default_organization_id:
                self.budget_service.check_and_alert(
                    organization_id=self._user.default_organization_id,
                    alert_context={
                        'extraction_session': session_id,
                        'page_number': page_number,
                        'provider_type': self._current_provider_type,
                    }
                )

            raise

        except APIError as e:
            logger.error(f"API error during extraction: {e}")

            # Log API error
            self.audit_service.log_extraction_failure(
                session_id=session_id,
                error_category='api_error',
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
                provider_specific_error=getattr(e, 'provider_error', None),
                request_ip=context.request_ip if context else None,
            )

            # If using platform provider, consider failover
            if self._current_provider_type == 'platform' and self._platform_provider:
                # Mark current platform provider as failed
                self.platform_service.mark_provider_failed(self._platform_provider.id, str(e))

                # Try to failover for this request
                org_id = self._user.default_organization_id if self._user else None
                next_provider = self.platform_service.get_best_provider(
                    organization_id=org_id,
                    exclude_failed=True
                )

                if next_provider and next_provider.id != self._platform_provider.id:
                    logger.info(f"Attempting immediate failover to provider {next_provider.id}")
                    try:
                        failover_client = MultiProviderVLMClient(next_provider)

                        # Retry the request with failover provider
                        result = await failover_client.extract_from_image(
                            image_data=annotated_b64,
                            prompt=prompt,
                            media_type="image/jpeg",
                        )

                        # Update current provider
                        self._platform_provider = next_provider
                        self._client = failover_client

                        logger.info(f"Failover successful to: {next_provider.provider_type.value}")

                        # Continue with successful result processing...
                        self.total_input_tokens += result.input_tokens
                        self.total_output_tokens += result.output_tokens
                        self.total_cost += result.cost

                        # Parse and return result
                        parsed_result = self._parse_response(
                            {
                                "content": result.content,
                                "input_tokens": result.input_tokens,
                                "output_tokens": result.output_tokens,
                            },
                            page_number,
                            image_width=prep_width,
                            image_height=prep_height,
                        )

                        # Assign bounding boxes from regions (same as main path)
                        for product in parsed_result.products:
                            region_nums = getattr(product, '_region_numbers', [])
                            if region_nums:
                                matched_regions = [region_map[n] for n in region_nums if n in region_map]
                                if matched_regions:
                                    x = min(r["x"] for r in matched_regions)
                                    y = min(r["y"] for r in matched_regions)
                                    x2 = max(r["x"] + r["width"] for r in matched_regions)
                                    y2 = max(r["y"] + r["height"] for r in matched_regions)
                                    product.bounding_box = BoundingBox(
                                        x=max(0, int(x * scale_x)),
                                        y=max(0, int(y * scale_y)),
                                        width=max(1, int((x2 - x) * scale_x)),
                                        height=max(1, int((y2 - y) * scale_y)),
                                    )

                        parsed_result.processing_time_ms = int((time.time() - start_time) * 1000)

                        # Log successful failover
                        self.audit_service.log_extraction_success(
                            session_id=session_id,
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            cost=result.cost,
                            processing_time_ms=parsed_result.processing_time_ms,
                            products_found=parsed_result.product_count,
                            user_id=self.user_id,
                            leaflet_id=context.leaflet_uuid if context else None,
                            request_ip=context.request_ip if context else None,
                            response_metadata={
                                'failover': True,
                                'failed_provider_id': str(self._platform_provider.id),
                                'success_provider_id': str(next_provider.id),
                            }
                        )

                        return parsed_result

                    except Exception as failover_error:
                        logger.error(f"Failover also failed: {failover_error}")
                        self.platform_service.mark_provider_failed(next_provider.id, str(failover_error))

            raise

        except Exception as e:
            logger.error(f"Unexpected error during extraction: {e}", exc_info=True)

            # Log unexpected error
            self.audit_service.log_extraction_failure(
                session_id=session_id,
                error_category='unexpected_error',
                error_message=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
                request_ip=context.request_ip if context else None,
            )

            raise

    async def count_products_on_page(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        image_format: str = "png",
    ) -> tuple[int, str]:
        """
        Count the total number of products on a page.

        This is the first step in count-first verification - establishing
        the expected product count before extraction.

        Args:
            image_data: Image as bytes or base64 string
            page_number: Current page number
            image_format: Image format

        Returns:
            Tuple of (product_count, confidence)
        """
        logger.info(f"[COUNT] Counting products on page {page_number}")

        # Prepare the original image (no annotations)
        base64_image, media_type, _, _, _, _ = (
            await self._prepare_image_with_dimensions(image_data, image_format)
        )

        # Build count prompt
        count_prompt = self.prompt_builder.build_count_products_prompt()

        # Get the client and send request
        client = self._get_current_client()
        try:
            result = await client.extract_from_image(
                image_data=base64_image,
                prompt=count_prompt,
                media_type=media_type,
            )

            # Track usage
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            # Parse the response
            content = result.content.strip()
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                logger.warning(f"[COUNT] No JSON found in count response")
                return 0, "low"

            json_data = json.loads(json_match.group())
            product_count = json_data.get("product_count", 0)
            confidence = json_data.get("confidence", "medium")
            notes = json_data.get("notes", "")

            logger.info(
                f"[COUNT] Page {page_number}: VLM counted {product_count} products "
                f"(confidence: {confidence}) - {notes}"
            )

            return product_count, confidence

        except Exception as e:
            logger.error(f"[COUNT] Product counting failed: {e}")
            return 0, "low"

    async def find_missing_products(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        extracted_products: List[ExtractedProduct],
        expected_count: int,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
    ) -> List[ExtractedProduct]:
        """
        Find specific missing products when count doesn't match.

        Args:
            image_data: Original image as bytes or base64 string
            page_number: Current page number
            extracted_products: Products already extracted
            expected_count: Total products expected on page
            context: Optional extraction context
            image_format: Image format

        Returns:
            List of additional products that were missed
        """
        extracted_count = len(extracted_products)
        missing_count = expected_count - extracted_count

        logger.info(
            f"[FIND-MISSING] Page {page_number}: Looking for {missing_count} "
            f"missing products (expected {expected_count}, have {extracted_count})"
        )

        # Prepare the original image (no annotations)
        base64_image, media_type, _, _, _, _ = (
            await self._prepare_image_with_dimensions(image_data, image_format)
        )

        # Build list of already extracted products for the prompt
        extracted_list = []
        for p in extracted_products:
            extracted_list.append({
                "product_name": p.product_name,
                "brand": p.brand,
                "regular_price": p.regular_price,
                "discounted_price": p.discounted_price,
            })

        # Build find-missing prompt
        find_missing_prompt = self.prompt_builder.build_find_missing_prompt(
            extracted_products=extracted_list,
            expected_count=expected_count,
            missing_count=missing_count,
            context=context,
        )

        # Get the client and send request
        client = self._get_current_client()
        try:
            result = await client.extract_from_image(
                image_data=base64_image,
                prompt=find_missing_prompt,
                media_type=media_type,
            )

            # Track usage
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            # Parse the response
            content = result.content.strip()
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                logger.warning(f"[FIND-MISSING] No JSON found in response")
                return []

            json_data = json.loads(json_match.group())
            missing_products = json_data.get("missing_products", [])
            still_missing = json_data.get("still_missing", 0)
            search_notes = json_data.get("search_notes", "")

            logger.info(
                f"[FIND-MISSING] Page {page_number}: Found {len(missing_products)} products, "
                f"still missing {still_missing}. Notes: {search_notes}"
            )

            # Convert missing products to ExtractedProduct objects
            additional_products = []
            for raw in missing_products:
                try:
                    location_desc = raw.get("location_description", "")
                    product = ExtractedProduct(
                        product_name=raw.get("product_name", "Unknown"),
                        brand=raw.get("brand"),
                        regular_price=raw.get("regular_price"),
                        discounted_price=raw.get("discounted_price"),
                        discount_percentage=raw.get("discount_percentage"),
                        currency=raw.get("currency", context.currency if context else None),
                        size=raw.get("size"),
                        confidence_score=0.70,  # Lower confidence for verification-found products
                        uncertainty_flags=["found_in_count_verification", location_desc],
                        bounding_box=None,  # Will get fallback bbox later
                    )
                    additional_products.append(product)
                    logger.info(f"[FIND-MISSING] Found: {product.product_name} at {location_desc}")
                except Exception as e:
                    logger.warning(f"[FIND-MISSING] Failed to parse product: {e}")

            return additional_products

        except Exception as e:
            logger.error(f"[FIND-MISSING] Find missing products failed: {e}")
            return []

    async def do_fresh_extraction(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        existing_products: List[ExtractedProduct],
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
    ) -> List[ExtractedProduct]:
        """
        Do a completely fresh extraction and return only new unique products.

        This is a fallback when find_missing_products doesn't find anything
        but we suspect products might still be missing. It uses a simple
        "list all products" prompt without card annotations.

        Args:
            image_data: Original image as bytes or base64 string
            page_number: Current page number
            existing_products: Products already extracted
            context: Optional extraction context
            image_format: Image format

        Returns:
            List of new products not in existing_products
        """
        logger.info(
            f"[FRESH-EXTRACT] Page {page_number}: Running fresh extraction "
            f"(have {len(existing_products)} existing products)"
        )

        # Prepare the original image (no annotations)
        base64_image, media_type, _, _, _, _ = (
            await self._prepare_image_with_dimensions(image_data, image_format)
        )

        # Build simple listing prompt
        simple_prompt = self.prompt_builder.build_simple_listing_prompt(context=context)

        # Get the client and send request
        client = self._get_current_client()
        try:
            result = await client.extract_from_image(
                image_data=base64_image,
                prompt=simple_prompt,
                media_type=media_type,
            )

            # Track usage
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            # Parse the response
            content = result.content.strip()
            json_match = re.search(r'\{[\s\S]*\}', content)
            if not json_match:
                logger.warning(f"[FRESH-EXTRACT] No JSON found in response")
                return []

            json_data = json.loads(json_match.group())
            fresh_products = json_data.get("products", [])
            total_found = json_data.get("total_count", len(fresh_products))

            logger.info(
                f"[FRESH-EXTRACT] Page {page_number}: Fresh extraction found {total_found} products"
            )

            # Helper function to normalize product names for comparison
            def normalize_for_comparison(name: str, brand: str = None) -> str:
                """Remove sizes, weights, brands from name for fuzzy matching."""
                import re
                name_lower = (name or "").lower().strip()
                # Remove common size/weight patterns
                name_lower = re.sub(r'\b\d+\s*(g|kg|ml|l|cl|kom|pack|pcs)\b', '', name_lower)
                name_lower = re.sub(r'\b\d+[.,]\d+\s*(g|kg|ml|l)\b', '', name_lower)
                # Remove brand if provided
                if brand:
                    brand_lower = brand.lower().strip()
                    name_lower = name_lower.replace(brand_lower, '')
                # Remove common suffixes/abbreviations
                name_lower = re.sub(r'\b(to!|toi|više vrsta|razne vrste)\b', '', name_lower)
                # Remove extra whitespace
                name_lower = ' '.join(name_lower.split())
                return name_lower

            def get_key_words(name: str) -> set:
                """Extract significant words (>2 chars) from name."""
                words = name.split()
                # Filter out short words and common noise
                return {w for w in words if len(w) > 2 and w not in {'the', 'and', 'ili', 'sa', 'od', 'za'}}

            # Build existing products info for deduplication
            existing_info = []
            for p in existing_products:
                name_norm = normalize_for_comparison(p.product_name, p.brand)
                key_words = get_key_words(name_norm)
                price = p.discounted_price or p.regular_price or 0
                existing_info.append({
                    'name': (p.product_name or "").lower(),
                    'name_norm': name_norm,
                    'key_words': key_words,
                    'brand': (p.brand or "").lower(),
                    'price': price,
                })

            # Find new products not in existing set
            new_products = []
            for raw in fresh_products:
                try:
                    name = raw.get("product_name", "")
                    brand = raw.get("brand", "") or ""
                    name_norm = normalize_for_comparison(name, brand)
                    key_words = get_key_words(name_norm)
                    price = raw.get("discounted_price") or raw.get("regular_price") or 0

                    # Check if this product is already in existing
                    is_duplicate = False

                    for existing in existing_info:
                        # Exact name match
                        if name.lower() == existing['name']:
                            is_duplicate = True
                            break

                        # Normalized name match
                        if name_norm == existing['name_norm'] and name_norm:
                            is_duplicate = True
                            break

                        # Key words overlap - if >50% of key words match, it's a duplicate
                        if key_words and existing['key_words']:
                            overlap = len(key_words & existing['key_words'])
                            # Use the smaller set for comparison (more restrictive)
                            min_words = min(len(key_words), len(existing['key_words']))
                            if min_words > 0 and overlap / min_words >= 0.5:
                                is_duplicate = True
                                logger.debug(
                                    f"[FRESH-EXTRACT] Duplicate detected by key words: "
                                    f"'{name}' matches '{existing['name']}' "
                                    f"(overlap: {overlap}/{min_words})"
                                )
                                break

                        # First word match (usually the main product type)
                        if name_norm and existing['name_norm']:
                            new_first = name_norm.split()[0] if name_norm.split() else ""
                            existing_first = existing['name_norm'].split()[0] if existing['name_norm'].split() else ""
                            if new_first and existing_first and new_first == existing_first and len(new_first) > 3:
                                # Same first word, check if prices are close
                                if price and existing['price']:
                                    price_diff = abs(price - existing['price']) / max(price, existing['price'])
                                    if price_diff < 0.1:  # Within 10%
                                        is_duplicate = True
                                        break

                    if is_duplicate:
                        continue

                    # This is a new product!
                    location_desc = raw.get("location", "")
                    product = ExtractedProduct(
                        product_name=name,
                        brand=raw.get("brand"),
                        regular_price=raw.get("regular_price"),
                        discounted_price=raw.get("discounted_price"),
                        discount_percentage=raw.get("discount_percentage"),
                        currency=raw.get("currency", context.currency if context else None),
                        size=raw.get("size"),
                        confidence_score=0.65,  # Lower confidence for fresh-extract products
                        uncertainty_flags=["found_in_fresh_extraction", location_desc],
                        bounding_box=None,  # Will get fallback bbox later
                    )
                    new_products.append(product)
                    logger.info(f"[FRESH-EXTRACT] New product found: {name} at {location_desc}")

                except Exception as e:
                    logger.warning(f"[FRESH-EXTRACT] Failed to parse product: {e}")

            logger.info(
                f"[FRESH-EXTRACT] Page {page_number}: Found {len(new_products)} NEW products "
                f"(filtered from {len(fresh_products)} total)"
            )

            return new_products

        except Exception as e:
            logger.error(f"[FRESH-EXTRACT] Fresh extraction failed: {e}")
            return []

    async def extract_page_with_verification(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
        max_verification_rounds: int = 2,
    ) -> PageExtractionResult:
        """
        Extract products using COUNT-FIRST verification.

        This approach:
        1. First asks VLM to count total products on the page
        2. Extracts products using card-first pipeline
        3. If counts don't match, specifically asks for missing products
        4. Repeats until counts match or max rounds reached

        Args:
            image_data: Image as bytes or base64 string
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context
            image_format: Image format
            max_verification_rounds: Maximum iterations to find missing products

        Returns:
            PageExtractionResult with all extracted products
        """
        # Step 1: Count products first (establish expectation)
        expected_count, count_confidence = await self.count_products_on_page(
            image_data=image_data,
            page_number=page_number,
            image_format=image_format,
        )

        logger.info(
            f"[COUNT-FIRST] Page {page_number}: Expecting {expected_count} products "
            f"(confidence: {count_confidence})"
        )

        # Step 2: Run standard card-first extraction
        result = await self.extract_page(
            image_data=image_data,
            page_number=page_number,
            total_pages=total_pages,
            context=context,
            image_format=image_format,
        )

        extracted_count = len(result.products)
        logger.info(
            f"[COUNT-FIRST] Page {page_number}: Extracted {extracted_count} products"
        )

        # Step 3: ALWAYS do at least one verification pass
        # The counter is not 100% reliable and can undercount, so even if
        # extracted >= expected, we should verify we haven't missed products
        # in corners, edges, or overlapping with other content.

        # Add a margin to account for counter undercounting (counter tends to
        # undercount by 10-15%). If counter says 20, expect up to 23.
        adjusted_expected = max(expected_count + 3, int(expected_count * 1.15))

        # Step 4: Find missing products until we reach adjusted expectation
        # or no more products are found
        verification_round = 0
        while verification_round < max_verification_rounds:
            verification_round += 1
            # Use adjusted count for estimation, but tell VLM to look for any missed
            estimated_missing = max(0, adjusted_expected - extracted_count)

            logger.info(
                f"[VERIFY] Page {page_number}: Round {verification_round} - "
                f"Scanning for potentially missed products (estimated: {estimated_missing})"
            )

            # Find the missing products - use adjusted expected for better coverage
            additional_products = await self.find_missing_products(
                image_data=image_data,
                page_number=page_number,
                extracted_products=result.products,
                expected_count=adjusted_expected,  # Use adjusted count
                context=context,
                image_format=image_format,
            )

            if not additional_products:
                logger.info(
                    f"[VERIFY] Page {page_number}: Round {verification_round} "
                    f"found no additional products via find_missing."
                )

                # If this is the first round and find_missing found nothing,
                # try a fresh extraction as fallback. This uses a completely
                # different prompt style that might catch missed products.
                if verification_round == 1:
                    logger.info(
                        f"[VERIFY] Page {page_number}: Trying fresh extraction fallback..."
                    )
                    fresh_products = await self.do_fresh_extraction(
                        image_data=image_data,
                        page_number=page_number,
                        existing_products=result.products,
                        context=context,
                        image_format=image_format,
                    )

                    if fresh_products:
                        result.products.extend(fresh_products)
                        extracted_count = len(result.products)
                        logger.info(
                            f"[VERIFY] Page {page_number}: Fresh extraction added "
                            f"{len(fresh_products)} products. Total now: {extracted_count}"
                        )
                    else:
                        logger.info(
                            f"[VERIFY] Page {page_number}: Fresh extraction found no new products."
                        )

                break

            # Add found products
            result.products.extend(additional_products)
            extracted_count = len(result.products)

            logger.info(
                f"[VERIFY] Page {page_number}: Round {verification_round} "
                f"added {len(additional_products)} products. Total now: {extracted_count}"
            )

        # Log final result
        logger.info(
            f"[COUNT-FIRST] Page {page_number}: Final count {extracted_count} products "
            f"(VLM counted: {expected_count}, adjusted: {adjusted_expected})"
        )

        return result

    async def extract_page_with_ocr(
        self,
        image_data: Union[bytes, str],
        page_number: int,
        total_pages: int,
        context: Optional[ExtractionContext] = None,
        image_format: str = "png",
    ) -> PageExtractionResult:
        """
        Extract products using VLM for data + PaddleOCR for bounding boxes.

        DEPRECATED: The main extraction path now uses card-first extraction
        via extract_page(). This method is kept for backward compatibility but
        is no longer called from the main extraction pipeline.

        This approach uses ONE VLM call (vs two for grid approach):
        1. VLM extracts product DATA only (names, prices, etc.)
        2. PaddleOCR detects text regions and clusters into product bounding boxes
        3. Match VLM products to OCR regions by text similarity

        Args:
            image_data: Image as bytes or base64 string
            page_number: Current page number (1-indexed)
            total_pages: Total pages in leaflet
            context: Optional extraction context
            image_format: Image format (png, jpg, etc.)

        Returns:
            PageExtractionResult with extracted products and OCR bounding boxes
        """
        if not _is_paddle_ocr_available():
            logger.warning("PaddleOCR not available, falling back to grid-based extraction")
            return await self.extract_page(image_data, page_number, total_pages, context, image_format)

        start_time = time.time()
        session_id = f"{context.leaflet_id if context else 'unknown'}_page_{page_number}_{int(time.time())}"

        # Prepare image (no grid overlay needed)
        base64_image, media_type, img_width, img_height, _, _ = await self._prepare_image_with_dimensions(
            image_data, image_format
        )

        # Update context with image dimensions
        if context is not None:
            context = ExtractionContext(
                leaflet_id=context.leaflet_id,
                leaflet_uuid=context.leaflet_uuid,
                retailer=context.retailer,
                country=context.country,
                language=context.language,
                currency=context.currency,
                page_count=context.page_count,
                previous_page_notes=context.previous_page_notes,
                has_previous_page=context.has_previous_page,
                has_next_page=context.has_next_page,
                image_width=img_width,
                image_height=img_height,
                request_ip=context.request_ip,
            )
        else:
            context = ExtractionContext(
                leaflet_id="unknown",
                page_count=total_pages,
                image_width=img_width,
                image_height=img_height,
            )

        logger.info(f"Extracting page {page_number} with OCR: image dimensions {img_width}x{img_height}")

        # Build DATA-ONLY prompt (no bounding boxes) - OCR provides bounding boxes
        prompt = self.prompt_builder.build_data_only_prompt(
            page_number=page_number,
            total_pages=total_pages,
            context=context,
        )

        # Get the VLM client
        client = self._get_current_client()

        try:
            # Step 1: VLM extracts product DATA
            self.audit_service.log_extraction_request(
                user_id=self._user.id if self._user else None,
                organization_id=self._user.default_organization_id if self._user else None,
                session_id=session_id,
                leaflet_id=context.leaflet_uuid if context else None,
                page_number=page_number,
                provider_type=self._current_provider_type,
                provider_id=self._get_current_provider_id(),
                model_name=self._get_current_model_name(),
                image_size_bytes=len(base64.b64decode(base64_image)),
                request_ip=context.request_ip if context else None,
            )

            result = await client.extract_from_image(
                image_data=base64_image,
                prompt=prompt,
                media_type=media_type,
            )

            # Track usage
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            # Parse VLM response (products without bounding boxes)
            parsed_result = self._parse_response(
                {
                    "content": result.content,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
                page_number,
                image_width=img_width,
                image_height=img_height,
            )

            # Step 2: PaddleOCR detects text regions
            # OPTIMIZATION: Check for pre-cached OCR results first
            ocr_regions = None
            logger.info(f"[VLM-OCR] Checking for cached OCR results for {context.leaflet_id} page {page_number}")
            try:
                from app.workers.tasks import get_cached_ocr_results
                cached_regions = get_cached_ocr_results(context.leaflet_id, page_number)
                if cached_regions is not None:
                    ocr_regions = cached_regions
                    logger.info(f"[VLM-OCR] Using cached OCR results: {len(ocr_regions)} regions for page {page_number}")
                else:
                    logger.warning(f"[VLM-OCR] No cached OCR results for page {page_number}")
            except ImportError as e:
                logger.warning(f"[VLM-OCR] Could not import get_cached_ocr_results: {e}")

            if ocr_regions is None:
                # No cached results - run OCR now
                logger.info(f"[VLM-OCR] Running PaddleOCR on-demand for page {page_number}...")
                ocr_detector = _get_paddle_ocr_detector()
                image_bytes = base64.b64decode(base64_image)
                ocr_regions = ocr_detector.detect_product_regions(
                    image_bytes,
                    image_width=img_width,
                    image_height=img_height,
                )
                logger.info(f"[VLM-OCR] PaddleOCR detected {len(ocr_regions)} product regions")

            # Step 3: Match VLM products to OCR regions
            logger.info(f"[VLM-OCR] Matching step: {len(ocr_regions) if ocr_regions else 0} OCR regions, {len(parsed_result.products)} VLM products")
            if ocr_regions and parsed_result.products:
                # Get OCR detector for matching (needed even if using cached regions)
                ocr_detector = _get_paddle_ocr_detector()
                # CRITICAL: Pass ALL product data for accurate matching
                # The matching algorithm uses prices, product codes, and quantities
                # to find the correct OCR region for each product
                products_dict = [
                    {
                        "product_name": p.product_name,
                        "brand": p.brand,
                        "discounted_price": p.discounted_price,
                        "regular_price": p.regular_price,
                        "product_code": p.product_code,
                        "quantity": p.quantity,
                        "units": p.units,
                        "size": p.size,
                    }
                    for p in parsed_result.products
                ]
                logger.info(f"[VLM-OCR] Calling match_products_to_regions with {len(products_dict)} products and {len(ocr_regions)} regions")

                # Log first few OCR regions for debugging
                for idx, region in enumerate(ocr_regions[:3]):
                    logger.info(f"[VLM-OCR] OCR region {idx}: text='{region.get('combined_text', '')[:50]}...', bbox={region.get('bbox')}")

                matched = ocr_detector.match_products_to_regions(products_dict, ocr_regions)

                # Update product bounding boxes
                matched_count = 0
                for i, match in enumerate(matched):
                    if i < len(parsed_result.products) and "bounding_box" in match:
                        bbox = match["bounding_box"]
                        parsed_result.products[i].bounding_box = BoundingBox(
                            x=bbox["x"],
                            y=bbox["y"],
                            width=bbox["width"],
                            height=bbox["height"],
                        )
                        bbox_source = match.get("bbox_source", "unknown")
                        if bbox_source in ("paddle_ocr", "ocr_text_match"):
                            if "ocr_bbox" not in parsed_result.products[i].uncertainty_flags:
                                parsed_result.products[i].uncertainty_flags.append("ocr_bbox")
                            matched_count += 1
                        logger.debug(f"[VLM-OCR] Product '{parsed_result.products[i].product_name[:30]}' assigned bbox from {bbox_source}")

                logger.info(f"[VLM-OCR] Matching complete: {matched_count}/{len(parsed_result.products)} products matched to OCR regions")

            # Set processing time
            parsed_result.processing_time_ms = int((time.time() - start_time) * 1000)

            # Log success
            self.audit_service.log_extraction_success(
                session_id=session_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=result.cost,
                processing_time_ms=parsed_result.processing_time_ms,
                products_found=parsed_result.product_count,
                user_id=self.user_id,
                leaflet_id=context.leaflet_uuid if context else None,
                request_ip=context.request_ip if context else None,
                response_metadata={
                    'extraction_method': 'ocr_based',
                    'ocr_regions_detected': len(ocr_regions),
                }
            )

            logger.info(
                f"OCR-based extraction: {parsed_result.product_count} products, "
                f"{len(ocr_regions)} OCR regions, {parsed_result.processing_time_ms}ms "
                f"(cost: ${result.cost:.4f})"
            )

            return parsed_result

        except Exception as e:
            logger.error(f"OCR-based extraction failed: {e}", exc_info=True)
            # Fall back to grid-based extraction
            logger.info("Falling back to grid-based extraction")
            return await self.extract_page(image_data, page_number, total_pages, context, image_format)

    def _get_current_client(self):
        """Get the current VLM client based on provider selection."""
        if self._client:
            return self._client
        else:
            raise ValueError(
                "No VLM provider available. Please configure an organization-level VLM provider "
                "in Settings, or contact your administrator to set up platform-level providers."
            )

    def _get_current_provider_id(self) -> Optional[str]:
        """Get current provider ID for logging."""
        if self._current_provider_type == 'organization' and self._organization_provider:
            return str(self._organization_provider.id)
        elif self._current_provider_type == 'platform' and self._platform_provider:
            return str(self._platform_provider.id)
        return None

    def _get_current_model_name(self) -> Optional[str]:
        """Get current model name for logging."""
        if self._current_provider_type == 'organization' and self._organization_provider:
            return self._organization_provider.model_name
        elif self._current_provider_type == 'platform' and self._platform_provider:
            return self._platform_provider.model_name
        return None

    async def extract_leaflet(
        self,
        page_images: List[Union[bytes, str]],
        leaflet_id: str,
        context: Optional[ExtractionContext] = None,
        parallel: bool = True,
        max_concurrent: int = 4,
        verify_completeness: bool = True,
    ) -> ExtractionResult:
        """
        Extract products from all pages in a leaflet with enhanced monitoring.

        Uses card-first extraction: detect card regions via image analysis,
        annotate with numbered boxes, VLM matches products to region numbers,
        then region numbers are mapped to accurate bounding boxes.

        Args:
            page_images: List of page images (bytes or base64)
            leaflet_id: Leaflet identifier
            context: Optional extraction context
            parallel: Process pages in parallel
            max_concurrent: Max concurrent API calls
            verify_completeness: Run verification pass to catch missed products (default True)

        Returns:
            ExtractionResult with all extracted products
        """
        start_time = time.time()
        total_pages = len(page_images)

        if context is None:
            # Try to parse leaflet_id as UUID for audit logging; falls back to None
            _leaflet_uuid = None
            if leaflet_id and leaflet_id != "unknown":
                try:
                    _leaflet_uuid = uuid.UUID(leaflet_id)
                except (ValueError, AttributeError):
                    pass
            context = ExtractionContext(
                leaflet_id=leaflet_id,
                leaflet_uuid=_leaflet_uuid,
                page_count=total_pages,
            )

        result = ExtractionResult(leaflet_id=leaflet_id)

        # Card-first extraction — detect regions, annotate, VLM matches to region numbers
        # With optional verification pass to catch missed products
        if verify_completeness:
            extraction_method = "card_first_with_verification"
            extract_fn = self.extract_page_with_verification
        else:
            extraction_method = "card_first"
            extract_fn = self.extract_page

        logger.info(f"Extraction method: {extraction_method}")

        # Log leaflet extraction start
        if self._user:
            self.audit_service.log_leaflet_extraction_start(
                user_id=self._user.id,
                organization_id=self._user.default_organization_id,
                leaflet_id=context.leaflet_uuid,
                page_count=total_pages,
                provider_type=self._current_provider_type,
                provider_id=self._get_current_provider_id(),
                concurrent_processing=parallel,
                max_concurrent=max_concurrent if parallel else 1,
                request_ip=context.request_ip,
            )

        try:
            if parallel and total_pages > 1:
                # Process pages in parallel with concurrency limit
                semaphore = asyncio.Semaphore(max_concurrent)

                async def extract_with_limit(page_num: int, image: Union[bytes, str]):
                    async with semaphore:
                        return await extract_fn(
                            image_data=image,
                            page_number=page_num,
                            total_pages=total_pages,
                            context=context,
                        )

                tasks = [
                    extract_with_limit(i + 1, img)
                    for i, img in enumerate(page_images)
                    if img is not None
                ]

                page_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, page_result in enumerate(page_results):
                    if isinstance(page_result, Exception):
                        logger.error(f"Page {i+1} extraction failed: {page_result}")
                        result.add_error(f"Page {i+1}: {str(page_result)}")
                    else:
                        result.add_page_result(page_result)
            else:
                # Process pages sequentially
                for i, image in enumerate(page_images):
                    if image is None:
                        continue
                    try:
                        page_result = await extract_fn(
                            image_data=image,
                            page_number=i + 1,
                            total_pages=total_pages,
                            context=context,
                        )
                        result.add_page_result(page_result)
                    except Exception as e:
                        logger.error(f"Page {i+1} extraction failed: {e}")
                        result.add_error(f"Page {i+1}: {str(e)}")

            # Set totals
            result.input_tokens = self.total_input_tokens
            result.output_tokens = self.total_output_tokens
            result.processing_time_ms = int((time.time() - start_time) * 1000)

            # Log successful leaflet extraction
            if self._user:
                self.audit_service.log_leaflet_extraction_success(
                    leaflet_id=context.leaflet_uuid,
                    pages_processed=len(result.page_results),
                    total_products=result.total_products,
                    total_input_tokens=result.input_tokens,
                    total_output_tokens=result.output_tokens,
                    total_cost=self.total_cost,
                    processing_time_ms=result.processing_time_ms,
                    extraction_metadata={
                        'parallel_processing': parallel,
                        'max_concurrent': max_concurrent if parallel else 1,
                        'provider_type': self._current_provider_type,
                        'error_message': result.error_message,
                    },
                    request_ip=context.request_ip,
                )

            logger.info(
                f"Leaflet extraction complete: {result.total_products} products, "
                f"{len(result.page_results)} pages, {result.processing_time_ms}ms, "
                f"${self.total_cost:.4f} total cost using {self._current_provider_type} provider"
            )

            return result

        except Exception as e:
            logger.error(f"Leaflet extraction failed: {e}", exc_info=True)

            # Log leaflet extraction failure
            if self._user:
                self.audit_service.log_leaflet_extraction_failure(
                    leaflet_id=context.leaflet_uuid,
                    error_message=str(e),
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    pages_attempted=len([img for img in page_images if img is not None]),
                    request_ip=context.request_ip,
                )

            raise

    # Copy all the existing helper methods from the original implementation
    # (keeping them exactly the same for compatibility)

    async def _prepare_image(
        self,
        image_data: Union[bytes, str],
        image_format: str,
    ) -> tuple:
        """Prepare image for API call (legacy method, use _prepare_image_with_dimensions instead)."""
        # If already base64, use directly
        if isinstance(image_data, str):
            base64_image = image_data
        else:
            # Encode bytes to base64
            base64_image = base64.b64encode(image_data).decode()

        # Determine media type
        format_to_mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        media_type = format_to_mime.get(image_format.lower(), "image/png")

        return base64_image, media_type

    async def _prepare_image_with_dimensions(
        self,
        image_data: Union[bytes, str],
        image_format: str,
        max_dimension: int = 1500,
        jpeg_quality: int = 85,
    ) -> tuple:
        """
        Prepare image for API call with compression for faster processing.

        Optimizations applied:
        1. Resize large images to max_dimension (reduces API latency)
        2. Convert to JPEG for smaller file size (50-70% reduction)
        3. Return BOTH original and prepared dimensions for coordinate scaling

        Args:
            image_data: Image as bytes or base64 string
            image_format: Image format (png, jpg, etc.)
            max_dimension: Maximum pixel dimension (default 1500)
            jpeg_quality: JPEG compression quality (default 85)

        Returns:
            Tuple of (base64_image, media_type, original_width, original_height,
                       prepared_width, prepared_height)
        """
        # Default dimensions (A4 at 300 DPI)
        original_width, original_height = 2480, 3508
        prepared_width, prepared_height = original_width, original_height

        try:
            # Get image bytes
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data

            # Open image
            img = Image.open(BytesIO(image_bytes))
            original_width, original_height = img.size
            prepared_width, prepared_height = original_width, original_height
            original_size_kb = len(image_bytes) / 1024

            # OPTIMIZATION 1: Resize if too large
            if max(original_width, original_height) > max_dimension:
                # Calculate new dimensions maintaining aspect ratio
                if original_width > original_height:
                    new_width = max_dimension
                    new_height = int(original_height * (max_dimension / original_width))
                else:
                    new_height = max_dimension
                    new_width = int(original_width * (max_dimension / original_height))

                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                prepared_width, prepared_height = new_width, new_height
                logger.debug(
                    f"Resized image: {original_width}x{original_height} -> {new_width}x{new_height}"
                )

            # OPTIMIZATION 2: Convert to JPEG for smaller size
            # Convert RGBA to RGB if needed (JPEG doesn't support alpha)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Save as JPEG to buffer
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=jpeg_quality, optimize=True)
            compressed_bytes = buffer.getvalue()
            compressed_size_kb = len(compressed_bytes) / 1024

            # Encode to base64
            base64_image = base64.b64encode(compressed_bytes).decode()

            # Log compression stats
            reduction_pct = (1 - compressed_size_kb / original_size_kb) * 100 if original_size_kb > 0 else 0
            logger.info(
                f"Image optimized: {original_size_kb:.0f}KB -> {compressed_size_kb:.0f}KB "
                f"({reduction_pct:.0f}% reduction), "
                f"prepared: {prepared_width}x{prepared_height}"
            )

            img.close()

            # Always return JPEG media type since we converted
            return base64_image, "image/jpeg", original_width, original_height, prepared_width, prepared_height

        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            # Fallback to original image without compression
            if isinstance(image_data, str):
                base64_image = image_data
            else:
                base64_image = base64.b64encode(image_data).decode()

            format_to_mime = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
            }
            media_type = format_to_mime.get(image_format.lower(), "image/png")

            return base64_image, media_type, original_width, original_height, prepared_width, prepared_height

    def _parse_response(
        self,
        response: Dict[str, Any],
        page_number: int,
        image_width: int = 2480,
        image_height: int = 3508,
    ) -> PageExtractionResult:
        """
        Parse VLM response into structured result.

        Args:
            response: Raw response from VLM
            page_number: Page number being parsed
            image_width: Image width for bounding box validation
            image_height: Image height for bounding box validation

        Returns:
            PageExtractionResult with parsed products
        """
        content = response.get("content", "")

        # Extract JSON from response
        json_data = self._extract_json(content)

        if json_data is None:
            logger.error(f"Failed to parse JSON from response: {content[:500]}")
            return PageExtractionResult(
                page_number=page_number,
                products=[],
                page_notes="Failed to parse VLM response",
                input_tokens=response.get("input_tokens", 0),
                output_tokens=response.get("output_tokens", 0),
            )

        # Parse products with image dimensions for validation
        products = []
        raw_products = json_data.get("products", [])

        logger.info(f"Page {page_number}: Parsing {len(raw_products)} products from VLM response")

        for idx, raw_product in enumerate(raw_products):
            try:
                product = self._parse_product(raw_product, image_width, image_height)
                if product:
                    # CRITICAL: Set source_page on each product for correct page association
                    # This ensures products stay associated with their correct page even after
                    # reconciliation (which can merge/modify products across pages)
                    product.source_page = page_number
                    products.append(product)
                    bbox_info = ""
                    if product.bounding_box:
                        bbox_info = f"bbox=({product.bounding_box.x},{product.bounding_box.y},{product.bounding_box.width}x{product.bounding_box.height})"
                    logger.debug(
                        f"  Product {idx+1} (page {page_number}): '{product.product_name[:40]}' {bbox_info}"
                    )
            except Exception as e:
                logger.warning(f"Failed to parse product {idx+1}: {e}")
                continue

        # Also parse unmatched_products (products the VLM found outside any region)
        unmatched_raw = json_data.get("unmatched_products", [])
        if unmatched_raw:
            logger.info(
                f"Page {page_number}: {len(unmatched_raw)} unmatched products reported by VLM"
            )
            for idx, raw_product in enumerate(unmatched_raw):
                try:
                    # Ensure unmatched products have empty region_numbers
                    raw_product["region_numbers"] = []
                    product = self._parse_product(raw_product, image_width, image_height)
                    if product:
                        product.source_page = page_number
                        if "region_uncertain" not in (product.uncertainty_flags or []):
                            flags = product.uncertainty_flags or []
                            flags.append("unmatched_region")
                            product.uncertainty_flags = flags
                        products.append(product)
                        logger.debug(
                            f"  Unmatched product {idx+1} (page {page_number}): "
                            f"'{product.product_name[:40]}' (no region)"
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse unmatched product {idx+1}: {e}")

        logger.info(f"Page {page_number}: Successfully parsed {len(products)} products")

        return PageExtractionResult(
            page_number=json_data.get("page_number", page_number),
            products=products,
            page_notes=json_data.get("page_notes"),
            continuation_detected=json_data.get("continuation_detected", False),
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
        )

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from VLM response content."""
        # Try direct JSON parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract from code block
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue

        return None

    def _parse_product(
        self,
        raw: Dict[str, Any],
        image_width: int = 2480,
        image_height: int = 3508,
    ) -> Optional[ExtractedProduct]:
        """
        Parse a single product from raw VLM output.

        Handles both card-first (region_numbers) and legacy (bounding_box) formats.

        Args:
            raw: Raw product data from VLM
            image_width: Page image width for validation
            image_height: Page image height for validation

        Returns:
            ExtractedProduct or None if invalid
        """
        product_name = raw.get("product_name")
        if not product_name or not product_name.strip():
            return None

        # Parse region_numbers (card-first pipeline)
        region_numbers = raw.get("region_numbers", [])
        if not isinstance(region_numbers, list):
            region_numbers = []
        # Ensure all entries are ints
        region_numbers = [int(n) for n in region_numbers if isinstance(n, (int, float))]

        # Bounding box: in card-first mode, bbox is assigned later from region_map.
        # For backward compatibility, also try to parse bounding_box directly.
        bounding_box = None
        if not region_numbers:
            bbox_data = raw.get("bounding_box")
            if bbox_data and isinstance(bbox_data, dict):
                try:
                    x = int(bbox_data.get("x", 0))
                    y = int(bbox_data.get("y", 0))
                    width = int(bbox_data.get("width", 0))
                    height = int(bbox_data.get("height", 0))

                    if width > 0 and height > 0:
                        x, y, width, height = self._validate_and_fix_bbox(
                            x, y, width, height, image_width, image_height, product_name
                        )
                        bounding_box = BoundingBox(x=x, y=y, width=width, height=height)
                except (ValueError, TypeError) as e:
                    logger.debug(f"No valid bounding box for '{product_name}': {e}")

        # Log status
        if region_numbers:
            logger.debug(
                f"Product '{product_name[:30]}...' region_numbers={region_numbers} "
                f"(bbox assigned later from card regions)"
            )
        elif bounding_box:
            logger.debug(
                f"Product '{product_name[:30]}...' legacy bbox: "
                f"x={bounding_box.x}, y={bounding_box.y}, "
                f"w={bounding_box.width}, h={bounding_box.height}"
            )
        else:
            logger.warning(
                f"Product '{product_name[:30]}...' has no region_numbers and no bounding box"
            )

        # Parse field confidence
        field_conf_data = raw.get("field_confidence", {})
        field_confidence = None
        if field_conf_data:
            try:
                field_confidence = FieldConfidence(**field_conf_data)
            except Exception:
                pass

        # Parse category fields
        suggested_category = raw.get("suggested_category")
        category_confidence = self._parse_float(raw.get("category_confidence"))
        category_alternatives = raw.get("category_alternatives")

        # Validate and normalize category_alternatives
        # VLM may return list of strings or list of dicts - normalize to list of dicts
        if category_alternatives:
            if not isinstance(category_alternatives, list):
                category_alternatives = None
            else:
                normalized_alts = []
                for alt in category_alternatives:
                    if isinstance(alt, str):
                        # Convert string to dict format
                        normalized_alts.append({"name": alt, "confidence": None})
                    elif isinstance(alt, dict):
                        normalized_alts.append(alt)
                    # Skip invalid entries
                category_alternatives = normalized_alts if normalized_alts else None

        # Build product
        try:
            product = ExtractedProduct(
                bounding_box=bounding_box,
                brand=raw.get("brand"),
                product_code=raw.get("product_code"),
                product_name=product_name,
                quantity=self._parse_float(raw.get("quantity")),
                units=raw.get("units"),
                size=raw.get("size"),
                regular_price=self._parse_float(raw.get("regular_price")),
                discounted_price=self._parse_float(raw.get("discounted_price")),
                discount_percentage=self._parse_float(raw.get("discount_percentage")),
                currency=raw.get("currency"),
                product_id=raw.get("product_id"),
                promotional_info=raw.get("promotional_info"),
                suggested_category=suggested_category,
                category_confidence=category_confidence,
                category_alternatives=category_alternatives if category_alternatives else None,
                confidence_score=self._parse_float(raw.get("confidence_score", 0.8)) or 0.8,
                field_confidence=field_confidence,
                uncertainty_flags=raw.get("uncertainty_flags", []),
            )
            # Store region_numbers as transient attribute for card-first pipeline.
            # extract_page() reads this to assign bounding boxes from detected regions.
            product._region_numbers = region_numbers
            return product
        except Exception as e:
            logger.warning(f"Failed to create ExtractedProduct: {e}")
            return None

    def _validate_and_fix_bbox(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        image_width: int,
        image_height: int,
        product_name: str,
    ) -> tuple:
        """
        Validate and fix bounding box coordinates.

        Ensures the bounding box is within image bounds and has sensible dimensions.

        Args:
            x, y, width, height: Original bounding box values
            image_width, image_height: Image dimensions
            product_name: Product name for logging

        Returns:
            Tuple of (x, y, width, height) after validation/fixing
        """
        original = (x, y, width, height)
        fixed = False

        # Fix negative coordinates
        if x < 0:
            x = 0
            fixed = True
        if y < 0:
            y = 0
            fixed = True

        # Fix coordinates beyond image bounds
        if x >= image_width:
            x = image_width - 100
            fixed = True
        if y >= image_height:
            y = image_height - 100
            fixed = True

        # Ensure minimum dimensions (typical product card is at least 150x200)
        min_width = max(150, image_width // 10)
        min_height = max(200, image_height // 10)

        if width < min_width:
            width = min_width
            fixed = True
        if height < min_height:
            height = min_height
            fixed = True

        # Ensure bounding box doesn't extend beyond image
        if x + width > image_width:
            width = image_width - x
            fixed = True
        if y + height > image_height:
            height = image_height - y
            fixed = True

        # Log if we had to fix anything
        if fixed:
            logger.info(
                f"Fixed bounding box for '{product_name[:30]}': "
                f"original={original} -> fixed=({x}, {y}, {width}, {height})"
            )

        return x, y, width, height

    def _parse_float(self, value: Any) -> Optional[float]:
        """Safely parse a float value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider being used."""
        if self._current_provider_type == 'organization' and self._organization_provider:
            return {
                "type": "organization",
                "provider_type": self._organization_provider.provider_type.value,
                "model": self._organization_provider.model_name,
                "provider_name": self._organization_provider.name,
                "provider_id": str(self._organization_provider.id),
                "is_user_configured": True,
                "budget_remaining": self._organization_provider.monthly_budget - self._organization_provider.current_month_spent if self._organization_provider.monthly_budget else None,
            }
        elif self._current_provider_type == 'platform' and self._platform_provider:
            return {
                "type": "platform",
                "provider_type": self._platform_provider.provider_type.value,
                "model": self._platform_provider.model_name,
                "provider_name": self._platform_provider.name,
                "provider_id": str(self._platform_provider.id),
                "priority": self._platform_provider.priority,
                "is_user_configured": False,
                "managed_by": "platform",
                "budget_remaining": self._platform_provider.daily_budget - self._platform_provider.current_day_spent if self._platform_provider.daily_budget else None,
            }
        else:
            return {
                "type": "none",
                "is_user_configured": False,
                "message": "No VLM provider configured. Configure organization providers in Settings or contact admin for platform providers.",
            }

    async def verify_bounding_boxes(
        self,
        image_data: Union[bytes, str],
        image_format: str,
        products: List[ExtractedProduct],
        page_width: int = 2480,
        page_height: int = 3508,
    ) -> List[ExtractedProduct]:
        """
        Pass 2: Verify and correct bounding boxes using visual verification.

        This method:
        1. Draws bounding boxes on the image
        2. Sends annotated image to VLM for verification
        3. Applies corrections to products

        Args:
            image_data: Original page image
            image_format: Image format (png, jpg, etc.)
            products: Products with bounding boxes from Pass 1
            page_width: Page width in pixels
            page_height: Page height in pixels

        Returns:
            List of products with verified/corrected bounding boxes
        """
        if not products:
            return products

        # Skip verification if no products have bounding boxes
        products_with_bbox = [p for p in products if p.bounding_box]
        if not products_with_bbox:
            logger.info("No products with bounding boxes to verify")
            return products

        try:
            # Import visualizer here to avoid circular imports
            from app.core.image_processing.bbox_visualizer import get_bbox_visualizer

            visualizer = get_bbox_visualizer()

            # Get image bytes
            if isinstance(image_data, str):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data

            # Convert products to dict format for visualizer
            products_dict = []
            for p in products:
                product_dict = {
                    "product_name": p.product_name,
                    "bounding_box": {
                        "x": p.bounding_box.x if p.bounding_box else 0,
                        "y": p.bounding_box.y if p.bounding_box else 0,
                        "width": p.bounding_box.width if p.bounding_box else 0,
                        "height": p.bounding_box.height if p.bounding_box else 0,
                    } if p.bounding_box else None
                }
                products_dict.append(product_dict)

            # Draw bounding boxes on image
            annotated_image_bytes = visualizer.draw_bboxes(
                image_bytes,
                products_dict,
                output_format="bytes"
            )

            # Prepare annotated image for VLM
            annotated_base64 = base64.b64encode(annotated_image_bytes).decode()
            media_type = "image/png"

            # Build verification prompt
            verification_prompt = self.prompt_builder.build_bbox_verification_prompt(
                products_dict,
                page_width=page_width,
                page_height=page_height,
            )

            # Ensure we have a client
            if not self._client:
                logger.warning("No VLM client available for verification")
                return products

            # Send to VLM for verification
            logger.info(f"Starting bounding box verification for {len(products)} products")
            start_time = time.time()

            result = await self._client.extract_from_image(
                image_data=annotated_base64,
                prompt=verification_prompt,
                media_type=media_type,
            )

            verification_time_ms = int((time.time() - start_time) * 1000)

            # Track tokens/cost
            self.total_input_tokens += result.input_tokens
            self.total_output_tokens += result.output_tokens
            self.total_cost += result.cost

            logger.info(
                f"Verification completed in {verification_time_ms}ms, "
                f"cost: ${result.cost:.4f}"
            )

            # Parse verification response
            content = result.content
            verification_data = self._parse_verification_response(content)

            if not verification_data:
                logger.warning("Failed to parse verification response")
                return products

            # Apply corrections
            corrected_products = self._apply_bbox_corrections(
                products, verification_data, page_width, page_height
            )

            return corrected_products

        except Exception as e:
            logger.error(f"Bounding box verification failed: {e}", exc_info=True)
            # Return original products if verification fails
            return products

    def _parse_verification_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse the verification response JSON."""
        try:
            # Try to extract JSON from the response
            content = content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            # Find JSON object
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())

            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse verification JSON: {e}")
            return None

    def _apply_bbox_corrections(
        self,
        products: List[ExtractedProduct],
        verification_data: Dict[str, Any],
        page_width: int,
        page_height: int,
    ) -> List[ExtractedProduct]:
        """Apply bounding box corrections from verification."""
        verifications = verification_data.get("verifications", [])
        missed_products = verification_data.get("missed_products", [])

        corrections_applied = 0

        # Apply corrections to existing products
        for verification in verifications:
            idx = verification.get("product_index", 0) - 1  # Convert to 0-indexed
            if idx < 0 or idx >= len(products):
                continue

            if not verification.get("is_correct", True):
                corrected_bbox = verification.get("corrected_bbox")
                if corrected_bbox:
                    # Validate and apply correction
                    x, y, width, height = self._validate_and_fix_bbox(
                        corrected_bbox.get("x", 0),
                        corrected_bbox.get("y", 0),
                        corrected_bbox.get("width", 0),
                        corrected_bbox.get("height", 0),
                        page_width,
                        page_height,
                        products[idx].product_name or "Unknown",
                    )

                    products[idx].bounding_box = BoundingBox(
                        x=x, y=y, width=width, height=height
                    )
                    corrections_applied += 1

                    logger.debug(
                        f"Corrected bbox for product {idx + 1}: "
                        f"{verification.get('issue', 'no reason given')}"
                    )

        # Log missed products (could add them in a future enhancement)
        if missed_products:
            logger.info(f"Verification detected {len(missed_products)} missed products")
            for missed in missed_products:
                logger.debug(
                    f"Missed product: {missed.get('product_name', 'Unknown')} "
                    f"at {missed.get('suggested_bbox')}"
                )

        logger.info(
            f"Verification complete: {corrections_applied} corrections applied, "
            f"{len(missed_products)} missed products detected"
        )

        return products


# Legacy alias for backward compatibility
UserAwareVLMExtractor = VLMExtractorService