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
import {
  getRegistrations,
  approveRegistration,
  rejectRegistration,
  suspendRegistration,
  deleteRegistration,
  type Registration,
} from "@/lib/actions/admin";

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
      const result = await getRegistrations({ page_size: 100 });
      if (result.success && result.data) {
        const items = (result.data.items || []) as Registration[];
        setRegistrations(items);
        setFilteredRegistrations(items);
      } else {
        throw new Error(result.error || "Failed to fetch registrations");
      }
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

      let result;
      if (actionType === "approve") {
        result = await approveRegistration(selectedRegistration.id);
      } else if (actionType === "reject") {
        result = await rejectRegistration(selectedRegistration.id, rejectionReason.trim() || undefined);
      } else if (actionType === "suspend") {
        result = await suspendRegistration(selectedRegistration.id);
      } else if (actionType === "delete") {
        result = await deleteRegistration(selectedRegistration.id);
      }

      if (!result?.success) {
        throw new Error(result?.error || `Failed to ${actionType} registration`);
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

    const styles: Record<string, { bg: string; text: string; border: string }> = {
      PENDING_APPROVAL: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
      ACTIVE: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
      SUSPENDED: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
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
    const styleObj = styles[normalizedStatus] || styles.PENDING_APPROVAL;

    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${styleObj.bg} ${styleObj.text} ${styleObj.border}`}
      >
        <Icon className="h-3 w-3" />
        {label}
      </div>
    );
  };

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
          Business <span className="font-normal">Registrations</span>
        </h1>
        <p className="text-sm text-gray-500">
          Review and manage business account registrations
        </p>
      </div>

      <div className="space-y-6">

      {/* Filter Bar */}
      <Card className="border-gray-200">
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <Input
                type="text"
                placeholder="Search by company, email, or owner..."
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

            {/* Status Filter */}
            <div className="w-full sm:w-[200px]">
              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
                <SelectTrigger className="h-10 border-gray-200">
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-gray-500" />
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
          <div className="mt-4 text-sm text-gray-500">
            Showing <span className="font-medium text-gray-900">{filteredRegistrations.length}</span> of{" "}
            <span className="font-medium text-gray-900">{registrations.length}</span> registrations
          </div>
        </CardContent>
      </Card>

      {filteredRegistrations.length === 0 ? (
        <Card className="border-gray-200">
          <CardContent className="py-12">
            <div className="text-center">
              <Search className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-normal mb-2 text-gray-900">
                No Results Found
              </h3>
              <p className="text-sm text-gray-500">
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
                  className="mt-4 border-gray-200"
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-gray-200">
          <CardHeader className="bg-gray-50 border-b border-gray-200">
            <CardTitle className="text-base text-gray-900">Registrations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-gray-200">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-100">
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Company</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Business Contact</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Account Owner</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Submitted</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Status</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRegistrations.map((registration) => (
                    <TableRow key={registration.id} className="hover:bg-gray-50/50">
                      <TableCell>
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-blue-50">
                            <Building className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <div className="font-medium text-gray-900">
                              {registration.name}
                            </div>
                            <div className="text-sm text-gray-500">
                              {registration.slug}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-sm">
                            <Mail className="h-4 w-4 text-gray-400" />
                            <span className="text-gray-900">
                              {registration.business_email}
                            </span>
                          </div>
                          {registration.business_phone && (
                            <div className="flex items-center gap-2 text-sm">
                              <Phone className="h-4 w-4 text-gray-400" />
                              <span className="text-gray-500">
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
                              <span className="font-medium text-gray-900">
                                {registration.requested_by.full_name}
                              </span>
                            </div>
                            <div className="text-sm pl-6 text-gray-500">
                              {registration.requested_by.email}
                            </div>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">N/A</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-gray-900">
                          {format(new Date(registration.created_at), "MMM d, yyyy")}
                        </div>
                        <div className="text-xs text-gray-500">
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
                                className="h-8 text-xs border-gray-200"
                              >
                                <XCircle className="h-3.5 w-3.5 mr-1" />
                                Reject
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => handleApprove(registration)}
                                disabled={processingId === registration.id}
                                className="h-8 text-xs hover:opacity-90 bg-blue-600"
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
                              className="h-8 text-xs border-yellow-300 text-yellow-600"
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
                              className="h-8 text-xs hover:opacity-90 bg-blue-600"
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
                            className="h-8 text-xs border-red-200 text-red-600"
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
            <AlertDialogTitle className={actionType === "delete" ? "text-red-600" : "text-gray-900"}>
              {actionType === "approve" && "Approve Registration?"}
              {actionType === "reject" && "Reject Registration?"}
              {actionType === "suspend" && "Suspend Organization?"}
              {actionType === "delete" && "Permanently Delete Organization?"}
            </AlertDialogTitle>
            {actionType !== "delete" && (
              <AlertDialogDescription className="text-gray-500">
                {actionType === "approve" && (
                  <>
                    Are you sure you want to approve <strong className="text-gray-900">{selectedRegistration?.name}</strong>?
                    <br /><br />
                    This will activate the organization and enable login access.
                  </>
                )}
                {actionType === "reject" && (
                  <>
                    Are you sure you want to reject <strong className="text-gray-900">{selectedRegistration?.name}</strong>?
                    <br /><br />
                    This will prevent the business from accessing the platform.
                  </>
                )}
                {actionType === "suspend" && (
                  <>
                    Are you sure you want to suspend <strong className="text-gray-900">{selectedRegistration?.name}</strong>?
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
              <div className="text-sm text-gray-500">
                This action is IRREVERSIBLE and will permanently delete the organization, all users, leaflets, products, and API keys.
              </div>
              <div className="space-y-3 rounded-lg p-4 bg-red-50 border border-red-200">
                <div className="font-semibold text-sm text-red-700">
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
                <label htmlFor="delete-confirm" className="text-sm font-medium block text-gray-700">
                  Type <span className="font-semibold text-red-600">{selectedRegistration?.name}</span> to confirm:
                </label>
                <Input
                  id="delete-confirm"
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  placeholder="Enter organization name"
                  className="border-red-200"
                />
              </div>
            </div>
          )}

          {/* Rejection reason input */}
          {actionType === "reject" && (
            <div className="px-6 space-y-2">
              <label htmlFor="rejection-reason" className="text-sm font-medium block text-gray-700">
                Reason for rejection (optional):
              </label>
              <textarea
                id="rejection-reason"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Enter reason for rejecting this registration..."
                rows={3}
                className="w-full px-3 py-2 rounded-md resize-none text-sm focus:outline-none focus:ring-2 border border-gray-200"
              />
              <p className="text-xs text-gray-400">
                This reason will be saved and can be viewed later. The user will not see this message automatically.
              </p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setDeleteConfirmation("");
                setRejectionReason("");
              }}
              className="border-gray-200"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmAction}
              disabled={actionType === "delete" && deleteConfirmation !== selectedRegistration?.name}
              className={`hover:opacity-90 ${actionType === "approve" ? "bg-blue-600" : "bg-red-600"} ${(actionType === "delete" && deleteConfirmation !== selectedRegistration?.name) ? "opacity-50" : ""}`}
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
