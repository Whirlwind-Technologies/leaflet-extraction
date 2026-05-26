"use client";

import { useState, useEffect, useCallback } from "react";
import { format } from "date-fns";
import {
  Trash2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  User,
  Building2,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";


import { toast } from "sonner";
import {
  getDeletionRequests,
  approveDeletionRequest,
  rejectDeletionRequest,
} from "@/lib/actions/admin";

interface DeletionRequest {
  id: string;
  organization_id: string;
  organization_name: string;
  request_type: "user" | "organization";
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: {
    id: string;
    email: string;
    full_name: string;
  };
  admin_notes?: string;
  created_at: string;
  reviewed_at?: string;
  reviewed_by?: string;
}

type StatusFilter = "all" | "pending" | "approved" | "rejected";

export default function DeletionRequestsPage() {
  const [requests, setRequests] = useState<DeletionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<DeletionRequest | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pending");
  const [searchQuery, setSearchQuery] = useState("");

  // Dialog states
  const [isApproveDialogOpen, setIsApproveDialogOpen] = useState(false);
  const [isRejectDialogOpen, setIsRejectDialogOpen] = useState(false);

  // Form states
  const [confirmationText, setConfirmationText] = useState("");
  const [adminNotes, setAdminNotes] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");

  const fetchRequests = useCallback(async () => {
    try {
      setLoading(true);
      const result = await getDeletionRequests({
        status: statusFilter === "all" ? undefined : statusFilter,
        page: 1,
        page_size: 100,
      });

      if (result.success) {
        const requests = result.data || [];
        setRequests(requests);
      } else {
        throw new Error(result.error || "Failed to fetch deletion requests");
      }
    } catch (error) {
      console.error("Error fetching deletion requests:", error);
      toast.error("Failed to load deletion requests");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleApproveRequest = async () => {
    if (!selectedRequest) return;

    if (confirmationText !== "PERMANENTLY DELETE") {
      toast.error("Please type 'PERMANENTLY DELETE' to confirm");
      return;
    }

    try {
      setProcessingId(selectedRequest.id);
      const result = await approveDeletionRequest(selectedRequest.id, {
        admin_notes: adminNotes,
        confirmation_text: confirmationText,
      });

      if (result.success) {
        toast.success("Deletion request approved and executed");
        setIsApproveDialogOpen(false);
        resetDialogStates();
        fetchRequests();
      } else {
        throw new Error(result.error || "Failed to approve deletion request");
      }
    } catch (error) {
      console.error("Error approving deletion request:", error);
      toast.error("Failed to approve deletion request");
    } finally {
      setProcessingId(null);
    }
  };

  const handleRejectRequest = async () => {
    if (!selectedRequest) return;

    if (!rejectionReason.trim()) {
      toast.error("Please provide a rejection reason");
      return;
    }

    try {
      setProcessingId(selectedRequest.id);
      const result = await rejectDeletionRequest(selectedRequest.id, {
        admin_notes: adminNotes,
        reason: rejectionReason,
      });

      if (result.success) {
        toast.success("Deletion request rejected");
        setIsRejectDialogOpen(false);
        resetDialogStates();
        fetchRequests();
      } else {
        throw new Error(result.error || "Failed to reject deletion request");
      }
    } catch (error) {
      console.error("Error rejecting deletion request:", error);
      toast.error("Failed to reject deletion request");
    } finally {
      setProcessingId(null);
    }
  };

  const resetDialogStates = () => {
    setSelectedRequest(null);
    setConfirmationText("");
    setAdminNotes("");
    setRejectionReason("");
  };

  const openApproveDialog = (request: DeletionRequest) => {
    setSelectedRequest(request);
    setIsApproveDialogOpen(true);
  };

  const openRejectDialog = (request: DeletionRequest) => {
    setSelectedRequest(request);
    setIsRejectDialogOpen(true);
  };

  const filteredRequests = requests.filter((request) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      request.organization_name.toLowerCase().includes(query) ||
      request.requested_by.email.toLowerCase().includes(query) ||
      request.requested_by.full_name.toLowerCase().includes(query) ||
      request.reason.toLowerCase().includes(query)
    );
  });

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; text: string; border: string }> = {
      pending: { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
      approved: { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
      rejected: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200" },
    };

    const icons: Record<string, React.ComponentType<{ className?: string }>> = {
      pending: Clock,
      approved: CheckCircle,
      rejected: XCircle,
    };

    const labels: Record<string, string> = {
      pending: "Pending",
      approved: "Approved",
      rejected: "Rejected",
    };

    const Icon = icons[status] || Clock;
    const label = labels[status] || status;
    const styleObj = styles[status] || styles.pending;

    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${styleObj.bg} ${styleObj.text} ${styleObj.border}`}
      >
        <Icon className="h-3 w-3" />
        {label}
      </div>
    );
  };

  const getTypeIcon = (type: string) => {
    return type === "organization" ? (
      <Building2 className="h-4 w-4 text-blue-600" />
    ) : (
      <User className="h-4 w-4 text-green-600" />
    );
  };

  if (loading) {
    return (
      <div className="container mx-auto pb-6 max-w-7xl bg-gray-50">
        <div className="mb-12">
          <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
            Deletion <span className="font-normal">Requests</span>
          </h1>
          <p className="text-sm text-gray-500">
            Review and manage organization deletion requests
          </p>
        </div>
        <Card className="bg-white border-gray-200">
          <CardContent className="p-12 text-center">
            <div
              className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto border-blue-600"
            ></div>
            <p className="mt-4 text-gray-500">Loading deletion requests...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl bg-gray-50">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
          Deletion <span className="font-normal">Requests</span>
        </h1>
        <p className="text-sm text-gray-500">
          Review and manage organization deletion requests
        </p>
      </div>

      <div className="space-y-6">

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Total Requests</p>
                <p className="text-3xl font-light mt-1 text-gray-900">{requests.length}</p>
              </div>
              <div className="p-3 rounded-lg bg-blue-50">
                <FileText className="h-6 w-6 text-blue-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Pending</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {requests.filter(r => r.status === "pending").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-yellow-50">
                <Clock className="h-6 w-6 text-yellow-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Approved</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {requests.filter(r => r.status === "approved").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-green-50">
                <CheckCircle className="h-6 w-6 text-green-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Rejected</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {requests.filter(r => r.status === "rejected").length}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-red-50">
                <XCircle className="h-6 w-6 text-red-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Bar */}
      <Card className="border-gray-200">
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <Input
                type="text"
                placeholder="Search by organization, user, or reason..."
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
              <Select value={statusFilter} onValueChange={(value: StatusFilter) => setStatusFilter(value)}>
                <SelectTrigger className="h-10 border-gray-200">
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-gray-500" />
                    <SelectValue placeholder="Filter by status" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Results Count */}
          <div className="mt-4 text-sm text-gray-500">
            Showing <span className="font-medium text-gray-900">{filteredRequests.length}</span> of{" "}
            <span className="font-medium text-gray-900">{requests.length}</span> requests
          </div>
        </CardContent>
      </Card>

      {filteredRequests.length === 0 ? (
        <Card className="border-gray-200">
          <CardContent className="py-12">
            <div className="text-center">
              <Trash2 className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <h3 className="text-lg font-normal mb-2 text-gray-900">
                No Results Found
              </h3>
              <p className="text-sm text-gray-500">
                {searchQuery && statusFilter !== "all" ? (
                  <>No deletion requests match your search and filter criteria.</>
                ) : searchQuery ? (
                  <>No deletion requests match your search for &ldquo;{searchQuery}&rdquo;.</>
                ) : statusFilter !== "all" ? (
                  <>No {statusFilter} deletion requests found.</>
                ) : (
                  <>There are no deletion requests yet.</>
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
            <CardTitle className="text-base text-gray-900">Deletion Requests</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-gray-200">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-100">
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Organization</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Type</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Requested By</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Reason</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Status</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">Submitted</TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRequests.map((request) => (
                    <TableRow key={request.id} className="hover:bg-gray-50/50">
                      <TableCell>
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-blue-50">
                            <Building2 className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <div className="font-medium text-gray-900">
                              {request.organization_name}
                            </div>
                            <div className="text-sm text-gray-500">
                              {request.organization_id.slice(0, 8)}...
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 text-sm">
                          {getTypeIcon(request.request_type)}
                          <span className="capitalize text-gray-900">{request.request_type}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 text-sm">
                            <User className="h-4 w-4 text-gray-400" />
                            <span className="font-medium text-gray-900">
                              {request.requested_by.full_name}
                            </span>
                          </div>
                          <div className="text-sm pl-6 text-gray-500">
                            {request.requested_by.email}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-xs truncate text-sm text-gray-900" title={request.reason}>
                          {request.reason}
                        </div>
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(request.status)}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm text-gray-900">
                          {format(new Date(request.created_at), 'MMM d, yyyy')}
                        </div>
                        <div className="text-xs text-gray-500">
                          {format(new Date(request.created_at), 'h:mm a')}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {request.status === "pending" && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openRejectDialog(request)}
                                disabled={processingId === request.id}
                                className="h-8 text-xs border-gray-200"
                              >
                                <XCircle className="h-3.5 w-3.5 mr-1 text-red-600" />
                                Reject
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => openApproveDialog(request)}
                                disabled={processingId === request.id}
                                className="h-8 text-xs hover:opacity-90 bg-red-600 text-white"
                              >
                                <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                                Delete
                              </Button>
                            </>
                          )}
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
      </div>

      {/* Approve Dialog */}
      <Dialog open={isApproveDialogOpen} onOpenChange={setIsApproveDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Approve Deletion Request
            </DialogTitle>
            <DialogDescription className="text-gray-500">
              This action will permanently delete the organization and all associated data. This cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {selectedRequest && (
            <div className="space-y-4">
              <div className="p-4 rounded-md border bg-red-50 border-red-200">
                <h4 className="font-medium mb-2 text-red-700">What will be deleted:</h4>
                <ul className="text-sm space-y-1 text-red-700">
                  <li>• Organization: {selectedRequest.organization_name}</li>
                  <li>• All leaflets and product data</li>
                  <li>• All user accounts and access</li>
                  <li>• All billing and usage history</li>
                  <li>• All integrations and settings</li>
                </ul>
              </div>

              <div className="space-y-2">
                <Label htmlFor="admin-notes" className="text-gray-700">Admin Notes (optional)</Label>
                <Textarea
                  id="admin-notes"
                  placeholder="Add any notes about this approval..."
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  rows={3}
                  className="border-gray-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmation" className="text-gray-700">
                  Type <span className="font-mono px-1 rounded bg-gray-100">PERMANENTLY DELETE</span> to confirm
                </Label>
                <Input
                  id="confirmation"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  placeholder="PERMANENTLY DELETE"
                  className="font-mono border-gray-200"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsApproveDialogOpen(false);
                resetDialogStates();
              }}
              className="border-gray-200 text-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleApproveRequest}
              disabled={confirmationText !== "PERMANENTLY DELETE" || processingId === selectedRequest?.id}
              className="bg-red-600 text-white"
            >
              {processingId === selectedRequest?.id ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Processing...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Confirm Deletion
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={isRejectDialogOpen} onOpenChange={setIsRejectDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-gray-900">
              <XCircle className="h-5 w-5 text-red-600" />
              Reject Deletion Request
            </DialogTitle>
            <DialogDescription className="text-gray-500">
              Provide a reason for rejecting this deletion request.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="rejection-reason" className="text-gray-700">Rejection Reason *</Label>
              <Textarea
                id="rejection-reason"
                placeholder="Please explain why this deletion request is being rejected..."
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={4}
                className="border-gray-200"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="admin-notes-reject" className="text-gray-700">Admin Notes (optional)</Label>
              <Textarea
                id="admin-notes-reject"
                placeholder="Add any additional notes..."
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={2}
                className="border-gray-200"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsRejectDialogOpen(false);
                resetDialogStates();
              }}
              className="border-gray-200 text-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleRejectRequest}
              disabled={!rejectionReason.trim() || processingId === selectedRequest?.id}
              className="bg-red-600 text-white"
            >
              {processingId === selectedRequest?.id ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Processing...
                </>
              ) : (
                "Reject Request"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
