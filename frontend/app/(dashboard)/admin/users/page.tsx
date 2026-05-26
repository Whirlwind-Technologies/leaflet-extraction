"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { toast } from "sonner";
import { brandColors as colors } from "@/lib/brand-colors";
import {
  Users,
  Plus,
  Search,
  AlertTriangle,
  CheckCircle,
  Loader2,
  MoreHorizontal,
  Trash2,
  Edit,
  RefreshCw,
  ShieldCheck,
  Key,
  UserCheck,
  UserX,
  Building2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Clock,
  XCircle,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  toggleUserActive,
  resetUserPassword,
  getAllOrganizations,
  approveUser,
  rejectUser,
  UserResponse,
  UserCreate,
  UserUpdate,
  OrganizationInfo,
} from "@/lib/actions/admin";

type SortField = "full_name" | "email" | "organization" | "is_active" | "is_superuser" | "leaflet_count" | "product_count" | "total_cost" | "last_login" | "created_at";
type SortDirection = "asc" | "desc";
type ViewTab = "all" | "pending";

export default function UserManagementPage() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [organizationFilter, setOrganizationFilter] = useState<string>("all");
  const [page] = useState(1);
  const [pageSize] = useState(20);
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [viewTab, setViewTab] = useState<ViewTab>("all");

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [resetPasswordDialogOpen, setResetPasswordDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [formLoading, setFormLoading] = useState(false);

  // Inline action loading states (keyed by user ID)
  const [approvingUsers, setApprovingUsers] = useState<Set<string>>(new Set());
  const [rejectingUser, setRejectingUser] = useState(false);

  // Create form state
  const [createFormData, setCreateFormData] = useState<UserCreate>({
    email: "",
    password: "",
    full_name: "",
    is_active: true,
    is_superuser: false,
    is_verified: false,
  });

  // Edit form state
  const [editFormData, setEditFormData] = useState<UserUpdate>({});

  // Reset password state
  const [newPassword, setNewPassword] = useState("");

  // Reject form state
  const [rejectionReason, setRejectionReason] = useState("");

  // Derived: count of pending users (inactive and not verified)
  const pendingUsersCount = useMemo(
    () => users.filter((u) => !u.is_active && !u.is_verified).length,
    [users]
  );

  // Load organizations on mount
  useEffect(() => {
    loadOrganizations();
  }, []);

  const loadOrganizations = async () => {
    try {
      const result = await getAllOrganizations();
      if (result.success && result.data) {
        setOrganizations(result.data);
      }
    } catch (error) {
      console.error("Failed to load organizations:", error);
    }
  };

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getUsers({
        page,
        page_size: pageSize,
        search: searchTerm || undefined,
        is_active: statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined,
        is_superuser: roleFilter === "superuser" ? true : roleFilter === "user" ? false : undefined,
        organization_id: organizationFilter !== "all" ? organizationFilter : undefined,
      });

      if (result.success && result.data) {
        setUsers(result.data);
      } else {
        toast.error(result.error || "Failed to load users");
      }
    } catch (error) {
      toast.error("Failed to load users");
      console.error("Load users error:", error);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, statusFilter, roleFilter, organizationFilter, page, pageSize]);

  // Load users on mount and filter change
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Filter users based on active tab
  const filteredByTab = useMemo(() => {
    if (viewTab === "pending") {
      return users.filter((u) => !u.is_active && !u.is_verified);
    }
    return users;
  }, [users, viewTab]);

  // Sort users client-side
  const sortedUsers = useMemo(() => {
    return [...filteredByTab].sort((a, b) => {
      let aValue: string | number | boolean | null = null;
      let bValue: string | number | boolean | null = null;

      switch (sortField) {
        case "full_name":
          aValue = a.full_name?.toLowerCase() || "";
          bValue = b.full_name?.toLowerCase() || "";
          break;
        case "email":
          aValue = a.email.toLowerCase();
          bValue = b.email.toLowerCase();
          break;
        case "organization":
          aValue = a.organizations?.[0]?.name?.toLowerCase() || "";
          bValue = b.organizations?.[0]?.name?.toLowerCase() || "";
          break;
        case "is_active":
          aValue = a.is_active ? 1 : 0;
          bValue = b.is_active ? 1 : 0;
          break;
        case "is_superuser":
          aValue = a.is_superuser ? 1 : 0;
          bValue = b.is_superuser ? 1 : 0;
          break;
        case "leaflet_count":
          aValue = a.leaflet_count;
          bValue = b.leaflet_count;
          break;
        case "product_count":
          aValue = a.product_count;
          bValue = b.product_count;
          break;
        case "total_cost":
          aValue = a.total_cost;
          bValue = b.total_cost;
          break;
        case "last_login":
          aValue = a.last_login ? new Date(a.last_login).getTime() : 0;
          bValue = b.last_login ? new Date(b.last_login).getTime() : 0;
          break;
        case "created_at":
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
      }

      if (aValue === bValue) return 0;
      if (aValue === null || aValue === "") return 1;
      if (bValue === null || bValue === "") return -1;

      const comparison = aValue < bValue ? -1 : 1;
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [filteredByTab, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const SortableHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <button
      onClick={() => handleSort(field)}
      className={`flex items-center gap-1 transition-colors ${sortField === field ? "text-gray-900" : "text-gray-500"}`}
    >
      {children}
      {sortField === field ? (
        sortDirection === "asc" ? (
          <ArrowUp className="h-3 w-3" strokeWidth={1.5} />
        ) : (
          <ArrowDown className="h-3 w-3" strokeWidth={1.5} />
        )
      ) : (
        <ArrowUpDown className="h-3 w-3 opacity-50" strokeWidth={1.5} />
      )}
    </button>
  );

  // Helper: is user pending approval?
  const isPendingApproval = (user: UserResponse) => !user.is_active && !user.is_verified;

  const handleCreateUser = async () => {
    if (!createFormData.email || !createFormData.password) {
      toast.error("Email and password are required");
      return;
    }

    setFormLoading(true);
    try {
      const result = await createUser(createFormData);

      if (result.success) {
        toast.success("User created successfully");
        setCreateDialogOpen(false);
        setCreateFormData({
          email: "",
          password: "",
          full_name: "",
          is_active: true,
          is_superuser: false,
          is_verified: false,
        });
        loadUsers();
      } else {
        toast.error(result.error || "Failed to create user");
      }
    } catch {
      toast.error("Failed to create user");
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!selectedUser) return;

    setFormLoading(true);
    try {
      const result = await updateUser(selectedUser.id, editFormData);

      if (result.success) {
        toast.success("User updated successfully");
        setEditDialogOpen(false);
        setSelectedUser(null);
        setEditFormData({});
        loadUsers();
      } else {
        toast.error(result.error || "Failed to update user");
      }
    } catch {
      toast.error("Failed to update user");
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;

    setFormLoading(true);
    try {
      const result = await deleteUser(selectedUser.id);

      if (result.success) {
        toast.success("User deleted successfully");
        setDeleteDialogOpen(false);
        setSelectedUser(null);
        loadUsers();
      } else {
        toast.error(result.error || "Failed to delete user");
      }
    } catch {
      toast.error("Failed to delete user");
    } finally {
      setFormLoading(false);
    }
  };

  const handleToggleActive = async (user: UserResponse) => {
    try {
      const result = await toggleUserActive(user.id);

      if (result.success) {
        toast.success(result.data?.message || "User status updated");
        loadUsers();
      } else {
        toast.error(result.error || "Failed to update user status");
      }
    } catch {
      toast.error("Failed to update user status");
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUser || !newPassword) return;

    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    setFormLoading(true);
    try {
      const result = await resetUserPassword(selectedUser.id, newPassword);

      if (result.success) {
        toast.success("Password reset successfully");
        setResetPasswordDialogOpen(false);
        setSelectedUser(null);
        setNewPassword("");
      } else {
        toast.error(result.error || "Failed to reset password");
      }
    } catch {
      toast.error("Failed to reset password");
    } finally {
      setFormLoading(false);
    }
  };

  const handleApproveUser = async (user: UserResponse) => {
    setApprovingUsers((prev) => new Set(prev).add(user.id));
    try {
      const result = await approveUser(user.id);

      if (result.success) {
        toast.success(result.data?.message || `${user.email} has been approved`);
        loadUsers();
      } else {
        toast.error(result.error || "Failed to approve user");
      }
    } catch {
      toast.error("Failed to approve user");
    } finally {
      setApprovingUsers((prev) => {
        const next = new Set(prev);
        next.delete(user.id);
        return next;
      });
    }
  };

  const handleRejectUser = async () => {
    if (!selectedUser) return;

    setRejectingUser(true);
    try {
      const result = await rejectUser(
        selectedUser.id,
        rejectionReason.trim() || undefined
      );

      if (result.success) {
        toast.success(result.data?.message || `${selectedUser.email} registration rejected`);
        setRejectDialogOpen(false);
        setSelectedUser(null);
        setRejectionReason("");
        loadUsers();
      } else {
        toast.error(result.error || "Failed to reject user");
      }
    } catch {
      toast.error("Failed to reject user");
    } finally {
      setRejectingUser(false);
    }
  };

  const openEditDialog = (user: UserResponse) => {
    setSelectedUser(user);
    setEditFormData({
      email: user.email,
      full_name: user.full_name || "",
      is_active: user.is_active,
      is_superuser: user.is_superuser,
      is_verified: user.is_verified,
    });
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (user: UserResponse) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const openResetPasswordDialog = (user: UserResponse) => {
    setSelectedUser(user);
    setNewPassword("");
    setResetPasswordDialogOpen(true);
  };

  const openRejectDialog = (user: UserResponse) => {
    setSelectedUser(user);
    setRejectionReason("");
    setRejectDialogOpen(true);
  };

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <TooltipProvider>
      <div className="container mx-auto pb-6 max-w-7xl bg-gray-50">
        {/* Header */}
        <div className="mb-8">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
                User <span className="font-normal">Management</span>
              </h1>
              <p className="text-sm text-gray-500">
                Manage platform users, roles, and permissions
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={loadUsers}
                disabled={loading}
                className="hover:bg-gray-50 border-gray-200 text-gray-500"
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} strokeWidth={1.5} />
                Refresh
              </Button>
              <Button
                onClick={() => setCreateDialogOpen(true)}
                style={{ backgroundColor: colors.primaryBrandBlue }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add User
              </Button>
            </div>
          </div>
        </div>

        {/* Pending Approval Banner */}
        {pendingUsersCount > 0 && viewTab !== "pending" && (
          <div className="mb-6 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <Clock className="h-5 w-5 flex-shrink-0 text-amber-600" strokeWidth={1.5} />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800">
                {pendingUsersCount} user{pendingUsersCount !== 1 ? "s" : ""} pending approval
              </p>
              <p className="text-xs text-amber-600 mt-0.5">
                New registrations require admin approval before users can access the platform.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setViewTab("pending")}
              className="border-amber-300 text-amber-700 hover:bg-amber-100 hover:text-amber-800"
            >
              Review Now
            </Button>
          </div>
        )}

        {/* View Tabs */}
        <div className="mb-4 flex items-center gap-1 border-b border-gray-200">
          <button
            onClick={() => setViewTab("all")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              viewTab === "all"
                ? ""
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
            style={viewTab === "all" ? { borderColor: colors.primaryBrandBlue, color: colors.primaryBrandBlue } : undefined}
          >
            All Users
            <span className="ml-1.5 text-xs text-gray-400">({users.length})</span>
          </button>
          <button
            onClick={() => setViewTab("pending")}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
              viewTab === "pending"
                ? "border-amber-600 text-amber-600"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            Pending Approval
            {pendingUsersCount > 0 && (
              <Badge
                variant="secondary"
                className={`text-[10px] px-1.5 py-0 h-5 font-medium ${
                  viewTab === "pending"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-amber-100 text-amber-600"
                }`}
              >
                {pendingUsersCount}
              </Badge>
            )}
          </button>
        </div>

        {/* Filters */}
        <Card className="mb-6 border-gray-200">
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" strokeWidth={1.5} />
                <Input
                  placeholder="Search by email or name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 border-gray-200"
                />
              </div>
              <Select value={organizationFilter} onValueChange={setOrganizationFilter}>
                <SelectTrigger className="w-[200px] border-gray-200">
                  <Building2 className="h-4 w-4 mr-2 text-gray-400" strokeWidth={1.5} />
                  <SelectValue placeholder="All Organizations" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Organizations</SelectItem>
                  {organizations.map((org) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={roleFilter} onValueChange={setRoleFilter}>
                <SelectTrigger className="w-[150px] border-gray-200">
                  <SelectValue placeholder="All Roles" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Roles</SelectItem>
                  <SelectItem value="superuser">Super Admin</SelectItem>
                  <SelectItem value="user">Regular User</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px] border-gray-200">
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Users Table */}
        <Card className="border-gray-200">
          <CardHeader className="border-b border-gray-200 bg-gray-50">
            <CardTitle className="text-base font-normal flex items-center gap-2 text-gray-900">
              <Users className="h-5 w-5" strokeWidth={1.5} style={{ color: colors.primaryBrandBlue }} />
              {viewTab === "pending" ? "Pending Approval" : "Users"} ({sortedUsers.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin" strokeWidth={1.5} style={{ color: colors.primaryBrandBlue }} />
              </div>
            ) : sortedUsers.length === 0 ? (
              <div className="text-center py-12">
                {viewTab === "pending" ? (
                  <div className="flex flex-col items-center gap-2">
                    <CheckCircle className="h-8 w-8 text-green-500" strokeWidth={1.5} />
                    <p className="font-light text-gray-500">No users pending approval</p>
                    <p className="text-xs text-gray-400">All registrations have been reviewed</p>
                  </div>
                ) : (
                  <p className="font-light text-gray-500">No users found</p>
                )}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-100">
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                      <SortableHeader field="full_name">User</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                      <SortableHeader field="organization">Organization</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                      <SortableHeader field="is_active">Status</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                      <SortableHeader field="is_superuser">Role</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">
                      <SortableHeader field="leaflet_count">Leaflets</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">
                      <SortableHeader field="product_count">Products</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-right text-gray-500">
                      <SortableHeader field="total_cost">Cost</SortableHeader>
                    </TableHead>
                    <TableHead className="text-xs font-medium uppercase tracking-wider text-gray-500">
                      <SortableHeader field="last_login">Last Login</SortableHeader>
                    </TableHead>
                    <TableHead className="w-[120px] text-xs font-medium uppercase tracking-wider text-gray-500">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedUsers.map((user) => {
                    const pending = isPendingApproval(user);
                    const isApproving = approvingUsers.has(user.id);

                    return (
                      <TableRow
                        key={user.id}
                        className={`hover:bg-gray-50/50 ${
                          pending ? "bg-amber-50/30" : ""
                        }`}
                      >
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium text-gray-900">{user.full_name || "\u2014"}</span>
                            <span className="text-sm text-gray-500">{user.email}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {user.organizations && user.organizations.length > 0 ? (
                            <div className="flex flex-col gap-1">
                              {user.organizations.slice(0, 2).map((org) => (
                                <div key={org.id} className="flex items-center gap-1.5">
                                  <Building2 className="h-3 w-3 text-gray-400" strokeWidth={1.5} />
                                  <span className="text-sm text-gray-700">{org.name}</span>
                                </div>
                              ))}
                              {user.organizations.length > 2 && (
                                <span className="text-xs text-gray-400">
                                  +{user.organizations.length - 2} more
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-sm text-gray-400">No organization</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            {pending ? (
                              <Badge variant="outline" className="w-fit text-xs font-normal bg-amber-50 text-amber-700 border-amber-200">
                                <Clock className="h-3 w-3 mr-1" strokeWidth={1.5} />
                                Pending Approval
                              </Badge>
                            ) : user.is_active ? (
                              <Badge variant="outline" className="w-fit text-xs font-normal bg-green-50 text-green-700 border-green-200">
                                <CheckCircle className="h-3 w-3 mr-1" strokeWidth={1.5} />
                                Active
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="w-fit text-xs font-normal bg-red-50 text-red-700 border-red-200">
                                <AlertTriangle className="h-3 w-3 mr-1" strokeWidth={1.5} />
                                Inactive
                              </Badge>
                            )}
                            {user.is_verified && (
                              <Badge variant="outline" className="w-fit text-xs font-normal" style={{ backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: colors.secondarySteel }}>
                                Verified
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {user.is_superuser ? (
                            <Badge className="font-normal" style={{ backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: colors.secondarySteel }}>
                              <ShieldCheck className="h-3 w-3 mr-1" strokeWidth={1.5} />
                              Super Admin
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="font-normal bg-gray-100 text-gray-500 border-gray-200">
                              User
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-medium text-gray-900">
                          {user.leaflet_count.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right font-medium text-gray-900">
                          {user.product_count.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right font-medium text-gray-900">
                          ${user.total_cost.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-sm text-gray-500">
                          {formatDate(user.last_login)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            {/* Quick approve/reject buttons for pending users */}
                            {pending && (
                              <>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50"
                                      onClick={() => handleApproveUser(user)}
                                      disabled={isApproving}
                                    >
                                      {isApproving ? (
                                        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.5} />
                                      ) : (
                                        <UserCheck className="h-4 w-4" strokeWidth={1.5} />
                                      )}
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent side="top">
                                    <p>Approve user</p>
                                  </TooltipContent>
                                </Tooltip>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                      onClick={() => openRejectDialog(user)}
                                    >
                                      <XCircle className="h-4 w-4" strokeWidth={1.5} />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent side="top">
                                    <p>Reject registration</p>
                                  </TooltipContent>
                                </Tooltip>
                              </>
                            )}

                            {/* Standard dropdown menu */}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 text-gray-500">
                                  <MoreHorizontal className="h-4 w-4" strokeWidth={1.5} />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuLabel className="text-xs font-normal text-gray-500">Actions</DropdownMenuLabel>
                                <DropdownMenuSeparator />

                                {/* Approve/Reject in dropdown for pending users */}
                                {pending && (
                                  <>
                                    <DropdownMenuItem
                                      onClick={() => handleApproveUser(user)}
                                      className="text-green-700"
                                      disabled={isApproving}
                                    >
                                      <UserCheck className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                      Approve
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={() => openRejectDialog(user)}
                                      className="text-red-600"
                                    >
                                      <XCircle className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                      Reject
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                  </>
                                )}

                                <DropdownMenuItem onClick={() => openEditDialog(user)} className="text-gray-700">
                                  <Edit className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                  Edit User
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => openResetPasswordDialog(user)} className="text-gray-700">
                                  <Key className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                  Reset Password
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handleToggleActive(user)} className="text-gray-700">
                                  {user.is_active ? (
                                    <>
                                      <UserX className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                      Deactivate
                                    </>
                                  ) : (
                                    <>
                                      <UserCheck className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                      Activate
                                    </>
                                  )}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  onClick={() => openDeleteDialog(user)}
                                  className="text-red-600"
                                >
                                  <Trash2 className="h-4 w-4 mr-2" strokeWidth={1.5} />
                                  Delete User
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Create User Dialog */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-normal text-gray-900">Create New User</DialogTitle>
              <DialogDescription className="text-gray-500">
                Add a new user to the platform
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="create-email" className="text-gray-700">Email *</Label>
                <Input
                  id="create-email"
                  type="email"
                  placeholder="user@example.com"
                  value={createFormData.email}
                  onChange={(e) => setCreateFormData({ ...createFormData, email: e.target.value })}
                  className="border-gray-200"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-password" className="text-gray-700">Password *</Label>
                <Input
                  id="create-password"
                  type="password"
                  placeholder="Minimum 8 characters"
                  value={createFormData.password}
                  onChange={(e) => setCreateFormData({ ...createFormData, password: e.target.value })}
                  className="border-gray-200"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="create-name" className="text-gray-700">Full Name</Label>
                <Input
                  id="create-name"
                  placeholder="John Doe"
                  value={createFormData.full_name || ""}
                  onChange={(e) => setCreateFormData({ ...createFormData, full_name: e.target.value })}
                  className="border-gray-200"
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Active</Label>
                  <p className="text-xs text-gray-400">User can log in</p>
                </div>
                <Switch
                  checked={createFormData.is_active}
                  onCheckedChange={(checked) => setCreateFormData({ ...createFormData, is_active: checked })}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Verified</Label>
                  <p className="text-xs text-gray-400">Email is verified</p>
                </div>
                <Switch
                  checked={createFormData.is_verified}
                  onCheckedChange={(checked) => setCreateFormData({ ...createFormData, is_verified: checked })}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Super Admin</Label>
                  <p className="text-xs text-gray-400">Full platform access</p>
                </div>
                <Switch
                  checked={createFormData.is_superuser}
                  onCheckedChange={(checked) => setCreateFormData({ ...createFormData, is_superuser: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="border-gray-200">
                Cancel
              </Button>
              <Button
                onClick={handleCreateUser}
                disabled={formLoading}
                className="hover:opacity-90 text-white"
                style={{ backgroundColor: colors.primaryBrandBlue }}
              >
                {formLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" strokeWidth={1.5} />}
                Create User
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit User Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={(open) => {
          setEditDialogOpen(open);
          if (!open) setSelectedUser(null);
        }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-normal text-gray-900">Edit User</DialogTitle>
              <DialogDescription className="text-gray-500">
                Update user details and permissions
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-email" className="text-gray-700">Email</Label>
                <Input
                  id="edit-email"
                  type="email"
                  value={editFormData.email || ""}
                  onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })}
                  className="border-gray-200"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-name" className="text-gray-700">Full Name</Label>
                <Input
                  id="edit-name"
                  value={editFormData.full_name || ""}
                  onChange={(e) => setEditFormData({ ...editFormData, full_name: e.target.value })}
                  className="border-gray-200"
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Active</Label>
                  <p className="text-xs text-gray-400">User can log in</p>
                </div>
                <Switch
                  checked={editFormData.is_active}
                  onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_active: checked })}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Verified</Label>
                  <p className="text-xs text-gray-400">Email is verified</p>
                </div>
                <Switch
                  checked={editFormData.is_verified}
                  onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_verified: checked })}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <div className="space-y-0.5">
                  <Label className="text-gray-700">Super Admin</Label>
                  <p className="text-xs text-gray-400">Full platform access</p>
                </div>
                <Switch
                  checked={editFormData.is_superuser}
                  onCheckedChange={(checked) => setEditFormData({ ...editFormData, is_superuser: checked })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="border-gray-200">
                Cancel
              </Button>
              <Button
                onClick={handleUpdateUser}
                disabled={formLoading}
                className="hover:opacity-90 text-white"
                style={{ backgroundColor: colors.primaryBrandBlue }}
              >
                {formLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" strokeWidth={1.5} />}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete User Dialog */}
        <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
          if (!formLoading) {
            setDeleteDialogOpen(open);
            if (!open) setSelectedUser(null);
          }
        }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 font-normal text-red-600">
                <AlertTriangle className="h-5 w-5" strokeWidth={1.5} />
                Delete User
              </DialogTitle>
              <DialogDescription className="text-gray-500">
                Are you sure you want to delete this user? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>

            {selectedUser && (
              <div className="my-4 p-4 rounded-lg bg-gray-100 border border-gray-200">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Email:</span>
                    <span className="text-sm font-medium text-gray-900">{selectedUser.email}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Name:</span>
                    <span className="text-sm text-gray-700">{selectedUser.full_name || "\u2014"}</span>
                  </div>
                  {selectedUser.organizations && selectedUser.organizations.length > 0 && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Organization:</span>
                      <span className="text-sm text-gray-700">{selectedUser.organizations[0].name}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Leaflets:</span>
                    <span className="text-sm text-gray-700">{selectedUser.leaflet_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Products:</span>
                    <span className="text-sm text-gray-700">{selectedUser.product_count}</span>
                  </div>
                </div>
              </div>
            )}

            {selectedUser && (selectedUser.leaflet_count > 0 || selectedUser.product_count > 0) && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-yellow-50 border border-yellow-300">
                <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0 text-yellow-600" strokeWidth={1.5} />
                <p className="text-sm text-yellow-700">
                  This user has associated data. Deleting them may affect existing leaflets and products.
                </p>
              </div>
            )}

            <DialogFooter className="gap-3">
              <Button
                variant="outline"
                onClick={() => setDeleteDialogOpen(false)}
                disabled={formLoading}
                className="border-gray-200"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteUser}
                disabled={formLoading}
                className="hover:opacity-90 bg-red-600"
              >
                {formLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" strokeWidth={1.5} />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4 mr-2" strokeWidth={1.5} />
                    Delete User
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Reset Password Dialog */}
        <Dialog open={resetPasswordDialogOpen} onOpenChange={(open) => {
          if (!formLoading) {
            setResetPasswordDialogOpen(open);
            if (!open) {
              setSelectedUser(null);
              setNewPassword("");
            }
          }
        }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 font-normal text-gray-900">
                <Key className="h-5 w-5" strokeWidth={1.5} style={{ color: colors.primaryBrandBlue }} />
                Reset Password
              </DialogTitle>
              <DialogDescription className="text-gray-500">
                Set a new password for {selectedUser?.email}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="new-password" className="text-gray-700">New Password</Label>
                <Input
                  id="new-password"
                  type="password"
                  placeholder="Minimum 8 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="border-gray-200"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setResetPasswordDialogOpen(false)}
                disabled={formLoading}
                className="border-gray-200"
              >
                Cancel
              </Button>
              <Button
                onClick={handleResetPassword}
                disabled={formLoading || newPassword.length < 8}
                className="hover:opacity-90 text-white"
                style={{ backgroundColor: colors.primaryBrandBlue }}
              >
                {formLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" strokeWidth={1.5} />
                    Resetting...
                  </>
                ) : (
                  "Reset Password"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Reject User Dialog */}
        <Dialog open={rejectDialogOpen} onOpenChange={(open) => {
          if (!rejectingUser) {
            setRejectDialogOpen(open);
            if (!open) {
              setSelectedUser(null);
              setRejectionReason("");
            }
          }
        }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 font-normal text-red-600">
                <XCircle className="h-5 w-5" strokeWidth={1.5} />
                Reject Registration
              </DialogTitle>
              <DialogDescription className="text-gray-500">
                Reject the registration for {selectedUser?.email}. The user will remain inactive
                and receive a notification email.
              </DialogDescription>
            </DialogHeader>

            {selectedUser && (
              <div className="my-2 p-3 rounded-lg bg-gray-100 border border-gray-200">
                <div className="space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Name:</span>
                    <span className="text-sm font-medium text-gray-900">{selectedUser.full_name || "\u2014"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Email:</span>
                    <span className="text-sm text-gray-700">{selectedUser.email}</span>
                  </div>
                  {selectedUser.organizations && selectedUser.organizations.length > 0 && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-500">Organization:</span>
                      <span className="text-sm text-gray-700">{selectedUser.organizations[0].name}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-500">Registered:</span>
                    <span className="text-sm text-gray-700">{formatDate(selectedUser.created_at)}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="rejection-reason" className="text-gray-700">
                Reason for rejection <span className="text-gray-400 font-normal">(optional)</span>
              </Label>
              <Textarea
                id="rejection-reason"
                placeholder="Provide a reason so the user understands why their registration was not approved..."
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                className="border-gray-200 resize-none"
                rows={3}
              />
              <p className="text-xs text-gray-400">
                This reason will be included in the rejection email sent to the user.
              </p>
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                variant="outline"
                onClick={() => setRejectDialogOpen(false)}
                disabled={rejectingUser}
                className="border-gray-200"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleRejectUser}
                disabled={rejectingUser}
                className="hover:opacity-90 bg-red-600"
              >
                {rejectingUser ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" strokeWidth={1.5} />
                    Rejecting...
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-2" strokeWidth={1.5} />
                    Reject Registration
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
