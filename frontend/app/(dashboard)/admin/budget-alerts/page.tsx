"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import {
  Bell,
  ArrowLeft,
  Plus,
  Edit,
  Trash2,
  Search,
  Filter,
  AlertTriangle,
  DollarSign,
  Mail,
  Power,
  PowerOff,
  ExternalLink,
  Calendar,
  Users,
  Zap,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import {
  getBudgetAlerts,
  createBudgetAlert,
  updateBudgetAlert,
  deleteBudgetAlert,
  getPlatformProviders,
  getOrganizations
} from "@/lib/actions/admin";
import { brandColors as colors } from "@/lib/brand-colors";

interface BudgetAlert {
  id: string;
  platform_provider_id: string;
  organization_id?: string;
  // Names for display
  provider_name?: string;
  organization_name?: string;
  // Alert config
  alert_type: "warning" | "critical" | "exhausted" | "rate_limit";
  threshold_percentage: number;
  period: "daily" | "monthly" | "hourly";
  is_active: boolean;
  // Notification settings
  notify_super_admins: boolean;
  notify_org_admins: boolean;
  email_recipients: string[];
  webhook_url?: string;
  slack_webhook_url?: string;
  // Rate limiting
  cooldown_minutes: number;
  max_triggers_per_day: number;
  custom_message?: string;
  // Status
  last_triggered_at?: string;
  trigger_count: number;
  can_trigger: boolean;
  // Timestamps
  created_at: string;
  updated_at: string;
  // Metadata
  alert_metadata?: Record<string, unknown>;
}

interface PlatformProvider {
  id: string;
  name: string;
  provider_type: string;
  is_active: boolean;
}

interface Organization {
  id: string;
  name: string;
  slug: string;
}

