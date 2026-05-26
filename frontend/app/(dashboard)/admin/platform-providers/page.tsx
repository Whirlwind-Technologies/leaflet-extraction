"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import {
  Brain,
  Plus,
  Settings,
  AlertTriangle,
  DollarSign,
  Loader2,
  MoreHorizontal,
  Play,
  Trash2,
  Edit,
  RefreshCw,
  Search,
  Filter,
  XCircle,
  Check,
} from "lucide-react";
import { brandColors as colors } from "@/lib/brand-colors";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// Import admin actions and types
import {
  getPlatformProviders,
  createPlatformProvider,
  updatePlatformProvider,
  deletePlatformProvider,
  testPlatformProvider,
  bulkTestProviders,
  PlatformProvider,
  PlatformVLMProviderType,
} from "@/lib/actions/admin";

interface ProviderFormData {
  name: string;
  provider_type: PlatformVLMProviderType | "";
  api_key: string;
  model_name: string;
  priority: number;
  monthly_budget: number | undefined;
  api_endpoint: string | undefined;
  region: string | undefined;
}

const PROVIDER_TYPES = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google Gemini" },
  { value: "azure_openai", label: "Azure OpenAI" },
  { value: "aws_bedrock", label: "AWS Bedrock" },
  { value: "custom", label: "Custom Provider" },
];

