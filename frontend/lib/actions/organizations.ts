"use server";

import { apiRequest } from "@/lib/api-client";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  organization_type: string;
  status: string;
  business_name: string | null;
  business_email: string;
  business_phone: string | null;
  business_address: string | null;
  tax_id: string | null;
  logo_url: string | null;
  member_count: number;
  is_active: boolean;
  role: string;
  created_at: string;
  updated_at: string;
}

export interface OrganizationSwitcherData {
  id: string;
  name: string;
  role: string;
  status: string;
  member_count?: number;
}

export async function getUserOrganizations(): Promise<OrganizationSwitcherData[]> {
  try {
    const organizations = await apiRequest<Organization[]>("/api/v1/organizations");

    // Transform to OrganizationSwitcherData format
    return organizations.map(org => ({
      id: org.id,
      name: org.name,
      role: org.role,
      status: org.status,
      member_count: org.member_count,
    }));
  } catch (error) {
    console.error("Failed to fetch user organizations:", error);
    return [];
  }
}

export async function getCurrentOrganization(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  userId: string
): Promise<OrganizationSwitcherData | null> {
  try {
    const organizations = await getUserOrganizations();

    // Return the first organization for now
    // TODO: Use user's default_organization_id to determine current org
    return organizations.length > 0 ? organizations[0] : null;
  } catch (error) {
    console.error("Failed to fetch current organization:", error);
    return null;
  }
}

export async function switchOrganization(orgId: string): Promise<{ success: boolean; error?: string }> {
  try {
    await apiRequest(`/api/v1/organizations/${orgId}/switch`, {
      method: "POST",
    });

    return { success: true };
  } catch (error) {
    console.error("Failed to switch organization:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to switch organization",
    };
  }
}

export interface OrganizationMember {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  joined_at: string;
}

export interface OrganizationInvitation {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  invited_by: string;
  email_sent: boolean;
  email_error?: string | null;
}

export async function getOrganizationMembers(orgId: string): Promise<OrganizationMember[]> {
  try {
    return await apiRequest<OrganizationMember[]>(`/api/v1/organizations/${orgId}/members`);
  } catch (error) {
    console.error("Failed to fetch organization members:", error);
    return [];
  }
}

export async function getOrganizationInvitations(orgId: string): Promise<OrganizationInvitation[]> {
  try {
    return await apiRequest<OrganizationInvitation[]>(`/api/v1/organizations/${orgId}/invitations`);
  } catch (error) {
    console.error("Failed to fetch organization invitations:", error);
    return [];
  }
}

export async function sendOrganizationInvitation(
  orgId: string,
  email: string,
  role: string
): Promise<{ success: boolean; data?: OrganizationInvitation; error?: string }> {
  try {
    const invitation = await apiRequest<OrganizationInvitation>(
      `/api/v1/organizations/${orgId}/invitations`,
      {
        method: "POST",
        body: JSON.stringify({ email, role }),
      }
    );

    return { success: true, data: invitation };
  } catch (error) {
    console.error("Failed to send invitation:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send invitation",
    };
  }
}

export async function resendOrganizationInvitation(
  orgId: string,
  invitationId: string
): Promise<{ success: boolean; data?: OrganizationInvitation; error?: string }> {
  try {
    const invitation = await apiRequest<OrganizationInvitation>(
      `/api/v1/organizations/${orgId}/invitations/${invitationId}/resend`,
      {
        method: "POST",
      }
    );

    return { success: true, data: invitation };
  } catch (error) {
    console.error("Failed to resend invitation:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to resend invitation",
    };
  }
}

export async function revokeOrganizationInvitation(
  orgId: string,
  invitationId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    await apiRequest(`/api/v1/organizations/${orgId}/invitations/${invitationId}`, {
      method: "DELETE",
    });

    return { success: true };
  } catch (error) {
    console.error("Failed to revoke invitation:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to revoke invitation",
    };
  }
}

export async function removeOrganizationMember(
  orgId: string,
  userId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    await apiRequest(`/api/v1/organizations/${orgId}/members/${userId}`, {
      method: "DELETE",
    });

    return { success: true };
  } catch (error) {
    console.error("Failed to remove member:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove member",
    };
  }
}
