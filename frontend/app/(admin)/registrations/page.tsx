"use client";

import { useState, useEffect } from "react";
import { format } from "date-fns";
import { Building, Mail, Phone, User, CheckCircle, XCircle, Clock, Loader2, Search, Trash2, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";

interface Registration {
  id: string;
  name: string;
  slug: string;
  status: string;
  business_email: string;
  business_phone: string | null;
  requested_by: {
    id: string;
    email: string;
    full_name: string;
  } | null;
  created_at: string;
  approved_at: string | null;
  rejection_reason: string | null;
}

type StatusFilter = "all" | "pending" | "approved" | "rejected";

export default function AdminRegistrationsPage() {
  const [registrations, setRegistrations] = useState<Registration[]>([]);
  const [filteredRegistrations, setFilteredRegistrations] = useState<Registration[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [selectedRegistration, setSelectedRegistration] = useState<Registration | null>(null);
  const [actionType, setActionType] = useState<"approve" | "reject" | "suspend" | "delete" | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  useEffect(() => {
    fetchRegistrations();
  }, []);

  useEffect(() => {
    // Filter registrations based on search query and status
    let filtered = [...registrations];

    // Apply status filter
    if (statusFilter !== "all") {
      const statusMap = {
        pending: "PENDING_APPROVAL",
        approved: "ACTIVE",
        rejected: "SUSPENDED",
      };
      const targetStatus = statusMap[statusFilter as keyof typeof statusMap];
      filtered = filtered.filter((reg) => reg.status.toUpperCase() === targetStatus);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((reg) => {
        const nameMatch = reg.name.toLowerCase().includes(query);
        const emailMatch = reg.business_email.toLowerCase().includes(query);
        const ownerNameMatch = reg.requested_by?.full_name?.toLowerCase().includes(query);
        const ownerEmailMatch = reg.requested_by?.email?.toLowerCase().includes(query);

        return nameMatch || emailMatch || ownerNameMatch || ownerEmailMatch;
      });
    }

    setFilteredRegistrations(filtered);
  }, [searchQuery, statusFilter, registrations]);

  const fetchRegistrations = async () => {
    try {
      setLoading(true);
      // Always fetch all registrations, filter client-side
      const url = "/api/admin/registrations";

      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to fetch registrations");
      const data = await response.json();
      setRegistrations(data.items || []);
      setFilteredRegistrations(data.items || []);
    } catch (error) {
      console.error("Error fetching registrations:", error);
      toast.error("Failed to load registrations");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (registration: Registration) => {
    setSelectedRegistration(registration);
    setActionType("approve");
  };

  const handleReject = async (registration: Registration) => {
    setSelectedRegistration(registration);
    setActionType("reject");
  };

  const handleSuspend = async (registration: Registration) => {
    setSelectedRegistration(registration);
    setActionType("suspend");
  };

  const handleDelete = async (registration: Registration) => {
    setSelectedRegistration(registration);
    setActionType("delete");
    setDeleteConfirmation("");
  };

  const confirmAction = async () => {
    if (!selectedRegistration || !actionType) return;

    try {
      setProcessingId(selectedRegistration.id);

      let endpoint = `/api/admin/registrations/${selectedRegistration.id}`;
      let method = "POST";
      let body = null;

      // Delete uses DELETE method without action suffix
      if (actionType === "delete") {
        method = "DELETE";
      } else {
        endpoint += `/${actionType}`;
      }

      // Add rejection reason to request body if rejecting
      if (actionType === "reject" && rejectionReason.trim()) {
        body = JSON.stringify({ rejection_reason: rejectionReason.trim() });
      }

      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        ...(body && { body }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || `Failed to ${actionType} registration`);
      }

      const messages = {
        approve: "Registration approved successfully!",
        reject: "Registration rejected",
        suspend: "Organization suspended successfully",
        delete: "Organization deleted permanently",
      };
      toast.success(messages[actionType as keyof typeof messages]);

      await fetchRegistrations();
    } catch (error) {
      console.error(`Error ${actionType}ing registration:`, error);
      toast.error(error instanceof Error ? error.message : `Failed to ${actionType} registration`);
    } finally {
      setProcessingId(null);
      setSelectedRegistration(null);
      setActionType(null);
      setDeleteConfirmation("");
      setRejectionReason("");
    }
  };

  const getStatusBadge = (status: string) => {
    // Normalize status to uppercase for comparison
    const normalizedStatus = status.toUpperCase();

    const styles: Record<string, string> = {
      PENDING_APPROVAL: "bg-yellow-100 text-yellow-800 border-yellow-200",
      ACTIVE: "bg-green-100 text-green-800 border-green-200",
      SUSPENDED: "bg-red-100 text-red-800 border-red-200",
    };

    const icons: Record<string, React.ComponentType<{ className?: string }>> = {
      PENDING_APPROVAL: Clock,
      ACTIVE: CheckCircle,
      SUSPENDED: XCircle,
    };

    const labels: Record<string, string> = {
      PENDING_APPROVAL: "Pending",
      ACTIVE: "Approved",
      SUSPENDED: "Rejected",
    };

    const Icon = icons[normalizedStatus] || Clock;
    const label = labels[normalizedStatus] || status;
    const style = styles[normalizedStatus] || styles.PENDING_APPROVAL;

    return (
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${style}`}>
        <Icon className="h-3 w-3" />
        {label}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-[#5B8DBE]" />
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-2xl font-light text-[#2D3748] mb-1 tracking-tight">
          Business <span className="font-normal">Registrations</span>
        </h1>
        <p className="text-sm font-light text-[#6B7280]">
          Review and manage business account registrations
        </p>
      </div>

      <div className="space-y-6">

      {/* Filter Bar */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
              <Input
                type="text"
                placeholder="Search by company, email, or owner..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-10 border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE]"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#2D3748]"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Status Filter */}
            <div className="w-full sm:w-[200px]">
              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
                <SelectTrigger className="h-10 border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE]">
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-[#6B7280]" />
                    <SelectValue placeholder="Filter by status" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="pending">Pending Approval</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Results Count */}
          <div className="mt-4 text-sm text-[#6B7280]">
            Showing <span className="font-medium text-[#2D3748]">{filteredRegistrations.length}</span> of{" "}
            <span className="font-medium text-[#2D3748]">{registrations.length}</span> registrations
          </div>
        </CardContent>
      </Card>

      {filteredRegistrations.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-normal text-[#2D3748] mb-2">
                No Results Found
              </h3>
              <p className="text-sm text-[#6B7280] font-light">
                {searchQuery && statusFilter !== "all" ? (
                  <>No registrations match your search and filter criteria.</>
                ) : searchQuery ? (
                  <>No registrations match your search for &ldquo;{searchQuery}&rdquo;.</>
                ) : statusFilter !== "all" ? (
                  <>No registrations found with the selected status.</>
                ) : (
                  <>There are no business registrations yet.</>
                )}
              </p>
              {(searchQuery || statusFilter !== "all") && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSearchQuery("");
                    setStatusFilter("all");
                  }}
                  className="mt-4"
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Registrations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Company</TableHead>
                    <TableHead>Business Contact</TableHead>
                    <TableHead>Account Owner</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRegistrations.map((registration) => (
                    <TableRow key={registration.id}>
                      <TableCell>
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-10 h-10 bg-[#5B8DBE]/10 rounded-lg flex items-center justify-center">
                            <Building className="h-5 w-5 text-[#5B8DBE]" />
                          </div>
                          <div>
                            <div className="font-medium text-[#2D3748]">
                              {registration.name}
                            </div>
                            <div className="text-sm text-[#6B7280] font-light">
                              {registration.slug}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-sm">
                            <Mail className="h-4 w-4 text-gray-400" />
                            <span className="text-[#2D3748]">
                              {registration.business_email}
                            </span>
                          </div>
                          {registration.business_phone && (
                            <div className="flex items-center gap-2 text-sm">
                              <Phone className="h-4 w-4 text-gray-400" />
                              <span className="text-[#6B7280]">
                                {registration.business_phone}
                              </span>
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {registration.requested_by ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 text-sm">
                              <User className="h-4 w-4 text-gray-400" />
                              <span className="text-[#2D3748] font-medium">
                                {registration.requested_by.full_name}
                              </span>
                            </div>
                            <div className="text-sm text-[#6B7280] pl-6">
                              {registration.requested_by.email}
                            </div>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">N/A</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-[#2D3748]">
                          {format(new Date(registration.created_at), "MMM d, yyyy")}
                        </div>
                        <div className="text-xs text-[#6B7280]">
                          {format(new Date(registration.created_at), "h:mm a")}
                        </div>
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(registration.status)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {registration.status.toUpperCase() === "PENDING_APPROVAL" && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleReject(registration)}
                                disabled={processingId === registration.id}
                                className="h-8 text-xs"
                              >
                                <XCircle className="h-3.5 w-3.5 mr-1" />
                                Reject
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => handleApprove(registration)}
                                disabled={processingId === registration.id}
                                className="h-8 text-xs bg-[#5B8DBE] hover:bg-[#4A7AA8]"
                              >
                                {processingId === registration.id ? (
                                  <>
                                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                                    Processing...
                                  </>
                                ) : (
                                  <>
                                    <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                    Approve
                                  </>
                                )}
                              </Button>
                            </>
                          )}
                          {registration.status.toUpperCase() === "ACTIVE" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleSuspend(registration)}
                              disabled={processingId === registration.id}
                              className="h-8 text-xs border-orange-200 text-orange-600 hover:bg-orange-50"
                            >
                              <XCircle className="h-3.5 w-3.5 mr-1" />
                              Suspend
                            </Button>
                          )}
                          {registration.status.toUpperCase() === "SUSPENDED" && (
                            <Button
                              size="sm"
                              onClick={() => handleApprove(registration)}
                              disabled={processingId === registration.id}
                              className="h-8 text-xs bg-[#5B8DBE] hover:bg-[#4A7AA8]"
                            >
                              {processingId === registration.id ? (
                                <>
                                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                                  Processing...
                                </>
                              ) : (
                                <>
                                  <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                  Approve
                                </>
                              )}
                            </Button>
                          )}

                          {/* Delete button - available for all statuses */}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDelete(registration)}
                            disabled={processingId === registration.id}
                            className="h-8 text-xs border-red-300 text-red-700 hover:bg-red-100 hover:border-red-400"
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-1" />
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      <AlertDialog open={!!selectedRegistration && !!actionType} onOpenChange={() => {
        setSelectedRegistration(null);
        setActionType(null);
        setDeleteConfirmation("");
        setRejectionReason("");
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {actionType === "approve" && "Approve Registration?"}
              {actionType === "reject" && "Reject Registration?"}
              {actionType === "suspend" && "Suspend Organization?"}
              {actionType === "delete" && "⚠️ Permanently Delete Organization?"}
            </AlertDialogTitle>
            {actionType !== "delete" && (
              <AlertDialogDescription>
                {actionType === "approve" && (
                  <>
                    Are you sure you want to approve <strong>{selectedRegistration?.name}</strong>?
                    <br /><br />
                    This will activate the organization and enable login access.
                  </>
                )}
                {actionType === "reject" && (
                  <>
                    Are you sure you want to reject <strong>{selectedRegistration?.name}</strong>?
                    <br /><br />
                    This will prevent the business from accessing the platform.
                  </>
                )}
                {actionType === "suspend" && (
                  <>
                    Are you sure you want to suspend <strong>{selectedRegistration?.name}</strong>?
                    <br /><br />
                    This will revoke access and prevent users from logging in. The organization can be reactivated later.
                  </>
                )}
              </AlertDialogDescription>
            )}
          </AlertDialogHeader>

          {/* Delete content - outside header to avoid form element restrictions */}
          {actionType === "delete" && (
            <div className="px-6 space-y-4">
              <div className="text-sm text-muted-foreground">
                This action is IRREVERSIBLE and will permanently delete the organization, all users, leaflets, products, and API keys.
              </div>
              <div className="space-y-3 bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="font-semibold text-red-700 text-sm">
                  This will permanently delete:
                </div>
                <ul className="list-disc list-inside space-y-1 text-sm text-red-600">
                  <li>Organization: <strong>{selectedRegistration?.name}</strong></li>
                  <li>All users belonging only to this organization</li>
                  <li>All uploaded leaflets and extracted data</li>
                  <li>All products and analytics</li>
                  <li>All API keys and webhooks</li>
                </ul>
              </div>
              <div className="space-y-2">
                <label htmlFor="delete-confirm" className="text-sm font-medium text-gray-700 block">
                  Type <span className="font-semibold text-red-600">{selectedRegistration?.name}</span> to confirm:
                </label>
                <Input
                  id="delete-confirm"
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder="Enter organization name"
                  className="border-red-300 focus:border-red-500 focus:ring-red-500"
                />
              </div>
            </div>
          )}

          {/* Rejection reason input */}
          {actionType === "reject" && (
            <div className="px-6 space-y-2">
              <label htmlFor="rejection-reason" className="text-sm font-medium text-gray-700 block">
                Reason for rejection (optional):
              </label>
              <textarea
                id="rejection-reason"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Enter reason for rejecting this registration..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-[#5B8DBE] focus:border-transparent resize-none text-sm"
              />
              <p className="text-xs text-gray-500">
                This reason will be saved and can be viewed later. The user will not see this message automatically.
              </p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setDeleteConfirmation("");
              setRejectionReason("");
            }}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmAction}
              disabled={actionType === "delete" && deleteConfirmation !== selectedRegistration?.name}
              className={
                actionType === "delete"
                  ? "bg-red-700 hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
                  : actionType === "approve"
                    ? "bg-[#5B8DBE] hover:bg-[#4A7AA8]"
                    : "bg-red-600 hover:bg-red-700"
              }
            >
              {actionType === "approve" && "Approve"}
              {actionType === "reject" && "Reject"}
              {actionType === "suspend" && "Suspend"}
              {actionType === "delete" && "Delete Permanently"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </div>
  );
}
