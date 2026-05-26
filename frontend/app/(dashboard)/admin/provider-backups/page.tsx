"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  Database,
  ArrowLeft,
  HardDrive,
  RotateCcw,
  Clock,
  Download,
  Search,
  Filter,
  Plus,
  Eye,
  Trash2,
  User,
  RefreshCw,
  Archive,
  Shield,
} from "lucide-react";
import { toast } from "sonner";
import {
  getProviderBackups,
  restoreProviderBackup,
  createProviderBackup,
  deleteProviderBackup,
  downloadProviderBackup,
  getPlatformProviders,
} from "@/lib/actions/admin";
import { brandColors as colors } from "@/lib/brand-colors";

interface VLMProviderBackup {
  id: string;
  provider_id: string;
  provider_name: string;
  provider_type: string;
  backup_type: "manual" | "scheduled" | "pre_change";
  backup_data: {
    name: string;
    provider_type: string;
    api_endpoint?: string;
    model_name: string;
    max_tokens: number;
    temperature: number;
    config: Record<string, unknown>;
    priority: number;
    is_active: boolean;
    is_default: boolean;
    monthly_budget?: number;
    daily_budget?: number;
    max_requests_per_hour: number;
  };
  description?: string;
  created_by_user_id: string;
  created_by_email: string;
  created_at: string;
  file_size_bytes: number;
  checksum: string;
  is_compressed: boolean;
  restoration_count: number;
  last_restored_at?: string;
}

interface PlatformProvider {
  id: string;
  name: string;
  provider_type: string;
  is_active: boolean;
}

interface BackupFilters {
  search: string;
  provider_id: string;
  backup_type: string;
  start_date: string;
  end_date: string;
}

