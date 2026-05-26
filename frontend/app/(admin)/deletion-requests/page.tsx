"use client";

import { useState, useEffect, useCallback } from "react";
import { format } from "date-fns";
import Link from "next/link";
import {
  Trash2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  ArrowLeft,
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
import { Badge } from "@/components/ui/badge";
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
    switch (status) {
      case "pending":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Pending</Badge>;
      case "approved":
        return <Badge className="bg-green-100 text-green-800 border-green-200">Approved</Badge>;
      case "rejected":
        return <Badge className="bg-red-100 text-red-800 border-red-200">Rejected</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
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
      <div className="container mx-auto pb-6 max-w-7xl">
        <div className="mb-8">
          <Link href="/admin">
            <Button variant="outline" className="mb-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Admin Dashboard
            </Button>
          </Link>
          <h1 className="text-2xl font-light text-[#2D3748] mb-1 tracking-tight">
            Deletion <span className="font-normal">Requests</span>
          </h1>
          <p className="text-sm font-light text-[#6B7280]">
            Review and manage organization deletion requests
          </p>
        </div>
        <Card className="bg-white border-gray-200">
          <CardContent className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-[#6B7280]">Loading deletion requests...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-8">
        <Link href="/admin">
          <Button variant="outline" className="mb-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Admin Dashboard
          </Button>
        </Link>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-light text-[#2D3748] mb-1 tracking-tight">
              Deletion <span className="font-normal">Requests</span>
            </h1>
            <p className="text-sm font-light text-[#6B7280]">
              Review and manage organization deletion requests
            </p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-[#6B7280] mb-1">Total Requests</p>
                <p className="text-2xl font-light text-[#2D3748]">{requests.length}</p>
              </div>
              <FileText className="h-8 w-8 text-[#5B8DBE]" strokeWidth={1.5} />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-[#6B7280] mb-1">Pending</p>
                <p className="text-2xl font-light text-[#2D3748]">
                  {requests.filter(r => r.status === "pending").length}
                </p>
              </div>
              <Clock className="h-8 w-8 text-yellow-600" strokeWidth={1.5} />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-[#6B7280] mb-1">Approved</p>
                <p className="text-2xl font-light text-[#2D3748]">
                  {requests.filter(r => r.status === "approved").length}
                </p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-600" strokeWidth={1.5} />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-[#6B7280] mb-1">Rejected</p>
                <p className="text-2xl font-light text-[#2D3748]">
                  {requests.filter(r => r.status === "rejected").length}
                </p>
              </div>
              <XCircle className="h-8 w-8 text-red-600" strokeWidth={1.5} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white border-gray-200 mb-6">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
              <Input
                placeholder="Search by organization, user, or reason..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 border-gray-200 focus:border-[#5B8DBE] focus:ring-[#5B8DBE]"
              />
            </div>

            <div className="flex gap-4">
              <Select value={statusFilter} onValueChange={(value: StatusFilter) => setStatusFilter(value)}>
                <SelectTrigger className="w-[140px] border-gray-200">
                  <Filter className="h-4 w-4 mr-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Requests Table */}
      <Card className="bg-white border-gray-200">
        <CardHeader className="border-b border-gray-100 bg-[#F9FAFB]">
          <CardTitle className="text-lg font-light text-[#2D3748] flex items-center gap-3">
            <Trash2 className="h-5 w-5 text-[#5B8DBE]" strokeWidth={1.5} />
            Deletion Requests ({filteredRequests.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredRequests.length === 0 ? (
            <div className="text-center p-12">
              <div className="p-6 bg-gray-50 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center">
                <Trash2 className="h-12 w-12 text-gray-400" strokeWidth={1.5} />
              </div>
              <h3 className="text-xl font-light text-[#2D3748] mb-4">No Deletion Requests</h3>
              <p className="text-[#6B7280] max-w-md mx-auto">
                {statusFilter === "all"
                  ? "No deletion requests have been submitted yet."
                  : `No ${statusFilter} deletion requests found.`}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-gray-100">
                  <TableHead className="font-light text-[#6B7280]">Organization</TableHead>
                  <TableHead className="font-light text-[#6B7280]">Type</TableHead>
                  <TableHead className="font-light text-[#6B7280]">Requested By</TableHead>
                  <TableHead className="font-light text-[#6B7280]">Reason</TableHead>
                  <TableHead className="font-light text-[#6B7280]">Status</TableHead>
                  <TableHead className="font-light text-[#6B7280]">Date</TableHead>
                  <TableHead className="font-light text-[#6B7280] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRequests.map((request) => (
                  <TableRow key={request.id} className="border-gray-100 hover:bg-[#F9FAFB]">
                    <TableCell>
                      <div>
                        <div className="font-medium text-[#2D3748]">
                          {request.organization_name}
                        </div>
                        <div className="text-sm text-[#6B7280]">
                          ID: {request.organization_id.slice(0, 8)}...
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getTypeIcon(request.request_type)}
                        <span className="capitalize">{request.request_type}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium text-[#2D3748]">
                          {request.requested_by.full_name}
                        </div>
                        <div className="text-sm text-[#6B7280]">
                          {request.requested_by.email}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="max-w-xs truncate text-[#2D3748]" title={request.reason}>
                        {request.reason}
                      </div>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(request.status)}
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-[#6B7280]">
                        {format(new Date(request.created_at), 'MMM d, yyyy')}
                        <br />
                        <span className="text-xs">
                          {format(new Date(request.created_at), 'h:mm a')}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {request.status === "pending" && (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openRejectDialog(request)}
                            disabled={processingId === request.id}
                            className="hover:bg-red-50 hover:border-red-200"
                          >
                            <XCircle className="h-4 w-4 text-red-600" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openApproveDialog(request)}
                            disabled={processingId === request.id}
                            className="hover:bg-red-100 hover:border-red-300"
                          >
                            <AlertTriangle className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Approve Dialog */}
      <Dialog open={isApproveDialogOpen} onOpenChange={setIsApproveDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              Approve Deletion Request
            </DialogTitle>
            <DialogDescription>
              This action will permanently delete the organization and all associated data. This cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {selectedRequest && (
            <div className="space-y-4">
              <div className="p-4 bg-red-50 border border-red-200 rounded-md">
                <h4 className="font-medium text-red-800 mb-2">What will be deleted:</h4>
                <ul className="text-sm text-red-700 space-y-1">
                  <li>• Organization: {selectedRequest.organization_name}</li>
                  <li>• All leaflets and product data</li>
                  <li>• All user accounts and access</li>
                  <li>• All billing and usage history</li>
                  <li>• All integrations and settings</li>
                </ul>
              </div>

              <div className="space-y-2">
                <Label htmlFor="admin-notes">Admin Notes (optional)</Label>
                <Textarea
                  id="admin-notes"
                  placeholder="Add any notes about this approval..."
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmation">
                  Type <span className="font-mono bg-gray-100 px-1 rounded">PERMANENTLY DELETE</span> to confirm
                </Label>
                <Input
                  id="confirmation"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  placeholder="PERMANENTLY DELETE"
                  className="font-mono"
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
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleApproveRequest}
              disabled={confirmationText !== "PERMANENTLY DELETE" || processingId === selectedRequest?.id}
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
            <DialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Reject Deletion Request
            </DialogTitle>
            <DialogDescription>
              Provide a reason for rejecting this deletion request.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="rejection-reason">Rejection Reason *</Label>
              <Textarea
                id="rejection-reason"
                placeholder="Please explain why this deletion request is being rejected..."
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={4}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="admin-notes-reject">Admin Notes (optional)</Label>
              <Textarea
                id="admin-notes-reject"
                placeholder="Add any additional notes..."
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={2}
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
            >
              Cancel
            </Button>
            <Button
              onClick={handleRejectRequest}
              disabled={!rejectionReason.trim() || processingId === selectedRequest?.id}
              className="bg-red-600 hover:bg-red-700"
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