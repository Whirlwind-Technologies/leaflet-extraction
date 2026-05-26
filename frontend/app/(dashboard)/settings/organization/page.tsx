"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { format } from "date-fns";
import {
  Users,
  Mail,
  UserPlus,
  Trash2,
  Shield,
  Crown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  getUserOrganizations,
  getOrganizationMembers,
  getOrganizationInvitations,
  sendOrganizationInvitation,
  resendOrganizationInvitation,
  revokeOrganizationInvitation,
  removeOrganizationMember,
  type OrganizationMember,
  type OrganizationInvitation,
} from "@/lib/actions/organizations";
import {
  Card,
  CardContent,
  CardDescription,
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
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function OrganizationSettingsPage() {
  const [orgId, setOrgId] = useState<string | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [processing, setProcessing] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<OrganizationMember | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [resendCooldowns, setResendCooldowns] = useState<Record<string, number>>({});
  const cooldownTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // Clean up cooldown timers on unmount
  useEffect(() => {
    const timers = cooldownTimers.current;
    return () => {
      Object.values(timers).forEach(clearInterval);
    };
  }, []);

  useEffect(() => {
    fetchCurrentOrganization();
  }, []);

  const fetchCurrentOrganization = async () => {
    try {
      const orgs = await getUserOrganizations();
      if (orgs.length > 0) {
        // Use the first organization (or you could use default_organization_id from user)
        setOrgId(orgs[0].id);
      } else {
        toast.error("No organization found");
        setLoading(false);
      }
    } catch (error) {
      console.error("Failed to fetch organization:", error);
      toast.error("Failed to load organization");
      setLoading(false);
    }
  };

  const fetchData = useCallback(async () => {
    if (!orgId) return;

    try {
      const [membersData, invitationsData] = await Promise.all([
        getOrganizationMembers(orgId),
        getOrganizationInvitations(orgId),
      ]);

      setMembers(membersData);
      setInvitations(invitationsData);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load organization data");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (orgId) {
      fetchData();
    }
  }, [orgId, fetchData]);

  const startResendCooldown = useCallback((invitationId: string) => {
    setResendCooldowns((prev) => ({ ...prev, [invitationId]: 60 }));

    // Clear any existing timer for this invitation
    if (cooldownTimers.current[invitationId]) {
      clearInterval(cooldownTimers.current[invitationId]);
    }

    cooldownTimers.current[invitationId] = setInterval(() => {
      setResendCooldowns((prev) => {
        const remaining = (prev[invitationId] ?? 0) - 1;
        if (remaining <= 0) {
          clearInterval(cooldownTimers.current[invitationId]);
          delete cooldownTimers.current[invitationId];
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { [invitationId]: _removed, ...rest } = prev;
          return rest;
        }
        return { ...prev, [invitationId]: remaining };
      });
    }, 1000);
  }, []);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) {
      toast.error("Please enter an email address");
      return;
    }

    if (!orgId) {
      toast.error("No organization selected");
      return;
    }

    setProcessing(true);
    try {
      const result = await sendOrganizationInvitation(orgId, inviteEmail, inviteRole);

      if (result.success) {
        const invitation = result.data;

        if (invitation?.email_sent) {
          toast.success(`Invitation sent to ${inviteEmail}`);
        } else if (invitation?.email_error) {
          toast.warning(
            `Invitation created but email failed to send: ${invitation.email_error}. You can resend from the invitations list.`
          );
        } else {
          toast.warning(
            "Invitation created. Email sending is currently disabled -- share the invitation link manually."
          );
        }

        setShowInviteDialog(false);
        setInviteEmail("");
        setInviteRole("member");
        fetchData();
      } else {
        toast.error(result.error || "Failed to send invitation");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setProcessing(false);
    }
  };

  const handleResendInvitation = async (invitation: OrganizationInvitation) => {
    if (!orgId) return;

    setResendingId(invitation.id);
    try {
      const result = await resendOrganizationInvitation(orgId, invitation.id);

      if (result.success) {
        if (result.data?.email_sent) {
          toast.success(`Invitation email resent to ${invitation.email}`);
        } else if (result.data?.email_error) {
          toast.warning(
            `Email failed to send: ${result.data.email_error}`
          );
        } else {
          toast.warning(
            "Email sending is currently disabled. The invitation remains active."
          );
        }
        startResendCooldown(invitation.id);
        fetchData();
      } else {
        toast.error(result.error || "Failed to resend invitation");
      }
    } catch {
      toast.error("An error occurred while resending");
    } finally {
      setResendingId(null);
    }
  };

  const handleRevokeInvitation = async (invitationId: string) => {
    if (!orgId) return;

    try {
      const result = await revokeOrganizationInvitation(orgId, invitationId);

      if (result.success) {
        toast.success("Invitation revoked");
        fetchData();
      } else {
        toast.error(result.error || "Failed to revoke invitation");
      }
    } catch {
      toast.error("An error occurred");
    }
  };

  const handleRemoveMember = async () => {
    if (!memberToRemove || !orgId) return;

    setProcessing(true);
    try {
      const result = await removeOrganizationMember(orgId, memberToRemove.user_id);

      if (result.success) {
        toast.success("Member removed successfully");
        setMemberToRemove(null);
        fetchData();
      } else {
        toast.error(result.error || "Failed to remove member");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setProcessing(false);
    }
  };

  const getRoleIcon = (role: string) => {
    switch (role.toLowerCase()) {
      case "owner":
        return <Crown className="h-3.5 w-3.5" />;
      case "admin":
        return <Shield className="h-3.5 w-3.5" />;
      default:
        return <Users className="h-3.5 w-3.5" />;
    }
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role.toLowerCase()) {
      case "owner":
        return "bg-slate-700 text-white border-slate-700 font-medium";
      case "admin":
        return "bg-[#5B8DBE] text-white border-[#5B8DBE]";
      default:
        return "bg-gray-100 text-gray-700 border-gray-300";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-10">
        <h1 className="text-2xl font-light text-[#2D3748] mb-1 tracking-tight">
          Organization <span className="font-normal">Settings</span>
        </h1>
        <p className="text-sm font-light text-[#6B7280]">
          Manage your organization members and invitations
        </p>
      </div>

      <div className="space-y-6">

      {/* Members Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Team Members</CardTitle>
              <CardDescription>
                {members.length} member{members.length !== 1 ? "s" : ""} in your organization
              </CardDescription>
            </div>
            <Button onClick={() => setShowInviteDialog(true)}>
              <UserPlus className="h-4 w-4 mr-2" />
              Invite Member
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Member</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.user_id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{member.full_name}</span>
                      <span className="text-sm text-muted-foreground">{member.email}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={getRoleBadgeColor(member.role)}>
                      <span className="mr-1">{getRoleIcon(member.role)}</span>
                      {member.role}
                    </Badge>
                  </TableCell>
                  <TableCell>{format(new Date(member.joined_at), "MMM d, yyyy")}</TableCell>
                  <TableCell>
                    <Badge variant={member.is_active ? "default" : "secondary"}>
                      {member.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {member.role.toLowerCase() !== "owner" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors group"
                        onClick={() => setMemberToRemove(member)}
                        title="Remove member"
                      >
                        <Trash2 className="h-4 w-4 group-hover:scale-110 transition-transform" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      {invitations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Invitations</CardTitle>
            <CardDescription>
              {invitations.length} pending invitation{invitations.length !== 1 ? "s" : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Email Status</TableHead>
                  <TableHead>Invited By</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invitations.map((invitation) => {
                  const cooldownRemaining = resendCooldowns[invitation.id] ?? 0;
                  const isResending = resendingId === invitation.id;
                  const isOnCooldown = cooldownRemaining > 0;

                  return (
                    <TableRow key={invitation.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          {invitation.email}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={getRoleBadgeColor(invitation.role)}>
                          {invitation.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {invitation.email_sent ? (
                          <div className="flex items-center gap-1.5 text-green-700">
                            <CheckCircle className="h-3.5 w-3.5" />
                            <span className="text-sm">Email sent</span>
                          </div>
                        ) : invitation.email_error ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="flex items-center gap-1.5 text-red-600 cursor-help">
                                <XCircle className="h-3.5 w-3.5" />
                                <span className="text-sm">Email failed</span>
                              </div>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs">
                              <p>{invitation.email_error}</p>
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <div className="flex items-center gap-1.5 text-slate-500">
                            <AlertCircle className="h-3.5 w-3.5" />
                            <span className="text-sm">Email not sent</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>{invitation.invited_by}</TableCell>
                      <TableCell>{format(new Date(invitation.expires_at), "MMM d, yyyy")}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-slate-600 hover:text-slate-900"
                                onClick={() => handleResendInvitation(invitation)}
                                disabled={isResending || isOnCooldown}
                                aria-label={`Resend invitation to ${invitation.email}`}
                              >
                                <RefreshCw
                                  className={cn(
                                    "h-4 w-4 mr-1",
                                    isResending && "animate-spin"
                                  )}
                                />
                                {isOnCooldown
                                  ? `${cooldownRemaining}s`
                                  : isResending
                                    ? "Sending..."
                                    : "Resend"}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                              {isOnCooldown
                                ? `Wait ${cooldownRemaining} seconds before resending`
                                : "Resend invitation email"}
                            </TooltipContent>
                          </Tooltip>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive hover:text-destructive"
                            onClick={() => handleRevokeInvitation(invitation.id)}
                          >
                            Revoke
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Invite Dialog */}
      <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>
              Send an invitation to join your organization. They&apos;ll receive an email with
              instructions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="colleague@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Members can upload and process leaflets. Admins can also manage team members.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowInviteDialog(false);
                setInviteEmail("");
                setInviteRole("member");
              }}
              disabled={processing}
            >
              Cancel
            </Button>
            <Button onClick={handleInvite} disabled={processing || !inviteEmail.trim()}>
              {processing ? "Sending..." : "Send Invitation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Member Confirmation */}
      <AlertDialog open={!!memberToRemove} onOpenChange={() => setMemberToRemove(null)}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader className="space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-red-100">
              <AlertTriangle className="h-6 w-6 text-red-600" strokeWidth={1.5} />
            </div>
            <AlertDialogTitle className="text-center text-xl font-light text-[#2D3748]">
              <span className="font-normal">Remove</span> Team Member?
            </AlertDialogTitle>
            <div className="text-center text-[#6B7280] font-light space-y-3">
              <p>
                You&apos;re about to remove <strong className="font-normal text-[#2D3748]">{memberToRemove?.full_name}</strong> from the organization.
              </p>
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
                <p className="text-red-900 font-normal">
                  This action cannot be undone. They will immediately lose access to all organization data.
                </p>
              </div>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter className="sm:space-x-2">
            <AlertDialogCancel
              disabled={processing}
              className="font-light hover:bg-gray-100"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveMember}
              disabled={processing}
              className="bg-red-600 text-white hover:bg-red-700 font-normal shadow-sm"
            >
              {processing ? "Removing..." : "Remove Member"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </div>
  );
}