export default function ProviderBackupsPage() {
  const [backups, setBackups] = useState<VLMProviderBackup[]>([]);
  const [providers, setProviders] = useState<PlatformProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [selectedBackup, setSelectedBackup] = useState<VLMProviderBackup | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);

  const [filters, setFilters] = useState<BackupFilters>({
    search: "",
    provider_id: "",
    backup_type: "",
    start_date: "",
    end_date: "",
  });

  const [formData, setFormData] = useState<{
    provider_id: string;
    backup_type: "manual" | "scheduled" | "pre_change";
    description: string;
  }>({
    provider_id: "",
    backup_type: "manual",
    description: "",
  });

  const fetchBackups = useCallback(async () => {
    try {
      setLoading(true);
      const filterParams = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value)
      );

      const result = await getProviderBackups(filterParams);

      if (result.success && result.data) {
        setBackups((result.data.items || []) as unknown as VLMProviderBackup[]);
      } else {
        throw new Error(result.error || "Failed to fetch provider backups");
      }
    } catch (error) {
      console.error("Error fetching backups:", error);
      toast.error("Failed to load provider backups");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchBackups();
    fetchProviders();
  }, [fetchBackups]);

  const fetchProviders = async () => {
    try {
      const result = await getPlatformProviders({});

      if (result.success && result.data) {
        setProviders(result.data || []);
      }
    } catch (error) {
      console.error("Error fetching providers:", error);
    }
  };

  const handleCreateBackup = async () => {
    if (!formData.provider_id) {
      toast.error("Please select a provider to backup");
      return;
    }

    try {
      setCreating(true);
      const result = await createProviderBackup(formData);

      if (result.success) {
        toast.success("Provider backup created successfully");
        setIsCreateDialogOpen(false);
        setFormData({
          provider_id: "",
          backup_type: "manual",
          description: "",
        });
        fetchBackups();
      } else {
        throw new Error(result.error || "Failed to create backup");
      }
    } catch (error) {
      console.error("Error creating backup:", error);
      toast.error(error instanceof Error ? error.message : "Failed to create backup");
    } finally {
      setCreating(false);
    }
  };

  const handleRestoreBackup = async (backupId: string) => {
    const reason = prompt("Please provide a reason for restoring this backup:");
    if (!reason) {
      return;
    }

    if (!confirm("Are you sure you want to restore this backup? This will overwrite the current provider configuration.")) {
      return;
    }

    try {
      setRestoring(backupId);
      const result = await restoreProviderBackup(backupId, reason);

      if (result.success) {
        toast.success("Provider backup restored successfully");
        fetchBackups();
      } else {
        throw new Error(result.error || "Failed to restore backup");
      }
    } catch (error) {
      console.error("Error restoring backup:", error);
      toast.error(error instanceof Error ? error.message : "Failed to restore backup");
    } finally {
      setRestoring(null);
    }
  };

  const handleDeleteBackup = async (backupId: string) => {
    if (!confirm("Are you sure you want to delete this backup? This action cannot be undone.")) {
      return;
    }

    try {
      const result = await deleteProviderBackup(backupId);

      if (result.success) {
        toast.success("Provider backup deleted successfully");
        fetchBackups();
      } else {
        throw new Error(result.error || "Failed to delete backup");
      }
    } catch (error) {
      console.error("Error deleting backup:", error);
      toast.error("Failed to delete backup");
    }
  };

  const handleDownloadBackup = async (backupId: string, filename?: string) => {
    try {
      const result = await downloadProviderBackup(backupId);

      if (result.success && result.data) {
        // Create a temporary link to trigger download
        const a = document.createElement("a");
        a.href = result.data.download_url;
        a.download = filename || result.data.filename || `backup-${backupId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        toast.success("Backup downloaded successfully");
      } else {
        throw new Error(result.error || "Failed to download backup");
      }
    } catch (error) {
      console.error("Error downloading backup:", error);
      toast.error("Failed to download backup");
    }
  };

  const handleFilterChange = (key: keyof BackupFilters, value: string) => {
    setFilters({ ...filters, [key]: value });
  };

  const clearFilters = () => {
    setFilters({
      search: "",
      provider_id: "",
      backup_type: "",
      start_date: "",
      end_date: "",
    });
  };

  const openDetailDialog = (backup: VLMProviderBackup) => {
    setSelectedBackup(backup);
    setIsDetailDialogOpen(true);
  };

  const formatFileSize = (bytes: number) => {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  const getBackupTypeIcon = (type: string) => {
    switch (type) {
      case "manual":
        return <User className="h-4 w-4" style={{ color: colors.info }} />;
      case "scheduled":
        return <Clock className="h-4 w-4" style={{ color: colors.success }} />;
      case "pre_change":
        return <Shield className="h-4 w-4" style={{ color: colors.warning }} />;
      default:
        return <Database className="h-4 w-4" style={{ color: colors.secondaryText }} />;
    }
  };

  const getBackupTypeBadgeStyle = (type: string) => {
    switch (type) {
      case "manual":
        return { backgroundColor: colors.infoBg, color: colors.infoText, borderColor: colors.infoBorder };
      case "scheduled":
        return { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder };
      case "pre_change":
        return { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder };
      default:
        return { backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray };
    }
  };

  const filteredBackups = backups.filter((backup) => {
    const matchesSearch = backup.provider_name.toLowerCase().includes(filters.search.toLowerCase()) ||
                         backup.description?.toLowerCase().includes(filters.search.toLowerCase()) ||
                         backup.created_by_email.toLowerCase().includes(filters.search.toLowerCase());
    const matchesProvider = !filters.provider_id || backup.provider_id === filters.provider_id;
    const matchesType = !filters.backup_type || backup.backup_type === filters.backup_type;
    const matchesStartDate = !filters.start_date || new Date(backup.created_at) >= new Date(filters.start_date);
    const matchesEndDate = !filters.end_date || new Date(backup.created_at) <= new Date(filters.end_date);

    return matchesSearch && matchesProvider && matchesType && matchesStartDate && matchesEndDate;
  });

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
                Provider <span className="font-normal">Backups</span>
              </h1>
              <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
                Manage VLM provider configuration backups and restore points
              </p>
            </div>
          </div>
        </div>
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto" style={{ borderColor: colors.primaryBrandBlue }}></div>
            <p className="mt-4" style={{ color: colors.secondaryText }}>Loading provider backups...</p>
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
              Provider <span className="font-normal">Backups</span>
            </h1>
            <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
              Manage VLM provider configuration backups and restore points
            </p>
          </div>
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                <Plus className="h-4 w-4 mr-2" />
                Create Backup
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle style={{ color: colors.primaryText }}>Create Provider Backup</DialogTitle>
                <DialogDescription style={{ color: colors.secondaryText }}>
                  Create a backup of a platform provider configuration for restore purposes.
                </DialogDescription>
              </DialogHeader>

              <div className="grid gap-4 py-4">
                <div>
                  <Label htmlFor="provider_id" style={{ color: colors.primaryText }}>Platform Provider *</Label>
                  <Select
                    value={formData.provider_id || undefined}
                    onValueChange={(value) =>
                      setFormData({ ...formData, provider_id: value })
                    }
                  >
                    <SelectTrigger style={{ borderColor: colors.borderGray }}>
                      <SelectValue placeholder="Select provider to backup..." />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map((provider) => (
                        <SelectItem key={provider.id} value={provider.id}>
                          {provider.name} ({provider.provider_type})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="backup_type" style={{ color: colors.primaryText }}>Backup Type</Label>
                  <Select value={formData.backup_type} onValueChange={(value: string) =>
                    setFormData({ ...formData, backup_type: value as "manual" | "scheduled" | "pre_change" })
                  }>
                    <SelectTrigger style={{ borderColor: colors.borderGray }}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="manual">Manual Backup</SelectItem>
                      <SelectItem value="scheduled">Scheduled Backup</SelectItem>
                      <SelectItem value="pre_change">Pre-Change Backup</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="description" style={{ color: colors.primaryText }}>Description (Optional)</Label>
                  <Textarea
                    placeholder="Describe the purpose of this backup..."
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    style={{ borderColor: colors.borderGray }}
                  />
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)} style={{ borderColor: colors.borderGray }}>
                  Cancel
                </Button>
                <Button onClick={handleCreateBackup} disabled={creating} style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }}>
                  {creating ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Database className="h-4 w-4 mr-2" />
                  )}
                  Create Backup
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
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Backups</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{backups.length}</p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                <Archive className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Manual Backups</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {backups.filter(b => b.backup_type === "manual").length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.infoBg }}>
                <User className="h-6 w-6" style={{ color: colors.info }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Scheduled Backups</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {backups.filter(b => b.backup_type === "scheduled").length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.successBg }}>
                <Clock className="h-6 w-6" style={{ color: colors.success }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Size</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {formatFileSize(backups.reduce((sum, b) => sum + b.file_size_bytes, 0))}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                <HardDrive className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white mb-6" style={{ borderColor: colors.borderGray }}>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4" style={{ color: colors.secondaryText }} />
              <Input
                placeholder="Search backups..."
                value={filters.search}
                onChange={(e) => handleFilterChange("search", e.target.value)}
                className="pl-10"
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <Select
              value={filters.provider_id || "all"}
              onValueChange={(value) => handleFilterChange("provider_id", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <Database className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Providers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Providers</SelectItem>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id}>
                    {provider.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={filters.backup_type || "all"}
              onValueChange={(value) => handleFilterChange("backup_type", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <Filter className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="manual">Manual</SelectItem>
                <SelectItem value="scheduled">Scheduled</SelectItem>
                <SelectItem value="pre_change">Pre-Change</SelectItem>
              </SelectContent>
            </Select>

            <div>
              <Input
                type="date"
                placeholder="Start Date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange("start_date", e.target.value)}
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <Button variant="outline" onClick={clearFilters} style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Backups Table */}
      <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
            <Database className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
            Provider Backups ({filteredBackups.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredBackups.length === 0 ? (
            <div className="text-center p-12">
              <div className="p-6 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center" style={{ backgroundColor: colors.offWhiteBg }}>
                <Archive className="h-12 w-12" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
              </div>
              <h3 className="text-xl font-light mb-4" style={{ color: colors.primaryText }}>No Provider Backups</h3>
              <p className="max-w-md mx-auto mb-8" style={{ color: colors.secondaryText }}>
                No provider backups found. Create your first backup to get started with configuration recovery.
              </p>
              <Button
                onClick={() => setIsCreateDialogOpen(true)}
                style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }}
                className="hover:opacity-90"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Backup
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow style={{ borderColor: colors.borderGray }}>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Provider & Type</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Backup Type</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Created By</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Created At</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Size</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Restorations</TableHead>
                  <TableHead className="font-light text-right" style={{ color: colors.secondaryText }}>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredBackups.map((backup) => (
                  <TableRow key={backup.id} className="transition-colors" style={{ borderColor: colors.borderGray }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                    <TableCell>
                      <div>
                        <div className="font-medium" style={{ color: colors.primaryText }}>{backup.provider_name}</div>
                        <div className="text-sm capitalize" style={{ color: colors.secondaryText }}>
                          {backup.provider_type.replace("_", " ")}
                        </div>
                        {backup.description && (
                          <div className="text-xs mt-1 max-w-[200px] truncate" style={{ color: colors.secondaryText }}>
                            {backup.description}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                        style={getBackupTypeBadgeStyle(backup.backup_type)}
                      >
                        {getBackupTypeIcon(backup.backup_type)}
                        {backup.backup_type.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase())}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>{backup.created_by_email}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>
                          {new Date(backup.created_at).toLocaleDateString()}
                        </div>
                        <div className="text-xs" style={{ color: colors.secondaryText }}>
                          {new Date(backup.created_at).toLocaleTimeString()}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>{formatFileSize(backup.file_size_bytes)}</div>
                        {backup.is_compressed && (
                          <div className="text-xs" style={{ color: colors.secondaryText }}>Compressed</div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>{backup.restoration_count} times</div>
                        {backup.last_restored_at && (
                          <div className="text-xs" style={{ color: colors.secondaryText }}>
                            Last: {new Date(backup.last_restored_at).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDetailDialog(backup)}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          <Eye className="h-4 w-4" style={{ color: colors.info }} />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownloadBackup(backup.id, `${backup.provider_name}-backup-${backup.created_at}.json`)}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          <Download className="h-4 w-4" style={{ color: colors.success }} />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRestoreBackup(backup.id)}
                          disabled={restoring === backup.id}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          {restoring === backup.id ? (
                            <RefreshCw className="h-4 w-4 animate-spin" style={{ color: colors.warning }} />
                          ) : (
                            <RotateCcw className="h-4 w-4" style={{ color: colors.warning }} />
                          )}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteBackup(backup.id)}
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

      {/* Detail Dialog */}
      <Dialog open={isDetailDialogOpen} onOpenChange={setIsDetailDialogOpen}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle style={{ color: colors.primaryText }}>Backup Details</DialogTitle>
            <DialogDescription style={{ color: colors.secondaryText }}>
              Detailed information about this provider backup.
            </DialogDescription>
          </DialogHeader>

          {selectedBackup && (
            <div className="space-y-6 py-4">
              {/* Basic Info */}
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Basic Information</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Provider</Label>
                    <div className="font-medium" style={{ color: colors.primaryText }}>{selectedBackup.provider_name}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Provider Type</Label>
                    <div className="capitalize" style={{ color: colors.primaryText }}>{selectedBackup.provider_type.replace("_", " ")}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Backup Type</Label>
                    <div
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border w-fit mt-1"
                      style={getBackupTypeBadgeStyle(selectedBackup.backup_type)}
                    >
                      {getBackupTypeIcon(selectedBackup.backup_type)}
                      {selectedBackup.backup_type.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Created By</Label>
                    <div style={{ color: colors.primaryText }}>{selectedBackup.created_by_email}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Created At</Label>
                    <div style={{ color: colors.primaryText }}>{new Date(selectedBackup.created_at).toLocaleString()}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>File Size</Label>
                    <div style={{ color: colors.primaryText }}>{formatFileSize(selectedBackup.file_size_bytes)}</div>
                  </div>
                </div>
              </div>

              <Separator style={{ backgroundColor: colors.borderGray }} />

              {/* Restoration History */}
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Restoration History</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Restoration Count</Label>
                    <div style={{ color: colors.primaryText }}>{selectedBackup.restoration_count} times</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Last Restored At</Label>
                    <div style={{ color: colors.primaryText }}>
                      {selectedBackup.last_restored_at
                        ? new Date(selectedBackup.last_restored_at).toLocaleString()
                        : "Never"
                      }
                    </div>
                  </div>
                </div>
              </div>

              {selectedBackup.description && (
                <>
                  <Separator style={{ backgroundColor: colors.borderGray }} />
                  <div>
                    <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Description</h4>
                    <div className="border rounded-md p-3 text-sm" style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray, color: colors.primaryText }}>
                      {selectedBackup.description}
                    </div>
                  </div>
                </>
              )}

              {/* Technical Details */}
              <Separator style={{ backgroundColor: colors.borderGray }} />
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Technical Information</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Checksum</Label>
                    <div className="font-mono text-xs break-all" style={{ color: colors.primaryText }}>{selectedBackup.checksum}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Compressed</Label>
                    <div style={{ color: colors.primaryText }}>{selectedBackup.is_compressed ? "Yes" : "No"}</div>
                  </div>
                </div>
              </div>

              {/* Configuration Preview */}
              <Separator style={{ backgroundColor: colors.borderGray }} />
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Configuration Preview</h4>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Model</Label>
                      <div style={{ color: colors.primaryText }}>{selectedBackup.backup_data.model_name}</div>
                    </div>
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Priority</Label>
                      <div style={{ color: colors.primaryText }}>{selectedBackup.backup_data.priority}</div>
                    </div>
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Max Tokens</Label>
                      <div style={{ color: colors.primaryText }}>{selectedBackup.backup_data.max_tokens.toLocaleString()}</div>
                    </div>
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Temperature</Label>
                      <div style={{ color: colors.primaryText }}>{selectedBackup.backup_data.temperature}</div>
                    </div>
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Status</Label>
                      <div
                        className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border w-fit mt-1"
                        style={selectedBackup.backup_data.is_active
                          ? { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }
                          : { backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray }
                        }
                      >
                        {selectedBackup.backup_data.is_active ? "Active" : "Inactive"}
                      </div>
                    </div>
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Default Provider</Label>
                      <div
                        className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border w-fit mt-1"
                        style={selectedBackup.backup_data.is_default
                          ? { backgroundColor: colors.infoBg, color: colors.infoText, borderColor: colors.infoBorder }
                          : { backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray }
                        }
                      >
                        {selectedBackup.backup_data.is_default ? "Yes" : "No"}
                      </div>
                    </div>
                  </div>

                  {(selectedBackup.backup_data.monthly_budget || selectedBackup.backup_data.daily_budget) && (
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      {selectedBackup.backup_data.monthly_budget && (
                        <div>
                          <Label style={{ color: colors.secondaryText }}>Monthly Budget</Label>
                          <div style={{ color: colors.primaryText }}>${selectedBackup.backup_data.monthly_budget}</div>
                        </div>
                      )}
                      {selectedBackup.backup_data.daily_budget && (
                        <div>
                          <Label style={{ color: colors.secondaryText }}>Daily Budget</Label>
                          <div style={{ color: colors.primaryText }}>${selectedBackup.backup_data.daily_budget}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailDialogOpen(false)} style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
              Close
            </Button>
            {selectedBackup && (
              <>
                <Button
                  variant="outline"
                  onClick={() => handleDownloadBackup(selectedBackup.id, `${selectedBackup.provider_name}-backup-${selectedBackup.created_at}.json`)}
                  style={{ borderColor: colors.borderGray, color: colors.primaryText }}
                >
                  <Download className="h-4 w-4 mr-2" style={{ color: colors.success }} />
                  Download
                </Button>
                <Button
                  onClick={() => handleRestoreBackup(selectedBackup.id)}
                  disabled={restoring === selectedBackup.id}
                  style={{ backgroundColor: colors.warning, color: "white" }}
                  className="hover:opacity-90"
                >
                  {restoring === selectedBackup.id ? (
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <RotateCcw className="h-4 w-4 mr-2" />
                  )}
                  Restore
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
