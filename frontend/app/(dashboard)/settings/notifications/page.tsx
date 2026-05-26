"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Bell, Mail, Save, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  getNotificationTypes,
  NotificationPreferences,
  NotificationType,
} from "@/lib/actions/notifications";

export default function NotificationSettingsPage() {
  const [, setPreferences] = useState<NotificationPreferences | null>(null);
  const [notificationTypes, setNotificationTypes] = useState<NotificationType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Local state for form
  const [enabledTypes, setEnabledTypes] = useState<string[]>([]);
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [emailDigestFrequency, setEmailDigestFrequency] = useState("daily");
  const [showSuccessNotifications, setShowSuccessNotifications] = useState(true);
  const [autoDismissSeconds, setAutoDismissSeconds] = useState<number | undefined>(undefined);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setIsLoading(true);
    try {
      const [prefsResult, typesResult] = await Promise.all([
        getNotificationPreferences(),
        getNotificationTypes(),
      ]);

      if (prefsResult.success && prefsResult.data) {
        setPreferences(prefsResult.data);
        setEnabledTypes(prefsResult.data.enabled_types || []);
        setEmailEnabled(prefsResult.data.email_enabled);
        setEmailDigestFrequency(prefsResult.data.email_digest_frequency || "daily");
        setShowSuccessNotifications(prefsResult.data.show_success_notifications);
        setAutoDismissSeconds(prefsResult.data.auto_dismiss_after_seconds);
      }

      if (typesResult.success && typesResult.data) {
        setNotificationTypes(typesResult.data);
      }
    } catch (error) {
      console.error("Error loading notification settings:", error);
      toast.error("Failed to load notification settings");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      const result = await updateNotificationPreferences({
        enabled_types: enabledTypes,
        email_enabled: emailEnabled,
        email_digest_frequency: emailDigestFrequency,
        show_success_notifications: showSuccessNotifications,
        auto_dismiss_after_seconds: autoDismissSeconds || 0,
      });

      if (result.success) {
        toast.success("Notification preferences saved");
        if (result.data) {
          setPreferences(result.data);
        }
      } else {
        toast.error(result.error || "Failed to save preferences");
      }
    } catch (error) {
      console.error("Error saving notification preferences:", error);
      toast.error("Failed to save preferences");
    } finally {
      setIsSaving(false);
    }
  }

  function handleTypeToggle(typeValue: string, checked: boolean) {
    if (checked) {
      setEnabledTypes((prev) => [...prev, typeValue]);
    } else {
      setEnabledTypes((prev) => prev.filter((t) => t !== typeValue));
    }
  }

  function handleSelectAll() {
    setEnabledTypes(notificationTypes.map((t) => t.value));
  }

  function handleDeselectAll() {
    setEnabledTypes([]);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Notification Settings</h1>
        <p className="text-muted-foreground">
          Manage how you receive notifications from the platform.
        </p>
      </div>

      {/* In-App Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            In-App Notifications
          </CardTitle>
          <CardDescription>
            Configure which notifications appear in your notification bell.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="show-success">Show Success Notifications</Label>
              <p className="text-sm text-muted-foreground">
                Display notifications for successful operations (e.g., extraction complete).
              </p>
            </div>
            <Switch
              id="show-success"
              checked={showSuccessNotifications}
              onCheckedChange={setShowSuccessNotifications}
            />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Notification Types</Label>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleSelectAll}>
                  Select All
                </Button>
                <Button variant="outline" size="sm" onClick={handleDeselectAll}>
                  Deselect All
                </Button>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Choose which types of notifications you want to receive.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {notificationTypes.map((type) => (
                <div
                  key={type.value}
                  className="flex items-start space-x-3 rounded-lg border p-3"
                >
                  <Checkbox
                    id={`type-${type.value}`}
                    checked={enabledTypes.includes(type.value)}
                    onCheckedChange={(checked) =>
                      handleTypeToggle(type.value, checked as boolean)
                    }
                  />
                  <div className="space-y-1 leading-none">
                    <Label
                      htmlFor={`type-${type.value}`}
                      className="text-sm font-medium cursor-pointer"
                    >
                      {type.name}
                    </Label>
                    <p className="text-xs text-muted-foreground">{type.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Email Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Notifications
          </CardTitle>
          <CardDescription>
            Configure email notification settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="email-enabled">Enable Email Notifications</Label>
              <p className="text-sm text-muted-foreground">
                Receive important notifications via email.
              </p>
            </div>
            <Switch
              id="email-enabled"
              checked={emailEnabled}
              onCheckedChange={setEmailEnabled}
            />
          </div>

          {emailEnabled && (
            <div className="space-y-2">
              <Label htmlFor="digest-frequency">Email Digest Frequency</Label>
              <p className="text-sm text-muted-foreground">
                How often do you want to receive email digests?
              </p>
              <Select
                value={emailDigestFrequency}
                onValueChange={setEmailDigestFrequency}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Select frequency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="immediate">Immediate</SelectItem>
                  <SelectItem value="daily">Daily Digest</SelectItem>
                  <SelectItem value="weekly">Weekly Digest</SelectItem>
                  <SelectItem value="never">Never</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-between items-center">
        <Button variant="outline" onClick={loadData} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Preferences
        </Button>
      </div>
    </div>
  );
}