export default function PlatformProvidersPage() {
  const [providers, setProviders] = useState<PlatformProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<PlatformProvider | null>(null);
  const [deletingProvider, setDeletingProvider] = useState<PlatformProvider | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [testingProviders, setTestingProviders] = useState<Set<string>>(new Set());

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    provider_type: "" as PlatformVLMProviderType | "",
    api_key: "",
    model_name: "",
    priority: 1,
    monthly_budget: undefined as number | undefined,
    api_endpoint: undefined as string | undefined,
    region: undefined as string | undefined,
  });

  const loadProviders = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getPlatformProviders({
        search: searchTerm || undefined,
        provider_type: typeFilter !== "all" ? (typeFilter as PlatformVLMProviderType) : undefined,
        is_active: statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined,
        limit: 100
      });

      if (result.success && result.data) {
        setProviders(result.data);
      } else {
        toast.error(result.error || "Failed to load providers");
      }
    } catch (error) {
      toast.error("Failed to load providers");
      console.error("Load providers error:", error);
    } finally {
      setLoading(false);
    }
  }, [searchTerm, statusFilter, typeFilter]);

  // Load providers on mount and when filters change
  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleProviderTypeChange = (type: PlatformVLMProviderType) => {
    const defaultModels: Record<PlatformVLMProviderType, string> = {
      anthropic: "claude-sonnet-4.5-20250929",
      openai: "gpt-4o-latest-20250326",
      google: "gemini-2.5-pro",
      azure_openai: "gpt-4o-latest-20250326",
      aws_bedrock: "anthropic.claude-opus-4.5-20251124-v1:0",
      custom: "custom-model-name"
    };

    setFormData(prev => ({
      ...prev,
      provider_type: type,
      model_name: defaultModels[type] || "",
    }));
  };

  const handleCreateProvider = async () => {
    if (!formData.api_key || !formData.name || !formData.provider_type) {
      toast.error("Please fill in all required fields");
      return;
    }

    setFormLoading(true);
    try {
      const result = await createPlatformProvider({
        ...formData,
        provider_type: formData.provider_type as "anthropic" | "openai" | "google" | "azure_openai" | "aws_bedrock" | "custom",
      });

      if (result.success) {
        toast.success("Platform provider created successfully");
        setCreateDialogOpen(false);
        resetForm();
        loadProviders();
      } else {
        toast.error(result.error || "Failed to create provider");
      }
    } catch (error) {
      toast.error("Failed to create provider");
      console.error("Create provider error:", error);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdateProvider = async () => {
    if (!editingProvider) return;

    setFormLoading(true);
    try {
      const result = await updatePlatformProvider({
        id: editingProvider.id,
        ...formData,
        provider_type: formData.provider_type ? formData.provider_type as "anthropic" | "openai" | "google" | "azure_openai" | "aws_bedrock" | "custom" : undefined,
      });

      if (result.success) {
        toast.success("Platform provider updated successfully");
        setEditDialogOpen(false);
        setEditingProvider(null);
        resetForm();
        loadProviders();
      } else {
        toast.error(result.error || "Failed to update provider");
      }
    } catch (error) {
      toast.error("Failed to update provider");
      console.error("Update provider error:", error);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteProvider = async (provider: PlatformProvider) => {
    setDeletingProvider(provider);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteProvider = async () => {
    if (!deletingProvider) return;

    setDeleteLoading(true);
    try {
      const result = await deletePlatformProvider(deletingProvider.id);

      if (result.success) {
        toast.success("Platform provider deleted successfully");
        setDeleteDialogOpen(false);
        setDeletingProvider(null);
        loadProviders();
      } else {
        toast.error(result.error || "Failed to delete provider");
      }
    } catch (error) {
      toast.error("Failed to delete provider");
      console.error("Delete provider error:", error);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleTestProvider = async (id: string) => {
    setTestingProviders(prev => new Set([...prev, id]));

    try {
      const result = await testPlatformProvider(id);

      if (result.success && result.data) {
        if (result.data.success) {
          toast.success(`Provider responded in ${result.data.response_time_ms}ms`);
        } else {
          toast.error(result.data.error_message || "Provider test failed");
        }
      } else {
        toast.error(result.error || "Failed to test provider");
      }
    } catch (error) {
      toast.error("Failed to test provider");
      console.error("Test provider error:", error);
    } finally {
      setTestingProviders(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleBulkTest = async () => {
    if (selectedIds.size === 0) {
      toast.error("Please select providers to test");
      return;
    }

    const ids = Array.from(selectedIds);
    setTestingProviders(new Set(ids));

    try {
      const result = await bulkTestProviders(ids);

      if (result.success && result.data) {
        const successful = result.data.filter(r => r.success).length;
        const failed = result.data.length - successful;

        if (failed > 0) {
          toast.error(`${successful} providers passed, ${failed} failed`);
        } else {
          toast.success(`All ${successful} providers passed`);
        }
      } else {
        toast.error(result.error || "Failed to test providers");
      }
    } catch (error) {
      toast.error("Failed to test providers");
      console.error("Bulk test error:", error);
    } finally {
      setTestingProviders(new Set());
    }
  };

  const handleEditProvider = (provider: PlatformProvider) => {
    setEditingProvider(provider);
    setFormData({
      name: provider.name,
      provider_type: provider.provider_type as PlatformVLMProviderType,
      api_key: "", // Don't pre-fill for security
      model_name: provider.model_name,
      priority: provider.priority,
      monthly_budget: provider.monthly_budget,
      api_endpoint: provider.api_endpoint,
      region: undefined,
    });
    setEditDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      provider_type: "",
      api_key: "",
      model_name: "",
      priority: 1,
      monthly_budget: undefined,
      api_endpoint: undefined,
      region: undefined,
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(providers.map(p => p.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectProvider = (id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(id);
      } else {
        newSet.delete(id);
      }
      return newSet;
    });
  };

  // Calculate stats
  const totalProviders = providers.length;
  const activeProviders = providers.filter(p => p.is_active).length;
  const totalSpent = providers.reduce((sum, p) => sum + p.total_spent, 0);
  const monthlySpent = providers.reduce((sum, p) => sum + p.current_month_spent, 0);

  return (
    <div className="container mx-auto pb-6 max-w-7xl" style={{ backgroundColor: colors.offWhiteBg }}>
      {/* Header */}
      <div className="mb-12">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
              Platform <span className="font-normal">Providers</span>
            </h1>
            <p className="text-sm" style={{ color: colors.secondaryText }}>
              Manage system-wide VLM providers for the platform
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={loadProviders}
              disabled={loading}
              style={{ borderColor: colors.borderGray, color: colors.secondaryText }}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button style={{ backgroundColor: colors.primaryBrandBlue, color: colors.pureWhite }} className="hover:opacity-90">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Provider
                </Button>
              </DialogTrigger>
              <ProviderFormDialog
                title="Create Platform Provider"
                description="Add a new VLM provider for the platform"
                formData={formData}
                onFormDataChange={setFormData}
                onProviderTypeChange={handleProviderTypeChange}
                onSubmit={handleCreateProvider}
                onCancel={() => {
                  setCreateDialogOpen(false);
                  resetForm();
                }}
                isLoading={formLoading}
              />
            </Dialog>
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Providers</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{totalProviders}</p>
                  <p className="text-xs mt-1" style={{ color: colors.primaryBrandBlue }}>{activeProviders} active</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                  <Brain className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Spent</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>${totalSpent.toFixed(2)}</p>
                  <p className="text-xs mt-1" style={{ color: colors.success }}>All-time</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.successBg }}>
                  <DollarSign className="h-6 w-6" style={{ color: colors.success }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Monthly Spent</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>${monthlySpent.toFixed(2)}</p>
                  <p className="text-xs mt-1" style={{ color: colors.warning }}>Current month</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.warningBg }}>
                  <DollarSign className="h-6 w-6" style={{ color: colors.warning }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Selected</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{selectedIds.size}</p>
                  <p className="text-xs mt-1" style={{ color: colors.info }}>for bulk operations</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.infoBg }}>
                  <Settings className="h-6 w-6" style={{ color: colors.info }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filter Bar */}
        <Card style={{ borderColor: colors.borderGray }}>
          <CardContent className="pt-6">
            <div className="flex flex-col sm:flex-row gap-4">
              {/* Search Input */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: colors.secondaryText }} />
                <Input
                  type="text"
                  placeholder="Search providers..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 h-10"
                  style={{ borderColor: colors.borderGray }}
                />
                {searchTerm && (
                  <button
                    onClick={() => setSearchTerm("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2"
                    style={{ color: colors.secondaryText }}
                  >
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Provider Type Filter */}
              <div className="w-full sm:w-[200px]">
                <Select value={typeFilter} onValueChange={setTypeFilter}>
                  <SelectTrigger className="h-10" style={{ borderColor: colors.borderGray }}>
                    <div className="flex items-center gap-2">
                      <Filter className="h-4 w-4" style={{ color: colors.secondaryText }} />
                      <SelectValue placeholder="Provider Type" />
                    </div>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    {PROVIDER_TYPES.map((p) => (
                      <SelectItem key={p.value} value={p.value}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Status Filter */}
              <div className="w-full sm:w-[160px]">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="h-10" style={{ borderColor: colors.borderGray }}>
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Bulk Test Button */}
              <Button
                variant="outline"
                onClick={handleBulkTest}
                disabled={selectedIds.size === 0 || testingProviders.size > 0}
                style={{ borderColor: colors.borderGray, color: colors.secondaryText }}
              >
                <Play className="h-4 w-4 mr-2" />
                Test Selected ({selectedIds.size})
              </Button>
            </div>

            {/* Results Count */}
            <div className="mt-4 text-sm" style={{ color: colors.secondaryText }}>
              Showing <span className="font-medium" style={{ color: colors.deepNavy }}>{providers.length}</span> providers
            </div>
          </CardContent>
        </Card>

        {/* Providers Table */}
        {loading ? (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardContent className="py-12">
              <div className="flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin" style={{ color: colors.primaryBrandBlue }} />
                <span className="ml-2" style={{ color: colors.secondaryText }}>Loading providers...</span>
              </div>
            </CardContent>
          </Card>
        ) : providers.length === 0 ? (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardContent className="py-12">
              <div className="text-center">
                <Brain className="h-12 w-12 mx-auto mb-4" style={{ color: colors.disabledGray }} strokeWidth={1.5} />
                <h3 className="text-lg font-normal mb-2" style={{ color: colors.deepNavy }}>No Providers Found</h3>
                <p className="text-sm" style={{ color: colors.secondaryText }}>
                  Add your first platform provider to get started.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardHeader style={{ backgroundColor: colors.offWhiteBg, borderBottom: `1px solid ${colors.borderGray}` }}>
              <CardTitle className="text-base" style={{ color: colors.deepNavy }}>Platform Providers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border" style={{ borderColor: colors.borderGray }}>
                <Table>
                  <TableHeader>
                    <TableRow style={{ backgroundColor: colors.hoverGray }}>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={selectedIds.size === providers.length && providers.length > 0}
                          onCheckedChange={handleSelectAll}
                        />
                      </TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Provider</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Type</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Model</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Priority</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Status</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Usage</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Budget</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-right" style={{ color: colors.secondaryText }}>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {providers.map((provider) => (
                      <ProviderRow
                        key={provider.id}
                        provider={provider}
                        isSelected={selectedIds.has(provider.id)}
                        onSelect={handleSelectProvider}
                        onEdit={handleEditProvider}
                        onDelete={handleDeleteProvider}
                        onTest={handleTestProvider}
                        isTesting={testingProviders.has(provider.id)}
                      />
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <ProviderFormDialog
          title="Edit Platform Provider"
          description="Update platform provider configuration"
          formData={formData}
          onFormDataChange={setFormData}
          onProviderTypeChange={handleProviderTypeChange}
          onSubmit={handleUpdateProvider}
          onCancel={() => {
            setEditDialogOpen(false);
            setEditingProvider(null);
            resetForm();
          }}
          isLoading={formLoading}
          isEditing={true}
        />
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!deleteLoading) {
          setDeleteDialogOpen(open);
          if (!open) setDeletingProvider(null);
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ color: colors.error }}>
              <AlertTriangle className="h-5 w-5" />
              Delete Platform Provider
            </DialogTitle>
            <DialogDescription className="pt-2">
              Are you sure you want to delete this platform provider? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {deletingProvider && (
            <div className="my-4 p-4 rounded-lg" style={{ backgroundColor: colors.hoverGray, borderColor: colors.borderGray, border: `1px solid ${colors.borderGray}` }}>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm" style={{ color: colors.secondaryText }}>Name:</span>
                  <span className="text-sm font-medium" style={{ color: colors.deepNavy }}>{deletingProvider.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm" style={{ color: colors.secondaryText }}>Type:</span>
                  <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
                    style={{ backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: "#C7DBED" }}>
                    {deletingProvider.provider_display_name}
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm" style={{ color: colors.secondaryText }}>Model:</span>
                  <span className="text-sm" style={{ color: colors.deepNavy }}>{deletingProvider.model_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm" style={{ color: colors.secondaryText }}>Total Requests:</span>
                  <span className="text-sm" style={{ color: colors.deepNavy }}>{deletingProvider.total_requests.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm" style={{ color: colors.secondaryText }}>Total Spent:</span>
                  <span className="text-sm" style={{ color: colors.deepNavy }}>${deletingProvider.total_spent.toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}

          {deletingProvider && deletingProvider.total_requests > 0 && (
            <div className="flex items-start gap-2 p-3 rounded-lg" style={{ backgroundColor: colors.warningBg, border: `1px solid ${colors.warningBorder}` }}>
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" style={{ color: colors.warning }} />
              <p className="text-sm" style={{ color: colors.warningText }}>
                This provider has been used for {deletingProvider.total_requests.toLocaleString()} requests.
                All usage history will be preserved.
              </p>
            </div>
          )}

          <DialogFooter className="gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false);
                setDeletingProvider(null);
              }}
              disabled={deleteLoading}
              style={{ borderColor: colors.borderGray }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDeleteProvider}
              disabled={deleteLoading}
              style={{ backgroundColor: colors.error }}
              className="hover:opacity-90"
            >
              {deleteLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Provider
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Provider Table Row Component
function ProviderRow({
  provider,
  isSelected,
  onSelect,
  onEdit,
  onDelete,
  onTest,
  isTesting
}: {
  provider: PlatformProvider;
  isSelected: boolean;
  onSelect: (id: string, checked: boolean) => void;
  onEdit: (provider: PlatformProvider) => void;
  onDelete: (provider: PlatformProvider) => void;
  onTest: (id: string) => void;
  isTesting: boolean;
}) {
  const getStatusBadge = () => {
    if (!provider.is_active) {
      return (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.hoverGray, color: colors.secondaryText, borderColor: colors.borderGray }}>
          Inactive
        </div>
      );
    }
    if (provider.is_default) {
      return (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.infoBg, color: colors.infoText, borderColor: colors.infoBorder }}>
          Default
        </div>
      );
    }
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
        style={{ backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }}>
        <Check className="h-3 w-3" />
        Active
      </div>
    );
  };

  const getBudgetStatus = () => {
    if (!provider.monthly_budget) return "No limit";
    const percentage = (provider.current_month_spent / provider.monthly_budget) * 100;
    return `$${provider.current_month_spent.toFixed(2)} / $${provider.monthly_budget} (${percentage.toFixed(0)}%)`;
  };

  const getProviderLabel = (type: string) => {
    return PROVIDER_TYPES.find((p) => p.value === type)?.label || type;
  };

  return (
    <TableRow className="hover:bg-gray-50/50">
      <TableCell>
        <Checkbox
          checked={isSelected}
          onCheckedChange={(checked) => onSelect(provider.id, checked as boolean)}
        />
      </TableCell>
      <TableCell>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: colors.lightBlueTint }}>
            <Brain className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} />
          </div>
          <div>
            <div className="font-medium" style={{ color: colors.deepNavy }}>{provider.name}</div>
            <div className="text-sm font-mono" style={{ color: colors.secondaryText }}>Key: {provider.masked_api_key}</div>
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: "#C7DBED" }}>
          {getProviderLabel(provider.provider_type)}
        </div>
      </TableCell>
      <TableCell>
        <div className="text-sm" style={{ color: colors.deepNavy }}>{provider.model_name}</div>
      </TableCell>
      <TableCell style={{ color: colors.deepNavy }}>{provider.priority}</TableCell>
      <TableCell>{getStatusBadge()}</TableCell>
      <TableCell>
        <div className="text-sm">
          <div style={{ color: colors.deepNavy }}>{provider.total_requests} requests</div>
          <div style={{ color: colors.secondaryText }}>${provider.total_spent.toFixed(2)} total</div>
        </div>
      </TableCell>
      <TableCell>
        <div className="text-sm" style={{ color: colors.deepNavy }}>{getBudgetStatus()}</div>
      </TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => onTest(provider.id)} disabled={isTesting}>
              {isTesting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Test Connection
                </>
              )}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onEdit(provider)}>
              <Edit className="h-4 w-4 mr-2" />
              Edit Provider
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDelete(provider)}
              className="text-red-600"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete Provider
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

// Provider Form Dialog Component
function ProviderFormDialog({
  title,
  description,
  formData,
  onFormDataChange,
  onProviderTypeChange,
  onSubmit,
  onCancel,
  isLoading,
  isEditing = false,
}: {
  title: string;
  description: string;
  formData: ProviderFormData;
  onFormDataChange: (data: ProviderFormData) => void;
  onProviderTypeChange: (type: PlatformVLMProviderType) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isLoading: boolean;
  isEditing?: boolean;
}) {
  const updateFormData = (updates: Partial<ProviderFormData>) => {
    onFormDataChange({ ...formData, ...updates });
  };

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Provider Name *</Label>
            <Input
              value={formData.name}
              onChange={(e) => updateFormData({ name: e.target.value })}
              placeholder="My Anthropic Provider"
              style={{ borderColor: colors.borderGray }}
            />
          </div>

          <div className="space-y-2">
            <Label>Provider Type *</Label>
            <Select
              value={formData.provider_type || undefined}
              onValueChange={(value: PlatformVLMProviderType) => {
                onProviderTypeChange(value);
              }}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <SelectValue placeholder="Select provider type" />
              </SelectTrigger>
              <SelectContent>
                {PROVIDER_TYPES.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label>API Key {isEditing ? "(leave blank to keep current)" : "*"}</Label>
          <Input
            type="password"
            value={formData.api_key}
            onChange={(e) => updateFormData({ api_key: e.target.value })}
            placeholder={isEditing ? "Leave blank to keep current key" : "Enter API key"}
            style={{ borderColor: colors.borderGray }}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Model Name</Label>
            <Input
              value={formData.model_name}
              onChange={(e) => updateFormData({ model_name: e.target.value })}
              placeholder="claude-sonnet-4.5-20250929"
              style={{ borderColor: colors.borderGray }}
            />
          </div>

          <div className="space-y-2">
            <Label>Priority (1-999)</Label>
            <Input
              type="number"
              min="1"
              max="999"
              value={formData.priority}
              onChange={(e) => updateFormData({ priority: parseInt(e.target.value) || 1 })}
              style={{ borderColor: colors.borderGray }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Monthly Budget (USD)</Label>
            <Input
              type="number"
              min="0"
              step="0.01"
              value={formData.monthly_budget || ""}
              onChange={(e) => updateFormData({ monthly_budget: e.target.value ? parseFloat(e.target.value) : undefined })}
              placeholder="Optional budget limit"
              style={{ borderColor: colors.borderGray }}
            />
          </div>

          <div className="space-y-2">
            <Label>API Endpoint (Optional)</Label>
            <Input
              value={formData.api_endpoint || ""}
              onChange={(e) => updateFormData({ api_endpoint: e.target.value || undefined })}
              placeholder="Custom endpoint URL"
              style={{ borderColor: colors.borderGray }}
            />
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={isLoading} style={{ borderColor: colors.borderGray }}>
          Cancel
        </Button>
        <Button
          onClick={onSubmit}
          disabled={isLoading || !formData.name || (!isEditing && !formData.provider_type) || (!isEditing && !formData.api_key)}
          style={{ backgroundColor: colors.primaryBrandBlue, color: colors.pureWhite }}
          className="hover:opacity-90"
        >
          {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {isEditing ? "Update" : "Create"} Provider
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
