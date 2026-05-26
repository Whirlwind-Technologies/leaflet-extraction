import Link from "next/link";
import { Clock, ArrowRight } from "lucide-react";
import { getCurrentUser } from "@/lib/actions/auth";
import { getUsers } from "@/lib/actions/admin";

/**
 * Server component that shows a notification banner on the dashboard
 * when the current user is a superuser and there are pending user registrations.
 *
 * Renders nothing for non-superusers or when there are no pending users.
 */
export async function PendingUsersBanner() {
  // Check if the current user is a superuser
  const user = await getCurrentUser();
  if (!user || !user.is_superuser) {
    return null;
  }

  // Fetch inactive users (pending approval candidates)
  const result = await getUsers({ is_active: false, page_size: 100 });
  if (!result.success || !result.data) {
    return null;
  }

  // Filter to only truly pending users (not active AND not verified)
  const pendingUsers = result.data.filter((u) => !u.is_active && !u.is_verified);
  if (pendingUsers.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <Clock className="h-5 w-5 flex-shrink-0 text-amber-600" strokeWidth={1.5} />
      <div className="flex-1">
        <p className="text-sm font-medium text-amber-800">
          {pendingUsers.length} user{pendingUsers.length !== 1 ? "s" : ""} pending approval
        </p>
        <p className="text-xs text-amber-600 mt-0.5">
          New business registrations require admin review before users can access the platform.
        </p>
      </div>
      <Link
        href="/admin/users"
        className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 hover:text-amber-800"
      >
        Review
        <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
      </Link>
    </div>
  );
}
