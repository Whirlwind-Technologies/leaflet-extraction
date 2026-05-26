"use client";

import { useRouter } from "next/navigation";
import { LogOut, Settings, User as UserIcon, Menu, Shield, Bell, AlertTriangle, CheckCircle, Info } from "lucide-react";
import { logout } from "@/lib/actions/auth";
import { switchOrganization } from "@/lib/actions/organizations";
import { getNotifications, markNotificationRead, markAllNotificationsRead } from "@/lib/actions/admin";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { MobileSidebar } from "./mobile-sidebar";
import { OrganizationSwitcher } from "./organization-switcher";
import { useSidebar } from "./dashboard-layout-client";
import type { User } from "@/lib/types";
import type { SystemNotification } from "@/lib/types/admin";
import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";

interface HeaderOrganization {
  id: string;
  name: string;
  role: string;
  status: string;
  member_count?: number;
}

interface HeaderProps {
  user: User;
  currentOrganization?: HeaderOrganization;
  organizations?: HeaderOrganization[];
}

export function Header({ user, currentOrganization, organizations }: HeaderProps) {
  const router = useRouter();
  const { isCollapsed, setIsCollapsed } = useSidebar();
  const [notifications, setNotifications] = useState<SystemNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsLoading, setNotificationsLoading] = useState(false);

  const initials =
    user.full_name
      ?.split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase() || user.email[0].toUpperCase();

  // Load notifications
  const loadNotifications = useCallback(async () => {
    if (!user.is_superuser) return; // Only load for admin users

    setNotificationsLoading(true);
    try {
      const result = await getNotifications();
      if (result.success && result.data) {
        setNotifications(result.data);
        setUnreadCount(result.data.filter(n => !n.is_read).length);
      }
    } catch (error) {
      console.error("Failed to load notifications:", error);
    } finally {
      setNotificationsLoading(false);
    }
  }, [user.is_superuser]);

  // Load notifications on mount and periodically refresh
  useEffect(() => {
    loadNotifications();

    // Refresh notifications every 30 seconds
    const interval = setInterval(loadNotifications, 30000);
    return () => clearInterval(interval);
  }, [loadNotifications]);

  const handleOrganizationSwitch = async (orgId: string) => {
    try {
      const result = await switchOrganization(orgId);

      if (result.success) {
        // Refresh the page to reload with new organization context
        router.refresh();
      } else {
        console.error("Failed to switch organization:", result.error);
      }
    } catch (error) {
      console.error("Failed to switch organization:", error);
    }
  };

  const handleNotificationClick = async (notification: SystemNotification) => {
    if (!notification.is_read) {
      try {
        const result = await markNotificationRead(notification.id);
        if (result.success) {
          // Update local state
          setNotifications(prev =>
            prev.map(n => n.id === notification.id ? { ...n, is_read: true } : n)
          );
          setUnreadCount(prev => Math.max(0, prev - 1));
        }
      } catch (error) {
        console.error("Failed to mark notification as read:", error);
      }
    }

    // Navigate to action URL if provided
    if (notification.action_url) {
      router.push(notification.action_url);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const result = await markAllNotificationsRead();
      if (result.success) {
        setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
        setUnreadCount(0);
        toast.success("All notifications marked as read");
      }
    } catch (error) {
      console.error("Failed to mark all notifications as read:", error);
      toast.error("Failed to mark notifications as read");
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "error":
      case "critical":
        return AlertTriangle;
      case "success":
        return CheckCircle;
      case "warning":
        return AlertTriangle;
      case "info":
      default:
        return Info;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "error":
      case "critical":
        return "text-red-600 bg-red-50";
      case "success":
        return "text-green-600 bg-green-50";
      case "warning":
        return "text-yellow-600 bg-yellow-50";
      case "info":
      default:
        return "text-blue-600 bg-blue-50";
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200 h-20">
      <div className="flex items-center h-full gap-4">
        <MobileSidebar user={user} />

        {/* Desktop Sidebar Toggle */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="hidden lg:flex items-center justify-center h-10 w-10 ml-3 rounded-md hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors flex-shrink-0"
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <Menu className="h-5 w-5" strokeWidth={1.5} />
        </button>

        {/* Organization Switcher */}
        <div className="hidden lg:block flex-1 max-w-md">
          <OrganizationSwitcher
            currentOrganization={currentOrganization}
            organizations={organizations}
            onSwitch={handleOrganizationSwitch}
          />
        </div>

        <div className="flex-1" />

        {/* Notification Bell - Only for admin users */}
        {user.is_superuser && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="relative mr-3 hover:bg-gray-100 transition-colors"
                disabled={notificationsLoading}
              >
                <Bell className="h-5 w-5 text-gray-600" strokeWidth={1.5} />
                {unreadCount > 0 && (
                  <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center bg-red-500 text-white text-xs border-2 border-white">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
              <DropdownMenuLabel className="flex justify-between items-center">
                <span>Notifications</span>
                {unreadCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-[#6B7280] hover:text-[#2D3748]"
                    onClick={handleMarkAllRead}
                    disabled={notificationsLoading}
                  >
                    Mark all read
                  </Button>
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <div className="max-h-80 overflow-y-auto">
                {notificationsLoading ? (
                  <div className="p-4 text-center">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="text-sm text-gray-500 mt-2">Loading notifications...</p>
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    No notifications
                  </div>
                ) : (
                  notifications.map((notification) => {
                    const SeverityIcon = getSeverityIcon(notification.severity);
                    const severityColor = getSeverityColor(notification.severity);

                    return (
                      <DropdownMenuItem key={notification.id} className="p-0">
                        <div
                          className={`flex items-start gap-3 p-3 w-full hover:bg-[#F9FAFB] cursor-pointer ${
                            !notification.is_read ? 'bg-blue-50/50' : ''
                          }`}
                          onClick={() => handleNotificationClick(notification)}
                        >
                          <div className={`p-1.5 rounded-lg flex-shrink-0 mt-0.5 ${severityColor}`}>
                            <SeverityIcon className="h-3.5 w-3.5" strokeWidth={1.5} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className={`text-sm font-medium text-[#2D3748] ${
                                !notification.is_read ? 'font-semibold' : ''
                              }`}>
                                {notification.title}
                              </p>
                              {!notification.is_read && (
                                <div className="h-2 w-2 bg-blue-600 rounded-full"></div>
                              )}
                            </div>
                            <p className="text-xs text-[#6B7280] mt-1 line-clamp-2">
                              {notification.message}
                            </p>
                            <p className="text-xs text-[#6B7280] mt-1">
                              {new Date(notification.created_at).toLocaleString()}
                            </p>
                          </div>
                        </div>
                      </DropdownMenuItem>
                    );
                  })
                )}
              </div>
              {notifications.length > 0 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="justify-center text-[#5B8DBE] hover:text-[#4A7BA7] cursor-pointer"
                    onClick={() => router.push("/admin/audit-logs")}
                  >
                    View all notifications
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-11 w-11 rounded-full hover:bg-gray-100 transition-colors mr-6">
              <Avatar className="h-11 w-11 ring-2 ring-gray-200">
                <AvatarFallback className="bg-[#5B8DBE] text-white font-semibold text-sm">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56" align="end">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-semibold text-gray-900">
                  {user.full_name}
                </p>
                <p className="text-xs text-gray-500">
                  {user.email}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => router.push("/profile")}
            >
              <UserIcon className="mr-2 h-4 w-4" strokeWidth={2} />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => router.push("/settings")}
            >
              <Settings className="mr-2 h-4 w-4" strokeWidth={2} />
              Settings
            </DropdownMenuItem>
            {user.is_superuser && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="cursor-pointer"
                  onClick={() => router.push("/admin")}
                >
                  <Shield className="mr-2 h-4 w-4" strokeWidth={2} />
                  Admin Panel
                </DropdownMenuItem>
              </>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-red-600 focus:text-red-600 cursor-pointer"
              onClick={() => logout()}
            >
              <LogOut className="mr-2 h-4 w-4" strokeWidth={2} />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}