export default function BudgetAlertsPage() {
  const [alerts, setAlerts] = useState<BudgetAlert[]>([]);
  const [providers, setProviders] = useState<PlatformProvider[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterPeriod, setFilterPeriod] = useState<string>("all");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<BudgetAlert | null>(null);
  const [alertToDelete, setAlertToDelete] = useState<BudgetAlert | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState<{
    platform_provider_id: string;
    organization_id: string;
    alert_type: "warning" | "critical" | "exhausted" | "rate_limit";
    threshold_percentage: number;
    period: "daily" | "monthly" | "hourly";
    is_active: boolean;
    notify_super_admins: boolean;
    notify_org_admins: boolean;
    email_recipients: string;
    webhook_url: string;
    slack_webhook_url: string;
    cooldown_minutes: number;
    max_triggers_per_day: number;
    custom_message: string;
  }>({
    platform_provider_id: "",
    organization_id: "",
    alert_type: "warning",
    threshold_percentage: 80,
    period: "monthly",
    is_active: true,
    notify_super_admins: true,
    notify_org_admins: false,
    email_recipients: "",
    webhook_url: "",
    slack_webhook_url: "",
    cooldown_minutes: 60,
    max_triggers_per_day: 10,
    custom_message: "",
  });

  useEffect(() => {
    fetchAlerts();
    fetchProviders();
    fetchOrganizations();
  }, []);

  const fetchAlerts = async () => {
    try {
      const result = await getBudgetAlerts();

      if (result.success && result.data) {
        setAlerts((result.data.items || []) as unknown as BudgetAlert[]);
      } else {
        throw new Error(result.error || "Failed to fetch budget alerts");
      }
    } catch (error) {
      console.error("Error fetching alerts:", error);
      toast.error("Failed to load budget alerts");
    } finally {
      setLoading(false);
    }
  };

  const fetchProviders = async () => {
    try {
      const result = await getPlatformProviders({});

      if (result.success && result.data) {
        // getPlatformProviders returns an array directly
        setProviders(result.data);
      }
    } catch (error) {
      console.error("Error fetching providers:", error);
    }
  };

  const fetchOrganizations = async () => {
    try {
      const result = await getOrganizations({});

      if (result.success && result.data) {
        // Handle both paginated response and direct array response
        const organizations = Array.isArray(result.data) ? result.data : (result.data.items || []);
        setOrganizations(organizations);
      }
    } catch (error) {
      console.error("Error fetching organizations:", error);
    }
  };

  const handleCreateAlert = async () => {
    try {
      if (!formData.platform_provider_id) {
        toast.error("Please select a platform provider");
        return;
      }

      const emailList = formData.email_recipients
        .split(",")
        .map(email => email.trim())
        .filter(email => email);

      // Transform frontend form data to match backend BudgetAlertCreate schema
      const payload = {
        platform_provider_id: formData.platform_provider_id,
        organization_id: formData.organization_id || undefined,
        alert_type: formData.alert_type,
        threshold_percentage: formData.threshold_percentage,
        period: formData.period,
        is_active: formData.is_active,
        // Notification settings
        notify_super_admins: formData.notify_super_admins,
        notify_org_admins: formData.notify_org_admins,
        email_recipients: emailList,
        webhook_url: formData.webhook_url || undefined,
        slack_webhook_url: formData.slack_webhook_url || undefined,
        // Rate limiting
        cooldown_minutes: formData.cooldown_minutes,
        max_triggers_per_day: formData.max_triggers_per_day,
        custom_message: formData.custom_message || undefined,
      };

      const result = await createBudgetAlert(payload);

      if (result.success) {
        toast.success("Budget alert created successfully");
        setIsCreateDialogOpen(false);
        resetForm();
        fetchAlerts();
      } else {
        throw new Error(result.error || "Failed to create budget alert");
      }
    } catch (error) {
      console.error("Error creating alert:", error);
      toast.error(error instanceof Error ? error.message : "Failed to create budget alert");
    }
  };

  const handleUpdateAlert = async () => {
    if (!selectedAlert) return;

    try {
      const emailList = formData.email_recipients
        .split(",")
        .map(email => email.trim())
        .filter(email => email);

      // Transform frontend form data to match backend BudgetAlertUpdate schema
      const payload = {
        alert_type: formData.alert_type,
        threshold_percentage: formData.threshold_percentage,
        period: formData.period,
        is_active: formData.is_active,
        // Notification settings
        notify_super_admins: formData.notify_super_admins,
        notify_org_admins: formData.notify_org_admins,
        email_recipients: emailList,
        webhook_url: formData.webhook_url || undefined,
        slack_webhook_url: formData.slack_webhook_url || undefined,
        // Rate limiting
        cooldown_minutes: formData.cooldown_minutes,
        max_triggers_per_day: formData.max_triggers_per_day,
        custom_message: formData.custom_message || undefined,
      };

      const result = await updateBudgetAlert(selectedAlert.id, payload);

      if (result.success) {
        toast.success("Budget alert updated successfully");
        setIsEditDialogOpen(false);
        setSelectedAlert(null);
        resetForm();
        fetchAlerts();
      } else {
        throw new Error(result.error || "Failed to update budget alert");
      }
    } catch (error) {
      console.error("Error updating alert:", error);
      toast.error(error instanceof Error ? error.message : "Failed to update budget alert");
    }
  };

  const openDeleteDialog = (alert: BudgetAlert) => {
    setAlertToDelete(alert);
    setIsDeleteDialogOpen(true);
  };

  const handleDeleteAlert = async () => {
    if (!alertToDelete) return;

    setIsDeleting(true);
    try {
      const result = await deleteBudgetAlert(alertToDelete.id);

      if (result.success) {
        toast.success("Budget alert deleted successfully");
        setIsDeleteDialogOpen(false);
        setAlertToDelete(null);
        fetchAlerts();
      } else {
        throw new Error(result.error || "Failed to delete budget alert");
      }
    } catch (error) {
      console.error("Error deleting alert:", error);
      toast.error("Failed to delete budget alert");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggleAlert = async (alertId: string, isActive: boolean) => {
    try {
      const result = await updateBudgetAlert(alertId, { is_active: !isActive });
      if (result.success) {
        toast.success(`Budget alert ${!isActive ? "enabled" : "disabled"}`);
        fetchAlerts();
      } else {
        throw new Error(result.error || "Failed to toggle budget alert");
      }
    } catch (error) {
      console.error("Error toggling alert:", error);
      toast.error(error instanceof Error ? error.message : "Failed to toggle budget alert");
    }
  };

  const resetForm = () => {
    setFormData({
      platform_provider_id: "",
      organization_id: "",
      alert_type: "warning",
      threshold_percentage: 80,
      period: "monthly",
      is_active: true,
      notify_super_admins: true,
      notify_org_admins: false,
      email_recipients: "",
      webhook_url: "",
      slack_webhook_url: "",
      cooldown_minutes: 60,
      max_triggers_per_day: 10,
      custom_message: "",
    });
  };

  const openEditDialog = (alert: BudgetAlert) => {
    setSelectedAlert(alert);
    setFormData({
      platform_provider_id: alert.platform_provider_id,
      organization_id: alert.organization_id || "",
      alert_type: alert.alert_type as "warning" | "critical" | "exhausted" | "rate_limit",
      threshold_percentage: alert.threshold_percentage,
      period: alert.period as "daily" | "monthly" | "hourly",
      is_active: alert.is_active,
      notify_super_admins: alert.notify_super_admins,
      notify_org_admins: alert.notify_org_admins,
      email_recipients: (alert.email_recipients || []).join(", "),
      webhook_url: alert.webhook_url || "",
      slack_webhook_url: alert.slack_webhook_url || "",
      cooldown_minutes: alert.cooldown_minutes,
      max_triggers_per_day: alert.max_triggers_per_day,
      custom_message: alert.custom_message || "",
    });
    setIsEditDialogOpen(true);
  };

  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch = alert.platform_provider_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         (alert.organization_id && alert.organization_id.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesType = filterType === "all" || alert.alert_type === filterType;
    const matchesPeriod = filterPeriod === "all" || alert.period === filterPeriod;

    return matchesSearch && matchesType && matchesPeriod;
  });

  const getAlertTypeIcon = (type: string) => {
    switch (type) {
      case "warning": return <AlertTriangle className="h-4 w-4" style={{ color: colors.warning }} />;
      case "critical": return <AlertTriangle className="h-4 w-4" style={{ color: colors.error }} />;
      case "exhausted": return <DollarSign className="h-4 w-4" style={{ color: colors.error }} />;
      case "rate_limit": return <Zap className="h-4 w-4" style={{ color: colors.warning }} />;
      default: return <Bell className="h-4 w-4" style={{ color: colors.secondaryText }} />;
    }
  };

  const getAlertTypeBadgeStyle = (type: string) => {
    switch (type) {
      case "warning":
        return { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder };
      case "critical":
        return { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder };
      case "exhausted":
        return { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder };
      case "rate_limit":
        return { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder };
      default:
        return { backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray };
    }
  };

  const getPeriodIcon = (period: string) => {
    switch (period) {
      case "hourly": return <Zap className="h-4 w-4" style={{ color: colors.info }} />;
      case "daily": return <Calendar className="h-4 w-4" style={{ color: colors.success }} />;
      case "monthly": return <TrendingUp className="h-4 w-4" style={{ color: colors.primaryBrandBlue }} />;
      default: return <Calendar className="h-4 w-4" style={{ color: colors.secondaryText }} />;
    }
  };

  const getProviderName = (providerId: string, providerName?: string) => {
    if (providerName) return providerName;
    const provider = providers.find(p => p.id === providerId);
    return provider?.name || "Unknown Provider";
  };

  const getOrganizationName = (orgId: string | undefined, orgName?: string | null) => {
    if (!orgId) return "All Organizations";
    if (orgName) return orgName;
    const org = organizations.find(o => o.id === orgId);
    return org?.name || "Unknown Organization";
  };

  const renderDialogContent = (isEdit: boolean) => (
    <div className="grid gap-4 py-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="w-full">
          <Label htmlFor="platform_provider_id" style={{ color: colors.primaryText }}>Platform Provider *</Label>
          <Select
            value={formData.platform_provider_id || undefined}
            onValueChange={(value) =>
              setFormData({ ...formData, platform_provider_id: value })
            }
          >
            <SelectTrigger className="w-full" style={{ borderColor: colors.borderGray }}>
              <SelectValue placeholder="Select provider..." />
            </SelectTrigger>
            <SelectContent>
              {providers.map((provider) => (
                <SelectItem key={provider.id} value={provider.id}>
                  {provider.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full">
          <Label htmlFor="organization_id" style={{ color: colors.primaryText }}>Organization</Label>
          <Select
            value={formData.organization_id || "all"}
            onValueChange={(value) =>
              setFormData({ ...formData, organization_id: value === "all" ? "" : value })
            }
          >
            <SelectTrigger className="w-full" style={{ borderColor: colors.borderGray }}>
              <SelectValue placeholder="All organizations" />
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
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="w-full">
          <Label htmlFor="alert_type" style={{ color: colors.primaryText }}>Alert Type *</Label>
          <Select value={formData.alert_type} onValueChange={(value: string) =>
            setFormData({ ...formData, alert_type: value as BudgetAlert["alert_type"] })
          }>
            <SelectTrigger className="w-full" style={{ borderColor: colors.borderGray }}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="exhausted">Exhausted</SelectItem>
              <SelectItem value="rate_limit">Rate Limit</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="w-full">
          <Label htmlFor="threshold_percentage" style={{ color: colors.primaryText }}>Threshold %</Label>
          <Input
            type="number"
            min="1"
            max="100"
            value={formData.threshold_percentage}
            onChange={(e) => setFormData({ ...formData, threshold_percentage: parseInt(e.target.value) || 0 })}
            className="w-full"
            style={{ borderColor: colors.borderGray }}
          />
        </div>

        <div className="w-full">
          <Label htmlFor="period" style={{ color: colors.primaryText }}>Period *</Label>
          <Select value={formData.period} onValueChange={(value: string) =>
            setFormData({ ...formData, period: value as BudgetAlert["period"] })
          }>
            <SelectTrigger className="w-full" style={{ borderColor: colors.borderGray }}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hourly">Hourly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Separator style={{ backgroundColor: colors.borderGray }} />

      <div className="space-y-4">
        <h4 className="font-medium text-sm" style={{ color: colors.primaryText }}>Notification Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center space-x-2">
            <Switch
              id={`notify_super_admins_${isEdit ? 'edit' : 'create'}`}
              checked={formData.notify_super_admins}
              onCheckedChange={(checked) => setFormData({ ...formData, notify_super_admins: checked })}
            />
            <Label htmlFor={`notify_super_admins_${isEdit ? 'edit' : 'create'}`} style={{ color: colors.primaryText }}>Notify Super Admins</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id={`notify_org_admins_${isEdit ? 'edit' : 'create'}`}
              checked={formData.notify_org_admins}
              onCheckedChange={(checked) => setFormData({ ...formData, notify_org_admins: checked })}
            />
            <Label htmlFor={`notify_org_admins_${isEdit ? 'edit' : 'create'}`} style={{ color: colors.primaryText }}>Notify Org Admins</Label>
          </div>
        </div>

        <div>
          <Label htmlFor="email_recipients" style={{ color: colors.primaryText }}>Additional Email Recipients</Label>
          <Input
            placeholder="email1@example.com, email2@example.com"
            value={formData.email_recipients}
            onChange={(e) => setFormData({ ...formData, email_recipients: e.target.value })}
            style={{ borderColor: colors.borderGray }}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="webhook_url" style={{ color: colors.primaryText }}>Webhook URL</Label>
            <Input
              placeholder="https://yourapp.example.com/webhooks"
              value={formData.webhook_url}
              onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
              style={{ borderColor: colors.borderGray }}
            />
          </div>

          <div>
            <Label htmlFor="slack_webhook_url" style={{ color: colors.primaryText }}>Slack Webhook URL</Label>
            <Input
              placeholder="https://hooks.slack.com/..."
              value={formData.slack_webhook_url}
              onChange={(e) => setFormData({ ...formData, slack_webhook_url: e.target.value })}
              style={{ borderColor: colors.borderGray }}
            />
          </div>
        </div>
      </div>

      <Separator style={{ backgroundColor: colors.borderGray }} />

      <div className="space-y-4">
        <h4 className="font-medium text-sm" style={{ color: colors.primaryText }}>Rate Limiting</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="cooldown_minutes" style={{ color: colors.primaryText }}>Cooldown (minutes)</Label>
            <Input
              type="number"
              min="1"
              value={formData.cooldown_minutes}
              onChange={(e) => setFormData({ ...formData, cooldown_minutes: parseInt(e.target.value) || 0 })}
              style={{ borderColor: colors.borderGray }}
            />
          </div>

          <div>
            <Label htmlFor="max_triggers_per_day" style={{ color: colors.primaryText }}>Max Triggers/Day</Label>
            <Input
              type="number"
              min="1"
              value={formData.max_triggers_per_day}
              onChange={(e) => setFormData({ ...formData, max_triggers_per_day: parseInt(e.target.value) || 0 })}
              style={{ borderColor: colors.borderGray }}
            />
          </div>
        </div>

        <div>
          <Label htmlFor="custom_message" style={{ color: colors.primaryText }}>Custom Message Template</Label>
          <Textarea
            placeholder="Budget alert: {provider} has reached {percentage}% of {period} budget"
            value={formData.custom_message}
            onChange={(e) => setFormData({ ...formData, custom_message: e.target.value })}
            rows={3}
            style={{ borderColor: colors.borderGray }}
          />
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="container mx-auto pb-6 max-w-7xl">
        <div className="mb-8">
          <Link href="/admin">
            <Button variant="outline" className="mb-4" style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Admin Dashboard
            </Button>
          </Link>
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
                Budget <span className="font-normal">Alerts</span>
              </h1>
              <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
                Configure budget alerts and spending notifications for VLM usage
              </p>
            </div>
          </div>
        </div>
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto" style={{ borderColor: colors.primaryBrandBlue }}></div>
            <p className="mt-4" style={{ color: colors.secondaryText }}>Loading budget alerts...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-8">
        <Link href="/admin">
          <Button variant="outline" className="mb-4" style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Admin Dashboard
          </Button>
        </Link>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
              Budget <span className="font-normal">Alerts</span>
            </h1>
            <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
              Configure budget alerts and spending notifications for VLM usage
            </p>
          </div>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                <Plus className="h-4 w-4 mr-2" />
                Create Alert
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px]">
              <DialogHeader>
                <DialogTitle style={{ color: colors.primaryText }}>Create Budget Alert</DialogTitle>
                <DialogDescription style={{ color: colors.secondaryText }}>
                  Configure budget monitoring and notification settings.
                </DialogDescription>
              </DialogHeader>
              {renderDialogContent(false)}
              <DialogFooter>
                <Button variant="outline" onClick={() => {
                  setIsCreateDialogOpen(false);
                  resetForm();
                }} style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
                  Cancel
                </Button>
                <Button onClick={handleCreateAlert} style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                  Create Alert
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Alerts</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{alerts.length}</p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                <Bell className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Active Alerts</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {alerts.filter(a => a.is_active).length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.successBg }}>
                <Power className="h-6 w-6" style={{ color: colors.success }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Critical Alerts</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {alerts.filter(a => a.alert_type === "critical" && a.is_active).length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.errorBg }}>
                <AlertTriangle className="h-6 w-6" style={{ color: colors.error }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Recent Triggers</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {alerts.filter(a => a.last_triggered_at &&
                    new Date(a.last_triggered_at) > new Date(Date.now() - 24 * 60 * 60 * 1000)
                  ).length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.warningBg }}>
                <TrendingUp className="h-6 w-6" style={{ color: colors.warning }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white mb-6" style={{ borderColor: colors.borderGray }}>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4" style={{ color: colors.secondaryText }} />
              <Input
                placeholder="Search alerts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <div className="flex gap-4">
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-[140px]" style={{ borderColor: colors.borderGray }}>
                  <Filter className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                  <SelectValue placeholder="Alert Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="exhausted">Exhausted</SelectItem>
                  <SelectItem value="rate_limit">Rate Limit</SelectItem>
                </SelectContent>
              </Select>

              <Select value={filterPeriod} onValueChange={setFilterPeriod}>
                <SelectTrigger className="w-[130px]" style={{ borderColor: colors.borderGray }}>
                  <Calendar className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                  <SelectValue placeholder="Period" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Periods</SelectItem>
                  <SelectItem value="hourly">Hourly</SelectItem>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Table */}
      <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
            <Bell className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
            Budget Alerts ({filteredAlerts.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredAlerts.length === 0 ? (
            <div className="text-center p-12">
              <div className="p-6 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center" style={{ backgroundColor: colors.offWhiteBg }}>
                <Bell className="h-12 w-12" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
              </div>
              <h3 className="text-xl font-light mb-4" style={{ color: colors.primaryText }}>No Budget Alerts</h3>
              <p className="max-w-md mx-auto mb-8" style={{ color: colors.secondaryText }}>
                Create budget alerts to monitor VLM spending and receive notifications when thresholds are reached.
              </p>
              <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
                <DialogTrigger asChild>
                  <Button style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                    <Plus className="h-4 w-4 mr-2" />
                    Create Your First Alert
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[600px]">
                  <DialogHeader>
                    <DialogTitle style={{ color: colors.primaryText }}>Create Budget Alert</DialogTitle>
                    <DialogDescription style={{ color: colors.secondaryText }}>
                      Configure budget monitoring and notification settings.
                    </DialogDescription>
                  </DialogHeader>
                  {renderDialogContent(false)}
                  <DialogFooter>
                    <Button variant="outline" onClick={() => {
                      setIsCreateDialogOpen(false);
                      resetForm();
                    }} style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateAlert} style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                      Create Alert
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow style={{ borderColor: colors.borderGray }}>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Provider & Scope</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Alert Type</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Threshold & Period</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Status & Triggers</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Notifications</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Last Triggered</TableHead>
                  <TableHead className="font-light text-right" style={{ color: colors.secondaryText }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAlerts.map((alert) => (
                  <TableRow key={alert.id} className="transition-colors" style={{ borderColor: colors.borderGray }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                    <TableCell>
                      <div>
                        <div className="font-medium" style={{ color: colors.primaryText }}>
                          {getProviderName(alert.platform_provider_id, alert.provider_name)}
                        </div>
                        <div className="text-sm flex items-center gap-1" style={{ color: colors.secondaryText }}>
                          <Users className="h-3 w-3" />
                          {getOrganizationName(alert.organization_id, alert.organization_name)}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                        style={getAlertTypeBadgeStyle(alert.alert_type)}
                      >
                        {getAlertTypeIcon(alert.alert_type)}
                        {alert.alert_type.charAt(0).toUpperCase() + alert.alert_type.slice(1).replace("_", " ")}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium" style={{ color: colors.primaryText }}>{alert.threshold_percentage}%</div>
                        <div className="text-sm flex items-center gap-1" style={{ color: colors.secondaryText }}>
                          {getPeriodIcon(alert.period)}
                          {alert.period.charAt(0).toUpperCase() + alert.period.slice(1)}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          {alert.is_active ? (
                            <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }}>
                              <Power className="h-3 w-3 mr-1" />
                              Active
                            </div>
                          ) : (
                            <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border" style={{ backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray }}>
                              <PowerOff className="h-3 w-3 mr-1" />
                              Disabled
                            </div>
                          )}
                          {!alert.can_trigger && alert.is_active && (
                            <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ color: colors.warning, borderColor: colors.warningBorder }}>
                              Cooldown
                            </div>
                          )}
                        </div>
                        <div className="text-sm" style={{ color: colors.secondaryText }}>
                          {alert.trigger_count} triggers
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex flex-wrap gap-1">
                          {alert.notify_super_admins && (
                            <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>Admins</div>
                          )}
                          {alert.notify_org_admins && (
                            <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>Org Admins</div>
                          )}
                          {alert.email_recipients.length > 0 && (
                            <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>
                              <Mail className="h-2 w-2 mr-1" />
                              {alert.email_recipients.length}
                            </div>
                          )}
                          {alert.webhook_url && (
                            <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>
                              <ExternalLink className="h-2 w-2 mr-1" />
                              Webhook
                            </div>
                          )}
                        </div>
                        <div className="text-xs" style={{ color: colors.secondaryText }}>
                          Cooldown: {alert.cooldown_minutes}m
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {alert.last_triggered_at ? (
                        <div className="text-sm" style={{ color: colors.secondaryText }}>
                          {new Date(alert.last_triggered_at).toLocaleDateString()}
                          <br />
                          <span className="text-xs">
                            {new Date(alert.last_triggered_at).toLocaleTimeString()}
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm" style={{ color: colors.secondaryText }}>Never</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleToggleAlert(alert.id, alert.is_active)}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          {alert.is_active ? (
                            <PowerOff className="h-4 w-4" style={{ color: colors.secondaryText }} />
                          ) : (
                            <Power className="h-4 w-4" style={{ color: colors.success }} />
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(alert)}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          <Edit className="h-4 w-4" style={{ color: colors.info }} />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDeleteDialog(alert)}
                          className="h-8 w-8 p-0 hover:bg-red-50"
                          style={{ borderColor: colors.borderGray }}
                        >
                          <Trash2 className="h-4 w-4" style={{ color: colors.error }} />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle style={{ color: colors.primaryText }}>Edit Budget Alert</DialogTitle>
            <DialogDescription style={{ color: colors.secondaryText }}>
              Configure budget monitoring and notification settings.
            </DialogDescription>
          </DialogHeader>
          {renderDialogContent(true)}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setIsEditDialogOpen(false);
              setSelectedAlert(null);
              resetForm();
            }} style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
              Cancel
            </Button>
            <Button onClick={handleUpdateAlert} style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
              Update Alert
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={(open) => {
        if (!isDeleting) {
          setIsDeleteDialogOpen(open);
          if (!open) setAlertToDelete(null);
        }
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ color: colors.primaryText }}>
              <AlertTriangle className="h-5 w-5" style={{ color: colors.error }} />
              Delete Budget Alert
            </DialogTitle>
            <DialogDescription style={{ color: colors.secondaryText }}>
              Are you sure you want to delete this budget alert? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {alertToDelete && (
            <div className="py-4">
              <div className="rounded-lg p-4" style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray, border: '1px solid' }}>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm" style={{ color: colors.secondaryText }}>Provider:</span>
                    <span className="text-sm font-medium" style={{ color: colors.primaryText }}>
                      {getProviderName(alertToDelete.platform_provider_id, alertToDelete.provider_name)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm" style={{ color: colors.secondaryText }}>Organization:</span>
                    <span className="text-sm font-medium" style={{ color: colors.primaryText }}>
                      {getOrganizationName(alertToDelete.organization_id, alertToDelete.organization_name)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm" style={{ color: colors.secondaryText }}>Alert Type:</span>
                    <span className="text-sm font-medium capitalize" style={{ color: colors.primaryText }}>
                      {alertToDelete.alert_type.replace("_", " ")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm" style={{ color: colors.secondaryText }}>Threshold:</span>
                    <span className="text-sm font-medium" style={{ color: colors.primaryText }}>
                      {alertToDelete.threshold_percentage}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setIsDeleteDialogOpen(false);
                setAlertToDelete(null);
              }}
              disabled={isDeleting}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDeleteAlert}
              disabled={isDeleting}
              className="hover:opacity-90"
              style={{ backgroundColor: colors.error, color: "white" }}
            >
              {isDeleting ? (
                <>
                  <span className="animate-spin mr-2">⏳</span>
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Alert
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
