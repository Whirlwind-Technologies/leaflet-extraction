"""
Security tests for multi-tenant platform.

Tests critical security features:
- Data isolation between organizations
- JWT token validation
- Role-based access control
- Token tampering prevention
"""

import pytest
from jose import jwt
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.config import settings
from app.models.organization_user import OrganizationRole


class TestDataIsolation:
    """Test tenant data isolation."""

    def test_cannot_access_other_org_leaflets(self, client: TestClient, org_tokens):
        """Test organization cannot access another org's leaflets."""
        org1_token, org2_token = org_tokens

        # Org 1 creates a leaflet
        headers1 = {"Authorization": f"Bearer {org1_token}"}
        upload_response = client.post(
            "/api/v1/leaflets/upload",
            files={"file": ("test.pdf", b"%PDF-test", "application/pdf")},
            headers=headers1,
        )
        leaflet_id = upload_response.json()["leaflet_id"]

        # Org 2 tries to access Org 1's leaflet
        headers2 = {"Authorization": f"Bearer {org2_token}"}
        access_response = client.get(
            f"/api/v1/leaflets/{leaflet_id}",
            headers=headers2,
        )

        assert access_response.status_code == 404  # Not found due to org filtering

    def test_cannot_access_other_org_products(self, client: TestClient, org_tokens):
        """Test organization cannot access another org's products."""
        org1_token, org2_token = org_tokens

        # Org 1 has a product
        headers1 = {"Authorization": f"Bearer {org1_token}"}
        products_response1 = client.get("/api/v1/products", headers=headers1)
        org1_products = products_response1.json()["items"]

        if len(org1_products) > 0:
            product_id = org1_products[0]["product_id"]

            # Org 2 tries to access Org 1's product
            headers2 = {"Authorization": f"Bearer {org2_token}"}
            access_response = client.get(
                f"/api/v1/products/{product_id}",
                headers=headers2,
            )

            assert access_response.status_code == 404

    def test_organization_switch_updates_context(self, client: TestClient, multi_org_user_token):
        """Test switching organizations updates query context."""
        token = multi_org_user_token
        headers = {"Authorization": f"Bearer {token}"}

        # Get leaflets for current org
        response1 = client.get("/api/v1/leaflets", headers=headers)
        leaflets_org1 = response1.json()["items"]

        # Switch to different organization
        switch_response = client.post(
            f"/api/v1/organizations/{org2_id}/switch",
            headers=headers,
        )
        new_token = switch_response.json()["access_token"]

        # Get leaflets for new org
        new_headers = {"Authorization": f"Bearer {new_token}"}
        response2 = client.get("/api/v1/leaflets", headers=new_headers)
        leaflets_org2 = response2.json()["items"]

        # Should be different sets of leaflets
        org1_ids = {l["leaflet_id"] for l in leaflets_org1}
        org2_ids = {l["leaflet_id"] for l in leaflets_org2}
        assert org1_ids.isdisjoint(org2_ids)


class TestJWTSecurity:
    """Test JWT token security."""

    def test_tampered_jwt_rejected(self, client: TestClient, valid_token: str):
        """Test tampered JWT token is rejected."""
        # Decode without verification
        payload = jwt.decode(valid_token, "", algorithms=["HS256"], options={"verify_signature": False})

        # Tamper with org_id
        payload["org_id"] = "00000000-0000-0000-0000-000000000000"

        # Re-encode with wrong secret
        tampered_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        headers = {"Authorization": f"Bearer {tampered_token}"}
        response = client.get("/api/v1/leaflets", headers=headers)

        assert response.status_code == 401  # Unauthorized

    def test_expired_jwt_rejected(self, client: TestClient):
        """Test expired JWT token is rejected."""
        # Create expired token
        payload = {
            "sub": "test-user-id",
            "org_id": "test-org-id",
            "role": "member",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
            "type": "access",
        }

        expired_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/leaflets", headers=headers)

        assert response.status_code == 401

    def test_jwt_must_include_org_id(self, client: TestClient):
        """Test JWT without org_id is rejected."""
        # Create token without org_id
        payload = {
            "sub": "test-user-id",
            "role": "member",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "type": "access",
            # Missing org_id
        }

        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/leaflets", headers=headers)

        assert response.status_code == 401

    def test_jwt_org_id_must_match_user_membership(self, client: TestClient):
        """Test JWT org_id must match user's actual organization membership."""
        # Create token with org_id user doesn't belong to
        payload = {
            "sub": "valid-user-id",
            "org_id": "fake-org-id-user-not-member",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "type": "access",
        }

        fake_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        headers = {"Authorization": f"Bearer {fake_token}"}
        response = client.get("/api/v1/leaflets", headers=headers)

        # Should be rejected because user is not a member of that org
        assert response.status_code in [401, 403]


