"""Complete initial migration - all tables for fresh deployment

Revision ID: 001_complete_initial
Revises:
Create Date: 2026-01-15 00:00:00.000000

This is a consolidated migration that creates the complete database schema
for the Leaflet Extraction Platform. It combines all previous migrations into
a single file for fresh deployments.

Includes:
- Core user and authentication tables
- Multi-organization support
- Leaflet and product tables with categories
- VLM provider management (user and platform level)
- Webhooks and analytics
- Retailers
- System-wide product categories
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision: str = '001_complete_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create complete database schema."""

    # =========================================================================
    # STEP 1: Create all ENUM types
    # =========================================================================

    # Organization enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organizationtype AS ENUM ('BUSINESS', 'PERSONAL');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organizationstatus AS ENUM ('PENDING_APPROVAL', 'ACTIVE', 'SUSPENDED', 'DELETED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE organizationrole AS ENUM ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invitationstatus AS ENUM ('PENDING', 'ACCEPTED', 'EXPIRED', 'REVOKED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deletionrequesttype AS ENUM ('ORGANIZATION', 'USER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deletionrequeststatus AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Platform VLM enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE platformvlmprovidertype AS ENUM ('anthropic', 'openai', 'google', 'azure_openai', 'aws_bedrock', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationtype AS ENUM ('budget_warning', 'provider_failover', 'system_alert', 'maintenance', 'security_alert', 'feature_update', 'usage_report', 'api_key_expiry', 'organization_update', 'user_action_required');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationseverity AS ENUM ('info', 'success', 'warning', 'error', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationsource AS ENUM ('budget_monitor', 'failover_system', 'manual', 'system', 'webhook', 'scheduled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE alerttype AS ENUM ('warning', 'critical', 'exhausted', 'rate_limit');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE alertperiod AS ENUM ('daily', 'monthly', 'hourly');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE auditeventtype AS ENUM ('extraction', 'failover', 'budget_warning', 'budget_exhausted', 'rate_limit_hit', 'provider_error', 'key_created', 'key_updated', 'key_deleted', 'key_tested', 'config_changed', 'usage_reset');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE auditeventstatus AS ENUM ('success', 'failure', 'warning', 'error', 'partial');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE errorcategory AS ENUM ('authentication', 'rate_limit', 'budget_limit', 'network', 'timeout', 'validation', 'provider_error', 'system_error');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE backuptype AS ENUM ('manual', 'scheduled', 'pre_deletion', 'pre_update', 'migration', 'emergency');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE backupstatus AS ENUM ('active', 'archived', 'expired', 'corrupted');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # =========================================================================
    # STEP 2: Create users table (foundation)
    # =========================================================================

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('api_key', sa.String(64), nullable=True),
        sa.Column('api_key_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('login_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('settings', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('default_organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('api_key'),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_users_api_key', 'users', ['api_key'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])

    # =========================================================================
    # STEP 3: Create organizations tables
    # =========================================================================

    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('organization_type', postgresql.ENUM('BUSINESS', 'PERSONAL', name='organizationtype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING_APPROVAL', 'ACTIVE', 'SUSPENDED', 'DELETED', name='organizationstatus', create_type=False), nullable=False, server_default='PENDING_APPROVAL'),
        sa.Column('business_name', sa.String(300), nullable=True),
        sa.Column('business_email', sa.String(255), nullable=False),
        sa.Column('business_phone', sa.String(50), nullable=True),
        sa.Column('business_address', sa.Text(), nullable=True),
        sa.Column('tax_id', sa.String(100), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('settings', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('requested_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_org_status_created', 'organizations', ['status', 'created_at'])
    op.create_index('idx_org_type_status', 'organizations', ['organization_type', 'status'])
    op.create_index('ix_organizations_business_email', 'organizations', ['business_email'])

    # Add FK from users to organizations (now that organizations exists)
    op.create_foreign_key('fk_users_default_organization', 'users', 'organizations', ['default_organization_id'], ['id'], ondelete='SET NULL')
    op.create_index('idx_users_default_org', 'users', ['default_organization_id'])

    op.create_table(
        'organization_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', postgresql.ENUM('OWNER', 'ADMIN', 'MEMBER', 'VIEWER', name='organizationrole', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_organization_user'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_org_user_role', 'organization_users', ['organization_id', 'role'])
    op.create_index('idx_org_user_active', 'organization_users', ['organization_id', 'is_active'])
    op.create_index('idx_user_orgs', 'organization_users', ['user_id', 'organization_id'])

    op.create_table(
        'organization_invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', postgresql.ENUM('OWNER', 'ADMIN', 'MEMBER', 'VIEWER', name='organizationrole', create_type=False), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'ACCEPTED', 'EXPIRED', 'REVOKED', name='invitationstatus', create_type=False), nullable=False, server_default='PENDING'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['accepted_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_invitation_email_status', 'organization_invitations', ['email', 'status'])
    op.create_index('idx_invitation_org_status', 'organization_invitations', ['organization_id', 'status'])
    op.create_index('idx_invitation_expires', 'organization_invitations', ['expires_at', 'status'])
    op.create_index('ix_organization_invitations_token', 'organization_invitations', ['token'])

    op.create_table(
        'deletion_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('request_type', postgresql.ENUM('ORGANIZATION', 'USER', name='deletionrequesttype', create_type=False), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('requested_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', name='deletionrequeststatus', create_type=False), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_deletion_type_status', 'deletion_requests', ['request_type', 'status'])
    op.create_index('idx_deletion_org_status', 'deletion_requests', ['organization_id', 'status'])
    op.create_index('idx_deletion_created', 'deletion_requests', ['status', 'created_at'])

    # =========================================================================
    # STEP 4: Create retailers table
    # =========================================================================

    op.create_table(
        'retailers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('country', sa.String(2), nullable=True, comment='Default country code (ISO 3166-1 alpha-2)'),
        sa.Column('currency', sa.String(3), nullable=True, comment='Default currency code (ISO 4217)'),
        sa.Column('language', sa.String(5), nullable=True, comment='Default language code (ISO 639-1)'),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True, comment='Optional external identifier for integration with other systems'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_retailer_org_name'),
    )
    op.create_index('idx_retailer_name_lower', 'retailers', ['name'])
    op.create_index('idx_retailer_org_active', 'retailers', ['organization_id', 'is_active'])
    op.create_index('ix_retailers_id', 'retailers', ['id'])
    op.create_index('ix_retailers_is_active', 'retailers', ['is_active'])
    op.create_index('ix_retailers_name', 'retailers', ['name'])
    op.create_index('ix_retailers_organization_id', 'retailers', ['organization_id'])
    op.create_index('ix_retailers_external_id', 'retailers', ['external_id'])

    # =========================================================================
    # STEP 5: Create API keys table
    # =========================================================================

    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('rate_limit', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('daily_limit', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_ip', sa.String(45), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requests_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_reset_date', sa.Date(), nullable=True),
        sa.Column('allowed_ips', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('allowed_origins', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('metadata_', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_api_keys_id', 'api_keys', ['id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_is_active', 'api_keys', ['is_active'])
    op.create_index('idx_api_keys_organization', 'api_keys', ['organization_id'])

    # =========================================================================
    # STEP 6: Create leaflets table
    # =========================================================================

    op.create_table(
        'leaflets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('leaflet_id', sa.String(50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('retailer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=False, server_default='application/pdf'),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('pdf_type', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_step', sa.String(50), nullable=True),
        sa.Column('retailer', sa.String(255), nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('language', sa.String(5), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_path', sa.String(500), nullable=True),
        sa.Column('storage_bucket', sa.String(100), nullable=True),
        sa.Column('overall_confidence', sa.Float(), nullable=True),
        sa.Column('auto_approved_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('review_required_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('api_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processing_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('leaflet_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['retailer_id'], ['retailers.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_leaflets_id', 'leaflets', ['id'])
    op.create_index('ix_leaflets_leaflet_id', 'leaflets', ['leaflet_id'])
    op.create_index('ix_leaflets_user_id', 'leaflets', ['user_id'])
    op.create_index('ix_leaflets_status', 'leaflets', ['status'])
    op.create_index('ix_leaflets_retailer', 'leaflets', ['retailer'])
    op.create_index('ix_leaflets_country', 'leaflets', ['country'])
    op.create_index('ix_leaflets_file_hash', 'leaflets', ['file_hash'])
    op.create_index('ix_leaflets_created_at', 'leaflets', ['created_at'])
    op.create_index('idx_leaflets_organization', 'leaflets', ['organization_id'])
    op.create_index('idx_leaflet_retailer', 'leaflets', ['retailer_id'])

    # =========================================================================
    # STEP 7: Create leaflet_pages table
    # =========================================================================

    op.create_table(
        'leaflet_pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('leaflet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('thumbnail_path', sa.String(500), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(10), nullable=False, server_default='PNG'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('products_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extraction_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('extraction_confidence', sa.Float(), nullable=True),
        sa.Column('page_notes', sa.Text(), nullable=True),
        sa.Column('continuation_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['leaflet_id'], ['leaflets.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_leaflet_pages_id', 'leaflet_pages', ['id'])
    op.create_index('ix_leaflet_pages_leaflet_id', 'leaflet_pages', ['leaflet_id'])

    # =========================================================================
    # STEP 8: Create products table
    # =========================================================================

    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('leaflet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('brand', sa.String(200), nullable=True),
        sa.Column('product_code', sa.String(100), nullable=True),
        sa.Column('product_name', sa.Text(), nullable=False),
        sa.Column('product_id', sa.String(100), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('units', sa.String(20), nullable=True),
        sa.Column('size', sa.String(50), nullable=True),
        sa.Column('regular_price', sa.Float(), nullable=True),
        sa.Column('discounted_price', sa.Float(), nullable=True),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('promotional_info', sa.Text(), nullable=True),
        # Category fields
        sa.Column('suggested_category', sa.String(100), nullable=True, comment='AI-suggested product category (immutable after extraction)'),
        sa.Column('category', sa.String(100), nullable=True, comment='User-confirmed/corrected category'),
        sa.Column('category_confidence', sa.Float(), nullable=True, comment='Category confidence score (0.0 to 1.0)'),
        sa.Column('category_alternatives', postgresql.JSONB(), nullable=True, comment='Alternative category suggestions with confidence scores'),
        # Bounding box
        sa.Column('bbox_x', sa.Integer(), nullable=False),
        sa.Column('bbox_y', sa.Integer(), nullable=False),
        sa.Column('bbox_width', sa.Integer(), nullable=False),
        sa.Column('bbox_height', sa.Integer(), nullable=False),
        # Image storage
        sa.Column('image_storage_type', sa.String(10), nullable=True),
        sa.Column('image_base64', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('image_format', sa.String(10), nullable=True),
        sa.Column('image_width', sa.Integer(), nullable=True),
        sa.Column('image_height', sa.Integer(), nullable=True),
        sa.Column('image_size_bytes', sa.Integer(), nullable=True),
        sa.Column('image_quality_score', sa.Float(), nullable=True),
        # Confidence and validation
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('field_confidence', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('uncertainty_flags', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('review_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('review_priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('validation_errors', postgresql.JSONB(), nullable=False, server_default='[]'),
        # Correction tracking
        sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('original_data', postgresql.JSONB(), nullable=True),
        sa.Column('correction_type', sa.String(50), nullable=True),
        sa.Column('is_split_product', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('merged_from', postgresql.JSONB(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['leaflet_id'], ['leaflets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_products_id', 'products', ['id'])
    op.create_index('ix_products_leaflet_id', 'products', ['leaflet_id'])
    op.create_index('ix_products_page_number', 'products', ['page_number'])
    op.create_index('ix_products_brand', 'products', ['brand'])
    op.create_index('ix_products_product_code', 'products', ['product_code'])
    op.create_index('ix_products_product_id', 'products', ['product_id'])
    op.create_index('ix_products_review_status', 'products', ['review_status'])
    op.create_index('ix_products_review_priority', 'products', ['review_priority'])
    op.create_index('ix_products_created_at', 'products', ['created_at'])
    op.create_index('idx_products_organization', 'products', ['organization_id'])
    op.create_index('ix_products_suggested_category', 'products', ['suggested_category'])
    op.create_index('ix_products_category', 'products', ['category'])

    # =========================================================================
    # STEP 9: Create product_reviews table
    # =========================================================================

    op.create_table(
        'product_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('previous_data', postgresql.JSONB(), nullable=True),
        sa.Column('new_data', postgresql.JSONB(), nullable=True),
        sa.Column('changed_fields', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_product_reviews_id', 'product_reviews', ['id'])
    op.create_index('ix_product_reviews_product_id', 'product_reviews', ['product_id'])
    op.create_index('ix_product_reviews_reviewer_id', 'product_reviews', ['reviewer_id'])

    # =========================================================================
    # STEP 10: Create product_categories table (system-wide)
    # =========================================================================

    op.create_table(
        'product_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed description with include/exclude rules for AI'),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Parent category for hierarchical structure'),
        sa.Column('is_fallback', sa.Boolean(), nullable=False, server_default='false', comment='True if this is a fallback/parent category'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['product_categories.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_product_categories_id', 'product_categories', ['id'])
    op.create_index('ix_product_categories_name', 'product_categories', ['name'], unique=True)
    op.create_index('ix_product_categories_is_active', 'product_categories', ['is_active'])
    op.create_index('ix_product_categories_is_fallback', 'product_categories', ['is_fallback'])
    op.create_index('ix_product_categories_parent_id', 'product_categories', ['parent_id'])
    op.create_index('idx_category_active', 'product_categories', ['is_active', 'sort_order'])
    op.create_index('idx_category_parent', 'product_categories', ['parent_id', 'sort_order'])

    # =========================================================================
    # STEP 11: Create VLM providers table (user-level)
    # =========================================================================

    op.create_table(
        'vlm_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),  # Nullable for org-scoped
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('api_endpoint', sa.String(500), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='8192'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.1'),
        sa.Column('config', postgresql.JSONB(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('monthly_budget', sa.Float(), nullable=True),
        sa.Column('total_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_month_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_vlm_providers_user_id', 'vlm_providers', ['user_id'])
    op.create_index('ix_vlm_providers_is_default', 'vlm_providers', ['user_id', 'is_default'])
    op.create_index('idx_vlm_providers_organization', 'vlm_providers', ['organization_id'])

    # =========================================================================
    # STEP 12: Create VLM models table
    # =========================================================================

    op.create_table(
        'vlm_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='8192'),
        sa.Column('context_window', sa.Integer(), nullable=True),
        sa.Column('temperature_default', sa.Float(), nullable=False, server_default='0.1'),
        sa.Column('input_cost_per_1m', sa.Float(), nullable=False, server_default='3.0'),
        sa.Column('output_cost_per_1m', sa.Float(), nullable=False, server_default='15.0'),
        sa.Column('supports_vision', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('supports_tools', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_deprecated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deprecation_date', sa.DateTime(), nullable=True),
        sa.Column('replacement_model_id', sa.String(100), nullable=True),
        sa.Column('release_date', sa.DateTime(), nullable=True),
        sa.Column('capabilities', postgresql.JSONB(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_type', 'model_id', name='uq_vlm_model_provider_model'),
    )
    op.create_index('ix_vlm_models_provider_type', 'vlm_models', ['provider_type'])
    op.create_index('ix_vlm_models_model_id', 'vlm_models', ['model_id'])
    op.create_index('ix_vlm_models_is_active', 'vlm_models', ['is_active'])

    # Seed default VLM models
    op.execute("""
        INSERT INTO vlm_models (provider_type, model_id, display_name, description, max_tokens, context_window, temperature_default, input_cost_per_1m, output_cost_per_1m, supports_vision, supports_tools, is_default, is_active, sort_order)
        VALUES
        -- Anthropic models
        ('anthropic', 'claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5', 'Latest Claude Sonnet model with excellent vision and reasoning capabilities', 16384, 200000, 0.1, 3.0, 15.0, true, true, true, true, 10),
        ('anthropic', 'claude-opus-4-5-20251124', 'Claude Opus 4.5', 'Most powerful Claude model for complex extraction tasks', 16384, 200000, 0.1, 15.0, 75.0, true, true, false, true, 20),

        -- OpenAI models
        ('openai', 'gpt-4o-2025-03-26', 'GPT-4o (March 2025)', 'Latest GPT-4o model with enhanced vision capabilities', 8192, 128000, 0.1, 2.5, 10.0, true, true, true, true, 10),
        ('openai', 'gpt-4o-mini', 'GPT-4o Mini', 'Cost-effective model for simpler extraction tasks', 4096, 128000, 0.1, 0.15, 0.6, true, true, false, true, 20),

        -- Google models
        ('google', 'gemini-2.5-pro', 'Gemini 2.5 Pro', 'Latest stable Gemini model with very large context window', 1000000, 1000000, 0.1, 1.25, 5.0, true, true, true, true, 10),
        ('google', 'gemini-2.0-flash', 'Gemini 2.0 Flash', 'Fast and cost-effective Gemini model', 8192, 1000000, 0.1, 0.075, 0.3, true, true, false, true, 20),

        -- Azure OpenAI models
        ('azure_openai', 'gpt-4o-2025-03-26', 'GPT-4o (Azure, March 2025)', 'GPT-4o latest deployed on Azure OpenAI Service', 8192, 128000, 0.1, 2.5, 10.0, true, true, true, true, 10),

        -- AWS Bedrock models
        ('aws_bedrock', 'anthropic.claude-opus-4-5-20251124-v1:0', 'Claude Opus 4.5 (Bedrock)', 'Most powerful Claude model via AWS Bedrock', 16384, 200000, 0.1, 15.0, 75.0, true, true, true, true, 10),
        ('aws_bedrock', 'anthropic.claude-sonnet-4-5-20250929-v1:0', 'Claude Sonnet 4.5 (Bedrock)', 'Claude Sonnet 4.5 via AWS Bedrock', 16384, 200000, 0.1, 3.0, 15.0, true, true, false, true, 20)
    """)

    # =========================================================================
    # STEP 13: Create webhooks tables
    # =========================================================================

    op.create_table(
        'webhooks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(64), nullable=False),
        sa.Column('events', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('headers', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('retry_delay_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_failures', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('total_deliveries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_webhooks_user_id', 'webhooks', ['user_id'])
    op.create_index('ix_webhooks_is_active', 'webhooks', ['is_active'])
    op.create_index('idx_webhooks_organization', 'webhooks', ['organization_id'])

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('webhook_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'])
    op.create_index('ix_webhook_deliveries_status', 'webhook_deliveries', ['status'])
    op.create_index('ix_webhook_deliveries_created_at', 'webhook_deliveries', ['created_at'])

    # =========================================================================
    # STEP 14: Create analytics tables
    # =========================================================================

    op.create_table(
        'usage_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('leaflets_uploaded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leaflets_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('leaflets_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pages_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('products_extracted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('products_auto_approved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('products_reviewed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('products_approved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('products_rejected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_confidence', sa.Float(), nullable=True),
        sa.Column('avg_validation_pass_rate', sa.Float(), nullable=True),
        sa.Column('api_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('api_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('api_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('api_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_processing_time_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('storage_used_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='uq_usage_metrics_user_date'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_usage_metrics_user_id', 'usage_metrics', ['user_id'])
    op.create_index('ix_usage_metrics_date', 'usage_metrics', ['date'])

    op.create_table(
        'cost_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('leaflet_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('vlm_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('input_cost', sa.Float(), nullable=False),
        sa.Column('output_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('product_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_price_per_1m', sa.Float(), nullable=False),
        sa.Column('output_price_per_1m', sa.Float(), nullable=False),
        sa.Column('metadata_', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['leaflet_id'], ['leaflets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vlm_provider_id'], ['vlm_providers.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_cost_tracking_user_id', 'cost_tracking', ['user_id'])
    op.create_index('ix_cost_tracking_leaflet_id', 'cost_tracking', ['leaflet_id'])
    op.create_index('ix_cost_tracking_processed_at', 'cost_tracking', ['processed_at'])

    op.create_table(
        'processing_stats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('period_type', sa.String(20), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('total_leaflets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_leaflets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_leaflets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_products', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_approved_products', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reviewed_products', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_confidence', sa.Float(), nullable=True),
        sa.Column('avg_products_per_leaflet', sa.Float(), nullable=True),
        sa.Column('avg_processing_time', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extraction_success_rate', sa.Float(), nullable=True),
        sa.Column('auto_approval_rate', sa.Float(), nullable=True),
        sa.Column('validation_pass_rate', sa.Float(), nullable=True),
        sa.Column('top_retailers', postgresql.JSONB(), nullable=True),
        sa.Column('error_breakdown', postgresql.JSONB(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_processing_stats_user_id', 'processing_stats', ['user_id'])
    op.create_index('ix_processing_stats_period', 'processing_stats', ['period_type', 'period_start'])

    op.create_table(
        'feedback_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('leaflet_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('feedback_type', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(50), nullable=True),
        sa.Column('original_value', postgresql.JSONB(), nullable=True),
        sa.Column('corrected_value', postgresql.JSONB(), nullable=True),
        sa.Column('original_confidence', sa.Float(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('retailer', sa.String(100), nullable=True),
        sa.Column('error_category', sa.String(50), nullable=True),
        sa.Column('severity', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('used_for_training', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['leaflet_id'], ['leaflets.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_feedback_logs_user_id', 'feedback_logs', ['user_id'])
    op.create_index('ix_feedback_logs_feedback_type', 'feedback_logs', ['feedback_type'])
    op.create_index('ix_feedback_logs_field_name', 'feedback_logs', ['field_name'])
    op.create_index('ix_feedback_logs_created_at', 'feedback_logs', ['created_at'])

    op.create_table(
        'error_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('pattern_hash', sa.String(64), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('field_affected', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('retailers_affected', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('example_feedback_ids', postgresql.ARRAY(postgresql.UUID()), nullable=True),
        sa.Column('suggested_prompt_change', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pattern_hash'),
    )
    op.create_index('ix_error_patterns_pattern_hash', 'error_patterns', ['pattern_hash'], unique=True)
    op.create_index('ix_error_patterns_error_type', 'error_patterns', ['error_type'])
    op.create_index('ix_error_patterns_is_resolved', 'error_patterns', ['is_resolved'])

    # =========================================================================
    # STEP 15: Create platform VLM management tables
    # =========================================================================

    op.create_table(
        'platform_vlm_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider_type', postgresql.ENUM('anthropic', 'openai', 'google', 'azure_openai', 'aws_bedrock', 'custom', name='platformvlmprovidertype', create_type=False), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('api_endpoint', sa.String(500), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=False, server_default='claude-sonnet-4.5-20250929'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='16384'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.1'),
        sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('monthly_budget', sa.Float(), nullable=True),
        sa.Column('daily_budget', sa.Float(), nullable=True),
        sa.Column('max_requests_per_hour', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('total_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_month_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_day_spent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_hour_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint('priority >= 1 AND priority <= 999', name='check_priority_range'),
        sa.CheckConstraint('monthly_budget IS NULL OR monthly_budget > 0', name='check_monthly_budget_positive'),
        sa.CheckConstraint('daily_budget IS NULL OR daily_budget > 0', name='check_daily_budget_positive'),
        sa.CheckConstraint('max_requests_per_hour > 0', name='check_max_requests_positive'),
        sa.CheckConstraint('total_spent >= 0', name='check_total_spent_non_negative'),
        sa.CheckConstraint('current_month_spent >= 0', name='check_current_month_spent_non_negative'),
        sa.CheckConstraint('current_day_spent >= 0', name='check_current_day_spent_non_negative'),
    )
    op.create_index('idx_platform_provider_priority_active', 'platform_vlm_providers', ['priority', 'is_active', 'is_default'])
    op.create_index('idx_platform_provider_type_active', 'platform_vlm_providers', ['provider_type', 'is_active'])
    op.create_index('idx_platform_provider_created_at', 'platform_vlm_providers', ['created_at'])

    op.create_table(
        'system_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('role_requirement', sa.String(20), nullable=True),
        sa.Column('notification_type', postgresql.ENUM('budget_warning', 'provider_failover', 'system_alert', 'maintenance', 'security_alert', 'feature_update', 'usage_report', 'api_key_expiry', 'organization_update', 'user_action_required', name='notificationtype', create_type=False), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', postgresql.ENUM('info', 'success', 'warning', 'error', 'critical', name='notificationseverity', create_type=False), nullable=False, server_default='info'),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('action_text', sa.String(50), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_type', postgresql.ENUM('budget_monitor', 'failover_system', 'manual', 'system', 'webhook', 'scheduled', name='notificationsource', create_type=False), nullable=False, server_default='system'),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notification_metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_notification_user_read_created', 'system_notifications', ['user_id', 'is_read', 'created_at'])
    op.create_index('idx_notification_org_read_created', 'system_notifications', ['organization_id', 'is_read', 'created_at'])
    op.create_index('idx_notification_role_read_created', 'system_notifications', ['role_requirement', 'is_read', 'created_at'])
    op.create_index('idx_notification_type_created', 'system_notifications', ['notification_type', 'created_at'])
    op.create_index('idx_notification_severity_created', 'system_notifications', ['severity', 'created_at'])
    op.create_index('idx_notification_expires', 'system_notifications', ['expires_at'])
    op.create_index('idx_notification_source', 'system_notifications', ['source_type', 'source_id'])

    op.create_table(
        'notification_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enabled_types', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_digest_frequency', sa.String(20), nullable=False, server_default='daily'),
        sa.Column('show_success_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_dismiss_after_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'organization_vlm_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('usage_hour', sa.Integer(), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(10, 4), nullable=False, server_default='0.0'),
        sa.Column('leaflet_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('product_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'platform_provider_id', 'usage_date', 'usage_hour', name='uq_org_provider_date_hour'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['platform_provider_id'], ['platform_vlm_providers.id'], ondelete='SET NULL'),
        sa.CheckConstraint('usage_hour IS NULL OR (usage_hour >= 0 AND usage_hour <= 23)', name='check_usage_hour_range'),
        sa.CheckConstraint('request_count >= 0', name='check_request_count_non_negative'),
        sa.CheckConstraint('input_tokens >= 0', name='check_input_tokens_non_negative'),
        sa.CheckConstraint('output_tokens >= 0', name='check_output_tokens_non_negative'),
        sa.CheckConstraint('total_cost >= 0', name='check_total_cost_non_negative'),
        sa.CheckConstraint('leaflet_count >= 0', name='check_leaflet_count_non_negative'),
        sa.CheckConstraint('page_count >= 0', name='check_page_count_non_negative'),
        sa.CheckConstraint('product_count >= 0', name='check_product_count_non_negative'),
        sa.CheckConstraint('average_confidence IS NULL OR (average_confidence >= 0.0 AND average_confidence <= 1.0)', name='check_avg_confidence_range'),
    )
    op.create_index('idx_org_usage_org_date', 'organization_vlm_usage', ['organization_id', 'usage_date'])
    op.create_index('idx_org_usage_provider_date', 'organization_vlm_usage', ['platform_provider_id', 'usage_date'])
    op.create_index('idx_org_usage_date_hour', 'organization_vlm_usage', ['usage_date', 'usage_hour'])
    op.create_index('idx_org_usage_created', 'organization_vlm_usage', ['created_at'])

    op.create_table(
        'organization_usage_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('summary_period', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(10), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_input_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_output_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Numeric(12, 4), nullable=False, server_default='0.0'),
        sa.Column('total_leaflets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_products', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_confidence', sa.Float(), nullable=True),
        sa.Column('provider_breakdown', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'summary_period', 'period_type', name='uq_org_summary_period_type'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.CheckConstraint("period_type IN ('monthly', 'yearly')", name='check_period_type'),
    )
    op.create_index('idx_org_summary_org_period', 'organization_usage_summaries', ['organization_id', 'summary_period'])
    op.create_index('idx_org_summary_period_type', 'organization_usage_summaries', ['summary_period', 'period_type'])

    op.create_table(
        'budget_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('platform_provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', postgresql.ENUM('warning', 'critical', 'exhausted', 'rate_limit', name='alerttype', create_type=False), nullable=False),
        sa.Column('threshold_percentage', sa.Integer(), nullable=False),
        sa.Column('period', postgresql.ENUM('daily', 'monthly', 'hourly', name='alertperiod', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notify_super_admins', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_org_admins', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_recipients', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('slack_webhook_url', sa.String(500), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('max_triggers_per_day', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('custom_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['platform_provider_id'], ['platform_vlm_providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.CheckConstraint('threshold_percentage >= 0 AND threshold_percentage <= 100', name='check_threshold_range'),
        sa.CheckConstraint('cooldown_minutes >= 0', name='check_cooldown_non_negative'),
        sa.CheckConstraint('max_triggers_per_day > 0', name='check_max_triggers_positive'),
        sa.CheckConstraint('trigger_count >= 0', name='check_trigger_count_non_negative'),
    )
    op.create_index('idx_budget_alert_provider_active', 'budget_alerts', ['platform_provider_id', 'is_active'])
    op.create_index('idx_budget_alert_org_active', 'budget_alerts', ['organization_id', 'is_active'])
    op.create_index('idx_budget_alert_type_period', 'budget_alerts', ['alert_type', 'period'])
    op.create_index('idx_budget_alert_threshold', 'budget_alerts', ['threshold_percentage'])
    op.create_index('idx_budget_alert_last_triggered', 'budget_alerts', ['last_triggered_at'])

    op.create_table(
        'alert_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('budget_alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('platform_provider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', postgresql.ENUM('warning', 'critical', 'exhausted', 'rate_limit', name='alerttype', create_type=False), nullable=False),
        sa.Column('threshold_percentage', sa.Integer(), nullable=False),
        sa.Column('period', postgresql.ENUM('daily', 'monthly', 'hourly', name='alertperiod', create_type=False), nullable=False),
        sa.Column('current_usage', sa.Numeric(10, 4), nullable=False),
        sa.Column('budget_limit', sa.Numeric(10, 4), nullable=False),
        sa.Column('usage_percentage', sa.Float(), nullable=False),
        sa.Column('alert_message', sa.Text(), nullable=False),
        sa.Column('notifications_sent', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['budget_alert_id'], ['budget_alerts.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_alert_history_provider_triggered', 'alert_history', ['platform_provider_id', 'triggered_at'])
    op.create_index('idx_alert_history_org_triggered', 'alert_history', ['organization_id', 'triggered_at'])
    op.create_index('idx_alert_history_type_triggered', 'alert_history', ['alert_type', 'triggered_at'])
    op.create_index('idx_alert_history_triggered', 'alert_history', ['triggered_at'])

    op.create_table(
        'vlm_provider_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('platform_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('leaflet_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', postgresql.ENUM('extraction', 'failover', 'budget_warning', 'budget_exhausted', 'rate_limit_hit', 'provider_error', 'key_created', 'key_updated', 'key_deleted', 'key_tested', 'config_changed', 'usage_reset', name='auditeventtype', create_type=False), nullable=False),
        sa.Column('event_status', postgresql.ENUM('success', 'failure', 'warning', 'error', 'partial', name='auditeventstatus', create_type=False), nullable=False),
        sa.Column('operation_id', sa.String(100), nullable=True),
        sa.Column('provider_type', sa.String(50), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Numeric(8, 4), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('error_type', postgresql.ENUM('authentication', 'rate_limit', 'budget_limit', 'network', 'timeout', 'validation', 'provider_error', 'system_error', name='errorcategory', create_type=False), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('request_ip', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('api_key_id', sa.String(100), nullable=True),
        sa.Column('request_payload_hash', sa.String(64), nullable=True),
        sa.Column('response_payload_hash', sa.String(64), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['platform_provider_id'], ['platform_vlm_providers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['leaflet_id'], ['leaflets.id'], ondelete='SET NULL'),
        sa.CheckConstraint('retry_count >= 0', name='check_audit_retry_count_non_negative'),
        sa.CheckConstraint('input_tokens IS NULL OR input_tokens >= 0', name='check_audit_input_tokens_non_negative'),
        sa.CheckConstraint('output_tokens IS NULL OR output_tokens >= 0', name='check_audit_output_tokens_non_negative'),
        sa.CheckConstraint('cost IS NULL OR cost >= 0', name='check_audit_cost_non_negative'),
        sa.CheckConstraint('latency_ms IS NULL OR latency_ms >= 0', name='check_audit_latency_non_negative'),
    )
    op.create_index('idx_audit_log_org_created', 'vlm_provider_audit_log', ['organization_id', 'created_at'])
    op.create_index('idx_audit_log_user_created', 'vlm_provider_audit_log', ['user_id', 'created_at'])
    op.create_index('idx_audit_log_provider_created', 'vlm_provider_audit_log', ['platform_provider_id', 'created_at'])
    op.create_index('idx_audit_log_leaflet_created', 'vlm_provider_audit_log', ['leaflet_id', 'created_at'])
    op.create_index('idx_audit_log_event_type_created', 'vlm_provider_audit_log', ['event_type', 'created_at'])
    op.create_index('idx_audit_log_event_status_created', 'vlm_provider_audit_log', ['event_status', 'created_at'])
    op.create_index('idx_audit_log_error_type_created', 'vlm_provider_audit_log', ['error_type', 'created_at'])
    op.create_index('idx_audit_log_operation_id', 'vlm_provider_audit_log', ['operation_id'])
    op.create_index('idx_audit_log_session_id', 'vlm_provider_audit_log', ['session_id'])
    op.create_index('idx_audit_log_provider_type', 'vlm_provider_audit_log', ['provider_type', 'created_at'])
    op.create_index('idx_audit_log_request_ip_created', 'vlm_provider_audit_log', ['request_ip', 'created_at'])
    op.create_index('idx_audit_log_api_key_created', 'vlm_provider_audit_log', ['api_key_id', 'created_at'])

    # Conditional index for cost analysis
    op.execute(
        "CREATE INDEX idx_audit_log_cost_created ON vlm_provider_audit_log(cost, created_at) "
        "WHERE cost IS NOT NULL"
    )

    op.create_table(
        'vlm_provider_backups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('platform_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('backup_type', postgresql.ENUM('manual', 'scheduled', 'pre_deletion', 'pre_update', 'migration', 'emergency', name='backuptype', create_type=False), nullable=False),
        sa.Column('encrypted_config', sa.Text(), nullable=False),
        sa.Column('backup_hash', sa.String(64), nullable=False),
        sa.Column('encryption_key_id', sa.String(100), nullable=False, server_default='default'),
        sa.Column('provider_name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('config_version', sa.String(20), nullable=False, server_default='1.0'),
        sa.Column('backup_note', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'archived', 'expired', 'corrupted', name='backupstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_delete', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_passed', sa.Boolean(), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('restored_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('backup_hash'),
        sa.ForeignKeyConstraint(['platform_provider_id'], ['platform_vlm_providers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['restored_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint('expires_at IS NULL OR expires_at > created_at', name='check_expires_after_creation'),
    )
    op.create_index('idx_backup_provider_created', 'vlm_provider_backups', ['platform_provider_id', 'created_at'])
    op.create_index('idx_backup_created_by', 'vlm_provider_backups', ['created_by_user_id', 'created_at'])
    op.create_index('idx_backup_type_created', 'vlm_provider_backups', ['backup_type', 'created_at'])
    op.create_index('idx_backup_status_expires', 'vlm_provider_backups', ['status', 'expires_at'])
    op.create_index('idx_backup_provider_type', 'vlm_provider_backups', ['provider_type', 'created_at'])
    op.create_index('idx_backup_auto_delete_expires', 'vlm_provider_backups', ['auto_delete', 'expires_at'])


def downgrade() -> None:
    """Drop all database tables."""

    # Platform VLM management tables
    op.drop_table('vlm_provider_backups')
    op.drop_table('vlm_provider_audit_log')
    op.drop_table('alert_history')
    op.drop_table('budget_alerts')
    op.drop_table('organization_usage_summaries')
    op.drop_table('organization_vlm_usage')
    op.drop_table('notification_preferences')
    op.drop_table('system_notifications')
    op.drop_table('platform_vlm_providers')

    # Analytics tables
    op.drop_table('error_patterns')
    op.drop_table('feedback_logs')
    op.drop_table('processing_stats')
    op.drop_table('cost_tracking')
    op.drop_table('usage_metrics')

    # Webhook tables
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')

    # VLM tables
    op.drop_table('vlm_models')
    op.drop_table('vlm_providers')

    # Product tables
    op.drop_table('product_categories')
    op.drop_table('product_reviews')
    op.drop_table('products')

    # Leaflet tables
    op.drop_table('leaflet_pages')
    op.drop_table('leaflets')

    # API keys
    op.drop_table('api_keys')

    # Retailers
    op.drop_table('retailers')

    # Organization tables
    op.drop_table('deletion_requests')
    op.drop_table('organization_invitations')
    op.drop_table('organization_users')

    # Drop FK from users before dropping organizations
    op.drop_constraint('fk_users_default_organization', 'users', type_='foreignkey')
    op.drop_index('idx_users_default_org', table_name='users')
    op.drop_column('users', 'default_organization_id')

    op.drop_table('organizations')

    # Core tables
    op.drop_table('users')

    # Drop all enums
    op.execute('DROP TYPE IF EXISTS backupstatus')
    op.execute('DROP TYPE IF EXISTS backuptype')
    op.execute('DROP TYPE IF EXISTS errorcategory')
    op.execute('DROP TYPE IF EXISTS auditeventstatus')
    op.execute('DROP TYPE IF EXISTS auditeventtype')
    op.execute('DROP TYPE IF EXISTS alertperiod')
    op.execute('DROP TYPE IF EXISTS alerttype')
    op.execute('DROP TYPE IF EXISTS notificationsource')
    op.execute('DROP TYPE IF EXISTS notificationseverity')
    op.execute('DROP TYPE IF EXISTS notificationtype')
    op.execute('DROP TYPE IF EXISTS platformvlmprovidertype')
    op.execute('DROP TYPE IF EXISTS deletionrequeststatus')
    op.execute('DROP TYPE IF EXISTS deletionrequesttype')
    op.execute('DROP TYPE IF EXISTS invitationstatus')
    op.execute('DROP TYPE IF EXISTS organizationrole')
    op.execute('DROP TYPE IF EXISTS organizationstatus')
    op.execute('DROP TYPE IF EXISTS organizationtype')