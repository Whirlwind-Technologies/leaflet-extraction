"use server";

import { revalidatePath } from "next/cache";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// Types
export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  message: string;
  severity: "info" | "success" | "warning" | "error" | "critical";
  is_read: boolean;
  is_dismissed?: boolean;
  user_id?: string;
  organization_id?: string;
  role_requirement?: string;
  action_url?: string;
  action_text?: string;
  expires_at?: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface NotificationPreferences {
  user_id: string;
  enabled_types: string[];
  email_enabled: boolean;
  email_digest_frequency: "immediate" | "daily" | "weekly" | "never";
  show_success_notifications: boolean;
  auto_dismiss_after_seconds?: number;
  created_at: string;
  updated_at: string;
}

export interface NotificationType {
  value: string;
  name: string;
  description: string;
}

// Helper to get auth token
async function getAuthToken(): Promise<string | null> {
  const { cookies } = await import("next/headers");
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value || null;
}

// Get notifications for current user
export async function getNotifications(params?: {
  page?: number;
  page_size?: number;
  is_read?: boolean;
}): Promise<{ success: boolean; data?: Notification[]; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    if (params?.is_read !== undefined) searchParams.set("is_read", String(params.is_read));

    const response = await fetch(
      `${BACKEND_URL}/api/v1/notifications?${searchParams.toString()}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to fetch notifications" };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching notifications:", error);
    return { success: false, error: "Failed to fetch notifications" };
  }
}

// Get unread notification count
export async function getUnreadCount(): Promise<{ success: boolean; data?: number; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/notifications/unread-count`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return { success: false, error: "Failed to fetch unread count" };
    }

    const data = await response.json();
    return { success: true, data: data.unread_count };
  } catch (error) {
    console.error("Error fetching unread count:", error);
    return { success: false, error: "Failed to fetch unread count" };
  }
}

// Mark notification as read
export async function markNotificationRead(
  notificationId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(
      `${BACKEND_URL}/api/v1/notifications/${notificationId}/read`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to mark notification as read" };
    }

    revalidatePath("/");
    return { success: true };
  } catch (error) {
    console.error("Error marking notification as read:", error);
    return { success: false, error: "Failed to mark notification as read" };
  }
}

// Mark all notifications as read
export async function markAllNotificationsRead(): Promise<{ success: boolean; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/notifications/mark-all-read`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to mark all as read" };
    }

    revalidatePath("/");
    return { success: true };
  } catch (error) {
    console.error("Error marking all notifications as read:", error);
    return { success: false, error: "Failed to mark all as read" };
  }
}

// Dismiss notification
export async function dismissNotification(
  notificationId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(
      `${BACKEND_URL}/api/v1/notifications/${notificationId}/dismiss`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to dismiss notification" };
    }

    revalidatePath("/");
    return { success: true };
  } catch (error) {
    console.error("Error dismissing notification:", error);
    return { success: false, error: "Failed to dismiss notification" };
  }
}

// Get notification preferences
export async function getNotificationPreferences(): Promise<{
  success: boolean;
  data?: NotificationPreferences;
  error?: string;
}> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/notifications/preferences`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to fetch preferences" };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    console.error("Error fetching notification preferences:", error);
    return { success: false, error: "Failed to fetch preferences" };
  }
}

// Update notification preferences
export async function updateNotificationPreferences(
  preferences: Partial<{
    enabled_types: string[];
    email_enabled: boolean;
    email_digest_frequency: string;
    show_success_notifications: boolean;
    auto_dismiss_after_seconds: number;
  }>
): Promise<{ success: boolean; data?: NotificationPreferences; error?: string }> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/notifications/preferences`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(preferences),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to update preferences" };
    }

    const data = await response.json();
    revalidatePath("/settings/notifications");
    return { success: true, data };
  } catch (error) {
    console.error("Error updating notification preferences:", error);
    return { success: false, error: "Failed to update preferences" };
  }
}

// Get available notification types
export async function getNotificationTypes(): Promise<{
  success: boolean;
  data?: NotificationType[];
  error?: string;
}> {
  try {
    const token = await getAuthToken();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/notifications/types`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      next: { revalidate: 3600 }, // Cache for 1 hour
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Failed to fetch notification types" };
    }

    const data = await response.json();
    return { success: true, data: data.types };
  } catch (error) {
    console.error("Error fetching notification types:", error);
    return { success: false, error: "Failed to fetch notification types" };
  }
}