class TestRoleBasedAccessControl:
    """Test role-based access control."""

    def test_member_cannot_access_admin_endpoints(self, client: TestClient, member_token: str):
        """Test member role cannot access admin-only endpoints."""
        headers = {"Authorization": f"Bearer {member_token}"}

        # Try to invite a user (admin-only)
        invite_response = client.post(
            "/api/v1/organizations/current/invitations",
            json={"email": "newuser@example.com", "role": "member"},
            headers=headers,
        )

        assert invite_response.status_code == 403  # Forbidden

    def test_admin_can_invite_users(self, client: TestClient, admin_token: str):
        """Test admin role can invite users."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        invite_response = client.post(
            "/api/v1/organizations/current/invitations",
            json={"email": "newuser@example.com", "role": "member"},
            headers=headers,
        )

        assert invite_response.status_code == 201

    def test_member_cannot_remove_users(self, client: TestClient, member_token: str, user_id: str):
        """Test member role cannot remove users."""
        headers = {"Authorization": f"Bearer {member_token}"}

        remove_response = client.delete(
            f"/api/v1/organizations/current/members/{user_id}",
            headers=headers,
        )

        assert remove_response.status_code == 403

    def test_owner_cannot_be_removed(self, client: TestClient, admin_token: str, owner_id: str):
        """Test organization owner cannot be removed."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        remove_response = client.delete(
            f"/api/v1/organizations/current/members/{owner_id}",
            headers=headers,
        )

        assert remove_response.status_code == 400  # Bad request
        assert "owner" in remove_response.json()["detail"].lower()

    def test_cannot_remove_last_admin(self, client: TestClient, admin_token: str):
        """Test cannot remove the last admin from organization."""
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Assuming this is the last admin
        # Implementation would check admin count
        remove_response = client.delete(
            f"/api/v1/organizations/current/members/{last_admin_id}",
            headers=headers,
        )

        assert remove_response.status_code == 400
        assert "last admin" in remove_response.json()["detail"].lower()

    def test_regular_user_cannot_access_admin_panel(self, client: TestClient, user_token: str):
        """Test non-superuser cannot access admin panel."""
        headers = {"Authorization": f"Bearer {user_token}"}

        admin_response = client.get("/api/v1/admin/registrations", headers=headers)

        assert admin_response.status_code == 403

    def test_superuser_can_access_admin_panel(self, client: TestClient, superuser_token: str):
        """Test superuser can access admin panel."""
        headers = {"Authorization": f"Bearer {superuser_token}"}

        admin_response = client.get("/api/v1/admin/registrations", headers=headers)

        assert admin_response.status_code == 200


class TestInvitationSecurity:
    """Test invitation token security."""

    def test_expired_invitation_rejected(self, client: TestClient, expired_invitation_token: str):
        """Test expired invitation cannot be accepted."""
        response = client.post(
            "/api/v1/registrations/invitations/accept",
            json={"token": expired_invitation_token},
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_revoked_invitation_rejected(self, client: TestClient, revoked_invitation_token: str):
        """Test revoked invitation cannot be accepted."""
        response = client.post(
            "/api/v1/registrations/invitations/accept",
            json={"token": revoked_invitation_token},
        )

        assert response.status_code == 400
        assert "revoked" in response.json()["detail"].lower()

    def test_already_accepted_invitation_rejected(
        self, client: TestClient, accepted_invitation_token: str
    ):
        """Test already-accepted invitation cannot be reused."""
        response = client.post(
            "/api/v1/registrations/invitations/accept",
            json={"token": accepted_invitation_token},
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    def test_invalid_invitation_token_rejected(self, client: TestClient):
        """Test invalid invitation token is rejected."""
        response = client.post(
            "/api/v1/registrations/invitations/accept",
            json={"token": "invalid-token-12345"},
        )

        assert response.status_code == 404  # Not found


class TestAPIKeySecurity:
    """Test API key security and scoping."""

    def test_api_key_scoped_to_organization(self, client: TestClient, org1_api_key: str):
        """Test API key can only access its own organization's data."""
        headers = {"X-API-Key": org1_api_key}

        # Can access own org data
        response = client.get("/api/v1/leaflets", headers=headers)
        assert response.status_code == 200

        # Cannot access other org's specific resource
        response2 = client.get("/api/v1/leaflets/other-org-leaflet-id", headers=headers)
        assert response2.status_code == 404

    def test_api_key_respects_permissions(self, client: TestClient, readonly_api_key: str):
        """Test API key with read-only permissions cannot write."""
        headers = {"X-API-Key": readonly_api_key}

        # Can read
        response = client.get("/api/v1/leaflets", headers=headers)
        assert response.status_code == 200

        # Cannot write
        upload_response = client.post(
            "/api/v1/leaflets/upload",
            files={"file": ("test.pdf", b"%PDF-test", "application/pdf")},
            headers=headers,
        )
        assert upload_response.status_code == 403
