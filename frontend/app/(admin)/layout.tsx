import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/actions/auth";
import { getUserOrganizations } from "@/lib/actions/organizations";
import { DashboardLayoutClient } from "@/components/dashboard/dashboard-layout-client";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  // Fetch user's organizations
  const organizations = await getUserOrganizations();

  // Determine current organization (first one for now, or use user's default_organization_id)
  const currentOrganization = organizations.length > 0 ? organizations[0] : undefined;

  return (
    <DashboardLayoutClient
      user={user}
      currentOrganization={currentOrganization}
      organizations={organizations}
    >
      {children}
    </DashboardLayoutClient>
  );
}