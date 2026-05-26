"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Building,
  Loader2,
  Search,
  XCircle,
  Pencil,
  Check,
  X,
  Infinity as InfinityIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
import { getCurrentUser } from "@/lib/actions/auth";
import {
  getOrganizationsWithQuota,
  updateOrganizationLimit,
  type OrganizationWithQuota,
} from "@/lib/actions/admin";

const PAGE_SIZE = 50;

export default function AdminOrganizationsPage() {
  const router = useRouter();
  const [organizations, setOrganizations] = useState<OrganizationWithQuota[]>([]);
  const [filteredOrganizations, setFilteredOrganizations] = useState<OrganizationWithQuota[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [accessConfirmed, setAccessConfirmed] = useState(false);

  // Pagination state
  const [serverTotal, setServerTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Inline editing state
  const [editingOrgId, setEditingOrgId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const allLoaded = organizations.length >= serverTotal;

  // Superuser access gate — fetch organizations only after access is confirmed
  useEffect(() => {
    getCurrentUser().then((user) => {
      if (!user || !user.is_superuser) {
        router.replace("/dashboard");
        return;
      }
      setAccessConfirmed(true);
      fetchOrganizations();
    });
  }, [router]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredOrganizations(organizations);
      return;
    }
    const query = searchQuery.toLowerCase();
    setFilteredOrganizations(
      organizations.filter(
        (org) =>
          org.name.toLowerCase().includes(query) ||
          org.slug.toLowerCase().includes(query)
      )
    );
  }, [searchQuery, organizations]);

  const fetchOrganizations = async () => {
    try {
      setLoading(true);
      const result = await getOrganizationsWithQuota(1, PAGE_SIZE);
      if (result.success && result.data) {
        setOrganizations(result.data.items);
        setServerTotal(result.data.total);
        setCurrentPage(1);
      } else {
        throw new Error(result.error || "Failed to fetch organizations");
      }
    } catch (error) {
      console.error("Error fetching organizations:", error);
      toast.error("Failed to load organizations");
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (allLoaded || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const nextPage = currentPage + 1;
      const result = await getOrganizationsWithQuota(nextPage, PAGE_SIZE);
      if (result.success && result.data) {
        setOrganizations((prev) => [...prev, ...result.data!.items]);
        setServerTotal(result.data.total);
        setCurrentPage(nextPage);
      } else {
        throw new Error(result.error || "Failed to load more organizations");
      }
    } catch (error) {
      console.error("Error loading more organizations:", error);
      toast.error("Failed to load more organizations");
    } finally {
      setIsLoadingMore(false);
    }
  };

  const startEditing = (org: OrganizationWithQuota) => {
    setEditingOrgId(org.id);
    setEditValue(String(org.platform_leaflet_limit));
  };

  const cancelEditing = () => {
    setEditingOrgId(null);
    setEditValue("");
  };

  const saveLimit = async (orgId: string) => {
    const trimmed = editValue.trim();
    if (!/^\d+$/.test(trimmed)) {
      toast.error("Limit must be a whole number (e.g. 0, 10, 50)");
      return;
    }
    const numValue = parseInt(trimmed, 10);

    try {
      setSaving(true);
      const result = await updateOrganizationLimit(orgId, numValue);
      if (result.success && result.data) {
        toast.success(result.data.message);
        // Update local state
        setOrganizations((prev) =>
          prev.map((org) =>
            org.id === orgId
              ? {
                  ...org,
                  platform_leaflet_limit: result.data!.platform_leaflet_limit,
                  platform_leaflets_used: result.data!.platform_leaflets_used,
                }
              : org
          )
        );
        setEditingOrgId(null);
        setEditValue("");
      } else {
        throw new Error(result.error || "Failed to update limit");
      }
    } catch (error) {
      console.error("Error updating organization limit:", error);
      toast.error(
        error instanceof Error ? error.message : "Failed to update limit"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, orgId: string) => {
    if (e.key === "Enter") {
      saveLimit(orgId);
    } else if (e.key === "Escape" && !saving) {
      cancelEditing();
    }
  };

  const formatRemaining = (org: OrganizationWithQuota): string => {
    if (org.platform_leaflet_limit === 0) return "Unlimited";
    const remaining = Math.max(
      0,
      org.platform_leaflet_limit - org.platform_leaflets_used
    );
    return String(remaining);
  };

  const getUsagePercentage = (org: OrganizationWithQuota): number | null => {
    if (org.platform_leaflet_limit === 0) return null;
    return Math.min(
      100,
      Math.round((org.platform_leaflets_used / org.platform_leaflet_limit) * 100)
    );
  };

  const getUsageBadgeStyle = (org: OrganizationWithQuota) => {
    const pct = getUsagePercentage(org);
    if (pct === null) {
      return {
        bg: "bg-blue-50",
        text: "text-blue-700",
        border: "border-blue-200",
      };
    }
    if (pct >= 100) {
      return {
        bg: "bg-red-50",
        text: "text-red-700",
        border: "border-red-200",
      };
    }
    if (pct >= 80) {
      return {
        bg: "bg-yellow-50",
        text: "text-yellow-700",
        border: "border-yellow-200",
      };
    }
    return {
      bg: "bg-green-50",
      text: "text-green-700",
      border: "border-green-200",
    };
  };

  const getStatusBadge = (status: string) => {
    const normalizedStatus = status.toUpperCase();
    const styles: Record<string, { bg: string; text: string; border: string }> = {
      ACTIVE: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
      PENDING_APPROVAL: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
      SUSPENDED: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
    };
    const labels: Record<string, string> = {
      ACTIVE: "Active",
      PENDING_APPROVAL: "Pending",
      SUSPENDED: "Suspended",
    };
    const label = labels[normalizedStatus] || status;
    const styleObj = styles[normalizedStatus] || styles.ACTIVE;

    return (
      <span
        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${styleObj.bg} ${styleObj.text} ${styleObj.border}`}
      >
        {label}
      </span>
    );
  };

  // Summary stats (note: these reflect only the loaded subset, not all orgs)
  const totalOrgs = serverTotal;
  const unlimitedOrgs = organizations.filter(
    (org) => org.platform_leaflet_limit === 0
  ).length;
  const exhaustedOrgs = organizations.filter(
    (org) =>
      org.platform_leaflet_limit > 0 &&
      org.platform_leaflets_used >= org.platform_leaflet_limit
  ).length;

  // Render nothing until superuser access is confirmed — prevents flash of
  // loading spinner for non-superusers before the redirect fires.
  if (!accessConfirmed) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl bg-gray-50">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
          Organization <span className="font-normal">Extraction Limits</span>
        </h1>
        <p className="text-sm text-gray-500">
          Manage platform AI extraction limits per organization
        </p>
      </div>

      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="border-gray-200">
            <CardContent className="pt-6">
              <div className="text-sm text-gray-500">Total Organizations</div>
              <div className="text-2xl font-semibold text-gray-900 mt-1">
                {totalOrgs}
              </div>
            </CardContent>
          </Card>
          <Card className="border-gray-200">
            <CardContent className="pt-6">
              <div className="text-sm text-gray-500">Unlimited Access</div>
              <div className="text-2xl font-semibold text-blue-600 mt-1">
                {unlimitedOrgs}
              </div>
            </CardContent>
          </Card>
          <Card className="border-gray-200">
            <CardContent className="pt-6">
              <div className="text-sm text-gray-500">Limit Exhausted</div>
              <div className="text-2xl font-semibold text-red-600 mt-1">
                {exhaustedOrgs}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search Bar */}
        <Card className="border-gray-200">
          <CardContent className="pt-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <Input
                type="text"
                placeholder="Search by organization name or slug..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-10 border-gray-200"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="mt-4 text-sm text-gray-500">
              {searchQuery.trim() ? (
                <>
                  Showing{" "}
                  <span className="font-medium text-gray-900">
                    {filteredOrganizations.length}
                  </span>{" "}
                  matching{" "}
                  <span className="font-medium text-gray-900">
                    {organizations.length}
                  </span>{" "}
                  loaded organizations
                  {!allLoaded && (
                    <span className="text-gray-400">
                      {" "}&mdash; load more to search all {serverTotal}
                    </span>
                  )}
                </>
              ) : (
                <>
                  Showing{" "}
                  <span className="font-medium text-gray-900">
                    {organizations.length}
                  </span>{" "}
                  of{" "}
                  <span className="font-medium text-gray-900">
                    {serverTotal}
                  </span>{" "}
                  organizations
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Organizations Table */}
        {filteredOrganizations.length === 0 ? (
          <Card className="border-gray-200">
            <CardContent className="py-12">
              <div className="text-center">
                <Search className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-normal mb-2 text-gray-900">
                  No Results Found
                </h3>
                <p className="text-sm text-gray-500">
                  {searchQuery ? (
                    <>
                      No organizations match your search for &quot;{searchQuery}
                      &quot;.
                    </>
                  ) : (
                    <>There are no organizations yet.</>
                  )}
                </p>
                {searchQuery && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSearchQuery("")}
                    className="mt-4 border-gray-200"
                  >
                    Clear Search
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-gray-200">
            <CardHeader className="bg-gray-50 border-b border-gray-200">
              <CardTitle className="text-base text-gray-900">
                Organizations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-gray-200">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-100">
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                        Organization
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                        Status
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                        Usage
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger className="flex items-center gap-1">
                              Limit
                              <span className="text-gray-400 text-[10px] font-normal normal-case">
                                (0 = unlimited)
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>
                                Maximum platform extractions. Set to 0 for
                                unlimited access.
                              </p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                        Remaining
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">
                        Actions
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredOrganizations.map((org) => {
                      const usagePct = getUsagePercentage(org);
                      const usageStyle = getUsageBadgeStyle(org);
                      const isEditing = editingOrgId === org.id;

                      return (
                        <TableRow key={org.id} className="hover:bg-gray-50/50">
                          {/* Organization Name */}
                          <TableCell>
                            <div className="flex items-start gap-3">
                              <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-blue-50">
                                <Building className="h-5 w-5 text-blue-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900">
                                  {org.name}
                                </div>
                                <div className="text-sm text-gray-500">
                                  {org.slug}
                                </div>
                              </div>
                            </div>
                          </TableCell>

                          {/* Status */}
                          <TableCell>{getStatusBadge(org.status)}</TableCell>

                          {/* Usage */}
                          <TableCell>
                            <div className="space-y-1.5">
                              <div className="text-sm font-medium text-gray-900">
                                {org.platform_leaflets_used}
                                <span className="text-gray-400 font-normal">
                                  {" "}
                                  /{" "}
                                  {org.platform_leaflet_limit === 0
                                    ? "\u221E"
                                    : org.platform_leaflet_limit}
                                </span>
                              </div>
                              {usagePct !== null && (
                                <div className="w-24 bg-gray-200 rounded-full h-1.5">
                                  <div
                                    className={`h-1.5 rounded-full transition-all ${
                                      usagePct >= 100
                                        ? "bg-red-500"
                                        : usagePct >= 80
                                          ? "bg-yellow-500"
                                          : "bg-green-500"
                                    }`}
                                    style={{
                                      width: `${Math.min(usagePct, 100)}%`,
                                    }}
                                  />
                                </div>
                              )}
                            </div>
                          </TableCell>

                          {/* Limit (editable) */}
                          <TableCell>
                            {isEditing ? (
                              <div className="flex items-center gap-2">
                                <Input
                                  type="number"
                                  min="0"
                                  value={editValue}
                                  onChange={(e) => setEditValue(e.target.value)}
                                  onKeyDown={(e) => handleKeyDown(e, org.id)}
                                  className="w-24 h-8 text-sm border-gray-300"
                                  aria-label={`Extraction limit for ${org.name}`}
                                  autoFocus
                                  disabled={saving}
                                />
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => saveLimit(org.id)}
                                  disabled={saving}
                                  className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                                >
                                  {saving ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <Check className="h-4 w-4" />
                                  )}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={cancelEditing}
                                  disabled={saving}
                                  className="h-8 w-8 p-0 text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1.5">
                                {org.platform_leaflet_limit === 0 ? (
                                  <span className="inline-flex items-center gap-1 text-sm text-blue-600 font-medium">
                                    <InfinityIcon className="h-3.5 w-3.5" />
                                    Unlimited
                                  </span>
                                ) : (
                                  <span className="text-sm font-medium text-gray-900">
                                    {org.platform_leaflet_limit}
                                  </span>
                                )}
                              </div>
                            )}
                          </TableCell>

                          {/* Remaining */}
                          <TableCell>
                            <span
                              className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${usageStyle.bg} ${usageStyle.text} ${usageStyle.border}`}
                            >
                              {formatRemaining(org)}
                            </span>
                          </TableCell>

                          {/* Actions */}
                          <TableCell className="text-right">
                            {!isEditing && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => startEditing(org)}
                                className="h-8 text-xs border-gray-200"
                              >
                                <Pencil className="h-3.5 w-3.5 mr-1" />
                                Edit Limit
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Load More button when more organizations exist on the server */}
        {!allLoaded && (
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={loadMore}
              disabled={isLoadingMore}
              className="gap-2 border-gray-200"
            >
              {isLoadingMore ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Building className="h-4 w-4" />
              )}
              {isLoadingMore
                ? "Loading..."
                : `Load More Organizations (${serverTotal - organizations.length} remaining)`}
              {!isLoadingMore && (
                <span className="text-xs text-muted-foreground">
                  ({organizations.length} of {serverTotal} loaded)
                </span>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
