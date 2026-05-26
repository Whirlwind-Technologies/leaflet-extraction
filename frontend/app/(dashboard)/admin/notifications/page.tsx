"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Bell,
  Plus,
  RefreshCw,
  Loader2,
  Trash2,
  Eye,
  Send,
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import {
  getAdminNotifications,
  getNotificationStats,
  createAdminNotification,
  deleteAdminNotification,
  markAllNotificationsRead,
  AdminNotification,
  NotificationStats,
} from "@/lib/actions/admin";

export default function NotificationCenterPage() {
  const [notifications, setNotifications] = useState<AdminNotification[]>([]);
  const [stats, setStats] = useState<NotificationStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Filters
  const [filterType, setFilterType] = useState<string>("all");
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [filterRead, setFilterRead] = useState<string>("all");

  // Create dialog
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newNotification, setNewNotification] = useState({
    notification_type: "system_alert",
    title: "",
    message: "",
    severity: "info",
    broadcast_to_all: true,
    role_requirement: "",
    action_url: "",
    expires_in_hours: 24,
  });

  // View dialog
  const [selectedNotification, setSelectedNotification] = useState<AdminNotification | null>(null);

  const loadNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        page_size: "20",
      };
      if (filterType !== "all") params.notification_type = filterType;
      if (filterSeverity !== "all") params.severity = filterSeverity;
      if (filterRead === "read") params.is_read = "true";
      if (filterRead === "unread") params.is_read = "false";

      const result = await getAdminNotifications(params);

      if (result.success && result.data) {
        setNotifications(result.data.items || []);
        setTotalPages(result.data.total_pages || 1);
      } else {
        throw new Error(result.error || "Failed to fetch notifications");
      }
    } catch (error) {
      console.error("Error loading notifications:", error);
      toast.error("Failed to load notifications");
    } finally {
      setIsLoading(false);
    }
  }, [page, filterType, filterSeverity, filterRead]);

  useEffect(() => {
    loadNotifications();
    loadStats();
  }, [loadNotifications]);

  async function loadStats() {
    try {
      const result = await getNotificationStats();

      if (result.success && result.data) {
        setStats(result.data);
      }
    } catch (error) {
      console.error("Error loading stats:", error);
    }
  }

  async function handleCreateNotification() {
    if (!newNotification.title || !newNotification.message) {
      toast.error("Title and message are required");
      return;
    }

    setIsCreating(true);
    try {
      const payload: Parameters<typeof createAdminNotification>[0] = {
        notification_type: newNotification.notification_type,
        title: newNotification.title,
        message: newNotification.message,
        severity: newNotification.severity,
        broadcast_to_all: newNotification.broadcast_to_all,
        expires_in_hours: newNotification.expires_in_hours,
      };

      if (!newNotification.broadcast_to_all && newNotification.role_requirement) {
        payload.role_requirement = newNotification.role_requirement;
        payload.broadcast_to_all = false;
      }

      if (newNotification.action_url) {
        payload.action_url = newNotification.action_url;
      }

      const result = await createAdminNotification(payload);

      if (result.success) {
        toast.success("Notification created and broadcast");
        setIsCreateDialogOpen(false);
        setNewNotification({
          notification_type: "system_alert",
          title: "",
          message: "",
          severity: "info",
          broadcast_to_all: true,
          role_requirement: "",
          action_url: "",
          expires_in_hours: 24,
        });
        loadNotifications();
        loadStats();
      } else {
        throw new Error(result.error || "Failed to create notification");
      }
    } catch (error: unknown) {
      console.error("Error creating notification:", error);
      toast.error(error instanceof Error ? error.message : "Failed to create notification");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeleteNotification(id: string) {
    try {
      const result = await deleteAdminNotification(id);

      if (result.success) {
        toast.success("Notification deleted");
        loadNotifications();
        loadStats();
      } else {
        throw new Error(result.error || "Failed to delete notification");
      }
    } catch (error) {
      console.error("Error deleting notification:", error);
      toast.error("Failed to delete notification");
    }
  }

  async function handleMarkAllRead() {
    try {
      const result = await markAllNotificationsRead();

      if (result.success) {
        toast.success("All notifications marked as read");
        loadNotifications();
        loadStats();
      } else {
        throw new Error(result.error || "Failed to mark all as read");
      }
    } catch (error) {
      console.error("Error marking all as read:", error);
      toast.error("Failed to mark all as read");
    }
  }

  function getSeverityIcon(severity: string) {
    switch (severity) {
      case "critical":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notification Center</h1>
          <p className="text-muted-foreground">
            Manage and broadcast system notifications.
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Notification
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Unread</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.unread}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Read</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.read}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Types</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{Object.keys(stats.by_type).length}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="w-[180px]">
              <Label className="mb-2 block">Type</Label>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger>
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="budget_warning">Budget Warning</SelectItem>
                  <SelectItem value="provider_failover">Provider Failover</SelectItem>
                  <SelectItem value="system_alert">System Alert</SelectItem>
                  <SelectItem value="maintenance">Maintenance</SelectItem>
                  <SelectItem value="security_alert">Security Alert</SelectItem>
                  <SelectItem value="feature_update">Feature Update</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-[180px]">
              <Label className="mb-2 block">Severity</Label>
              <Select value={filterSeverity} onValueChange={setFilterSeverity}>
                <SelectTrigger>
                  <SelectValue placeholder="All severities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severities</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="success">Success</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-[180px]">
              <Label className="mb-2 block">Status</Label>
              <Select value={filterRead} onValueChange={setFilterRead}>
                <SelectTrigger>
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="unread">Unread</SelectItem>
                  <SelectItem value="read">Read</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => loadNotifications()}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button variant="outline" onClick={handleMarkAllRead}>
                Mark All Read
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notifications Table */}
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>
            {notifications.length} notifications found
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No notifications found
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">Status</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notifications.map((notification) => (
                  <TableRow
                    key={notification.id}
                    className={notification.is_read ? "opacity-60" : ""}
                  >
                    <TableCell>
                      {notification.is_read ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <Bell className="h-4 w-4 text-yellow-500" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium max-w-[300px] truncate">
                      {notification.title}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {notification.notification_type.replace(/_/g, " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {getSeverityIcon(notification.severity)}
                        <span className="capitalize">{notification.severity}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {notification.user_id
                        ? "User"
                        : notification.organization_id
                        ? "Organization"
                        : notification.role_requirement
                        ? notification.role_requirement
                        : "Global"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDistanceToNow(new Date(notification.created_at), {
                        addSuffix: true,
                      })}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedNotification(notification)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteNotification(notification.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              <Button
                variant="outline"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="py-2 px-4">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                disabled={page === totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Create Notification</DialogTitle>
            <DialogDescription>
              Broadcast a new notification to users.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="type">Notification Type</Label>
              <Select
                value={newNotification.notification_type}
                onValueChange={(value) =>
                  setNewNotification({ ...newNotification, notification_type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="system_alert">System Alert</SelectItem>
                  <SelectItem value="maintenance">Maintenance</SelectItem>
                  <SelectItem value="feature_update">Feature Update</SelectItem>
                  <SelectItem value="security_alert">Security Alert</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={newNotification.title}
                onChange={(e) =>
                  setNewNotification({ ...newNotification, title: e.target.value })
                }
                placeholder="Notification title"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="message">Message</Label>
              <Textarea
                id="message"
                value={newNotification.message}
                onChange={(e) =>
                  setNewNotification({ ...newNotification, message: e.target.value })
                }
                placeholder="Notification message"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="severity">Severity</Label>
                <Select
                  value={newNotification.severity}
                  onValueChange={(value) =>
                    setNewNotification({ ...newNotification, severity: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="info">Info</SelectItem>
                    <SelectItem value="success">Success</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="expires">Expires In (hours)</Label>
                <Input
                  id="expires"
                  type="number"
                  min={1}
                  max={720}
                  value={newNotification.expires_in_hours}
                  onChange={(e) =>
                    setNewNotification({
                      ...newNotification,
                      expires_in_hours: parseInt(e.target.value) || 24,
                    })
                  }
                />
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="broadcast"
                checked={newNotification.broadcast_to_all}
                onCheckedChange={(checked) =>
                  setNewNotification({
                    ...newNotification,
                    broadcast_to_all: checked as boolean,
                  })
                }
              />
              <Label htmlFor="broadcast">Broadcast to all users</Label>
            </div>
            {!newNotification.broadcast_to_all && (
              <div className="grid gap-2">
                <Label htmlFor="target">Target Role</Label>
                <Select
                  value={newNotification.role_requirement}
                  onValueChange={(value) =>
                    setNewNotification({ ...newNotification, role_requirement: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="super_admin">Super Admins</SelectItem>
                    <SelectItem value="admin">Admins</SelectItem>
                    <SelectItem value="member">Members</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="action_url">Action URL (optional)</Label>
              <Input
                id="action_url"
                value={newNotification.action_url}
                onChange={(e) =>
                  setNewNotification({ ...newNotification, action_url: e.target.value })
                }
                placeholder="/admin/dashboard"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateNotification} disabled={isCreating}>
              {isCreating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Send Notification
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Dialog */}
      <Dialog
        open={!!selectedNotification}
        onOpenChange={() => setSelectedNotification(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedNotification && getSeverityIcon(selectedNotification.severity)}
              {selectedNotification?.title}
            </DialogTitle>
          </DialogHeader>
          {selectedNotification && (
            <div className="space-y-4">
              <p className="text-muted-foreground">{selectedNotification.message}</p>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Type:</span>{" "}
                  {selectedNotification.notification_type.replace(/_/g, " ")}
                </div>
                <div>
                  <span className="text-muted-foreground">Severity:</span>{" "}
                  {selectedNotification.severity}
                </div>
                <div>
                  <span className="text-muted-foreground">Status:</span>{" "}
                  {selectedNotification.is_read ? "Read" : "Unread"}
                </div>
                <div>
                  <span className="text-muted-foreground">Created:</span>{" "}
                  {new Date(selectedNotification.created_at).toLocaleString()}
                </div>
                {selectedNotification.expires_at && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Expires:</span>{" "}
                    {new Date(selectedNotification.expires_at).toLocaleString()}
                  </div>
                )}
                {selectedNotification.action_url && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Action URL:</span>{" "}
                    <a
                      href={selectedNotification.action_url}
                      className="text-blue-500 hover:underline"
                    >
                      {selectedNotification.action_url}
                    </a>
                  </div>
                )}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedNotification(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
