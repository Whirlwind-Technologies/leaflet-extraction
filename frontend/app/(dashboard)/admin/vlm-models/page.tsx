"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";


import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  Cpu,
  Plus,
  Settings,
  Loader2,
  MoreHorizontal,
  Trash2,
  Edit,
  RefreshCw,
  Star,
  AlertTriangle,
  DollarSign,
  Check,
  Search,
  Filter,
  XCircle,
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

import {
  getVlmModels,
  createVlmModel,
  updateVlmModel,
  deleteVlmModel,
  setDefaultVlmModel,
  deprecateVlmModel,
  VlmModel,
  VlmModelCreate,
  VlmModelUpdate,
} from "@/lib/actions/admin-vlm-models";

const PROVIDER_TYPES = [
  { value: "anthropic", label: "Anthropic Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google Gemini" },
  { value: "azure_openai", label: "Azure OpenAI" },
  { value: "aws_bedrock", label: "AWS Bedrock" },
];

export default function VlmModelsPage() {
  const [models, setModels] = useState<VlmModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [providerFilter, setProviderFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deprecateDialogOpen, setDeprecateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<VlmModel | null>(null);
  const [deprecatingModel, setDeprecatingModel] = useState<VlmModel | null>(null);
  const [modelToDelete, setModelToDelete] = useState<{ id: string; display_name: string; model_id: string; provider_type: string } | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState<VlmModelCreate>({
    provider_type: "anthropic",
    model_id: "",
    display_name: "",
    description: "",
    max_tokens: 8192,
    context_window: 200000,
    temperature_default: 0.1,
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    supports_vision: true,
    supports_tools: true,
    is_default: false,
    is_active: true,
    sort_order: 100,
  });

  const [replacementModelId, setReplacementModelId] = useState<string>("");

  const loadModels = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getVlmModels({
        provider_type: providerFilter !== "all" ? providerFilter : undefined,
        is_active: statusFilter === "active" ? true : statusFilter === "inactive" ? false : undefined,
      });

      if (result.success && result.data) {
        let filteredModels = result.data.items;

        // Apply search filter
        if (searchTerm) {
          const term = searchTerm.toLowerCase();
          filteredModels = filteredModels.filter(
            (m) =>
              m.display_name.toLowerCase().includes(term) ||
              m.model_id.toLowerCase().includes(term) ||
              m.provider_type.toLowerCase().includes(term)
          );
        }

        setModels(filteredModels);
      } else {
        toast.error(result.error || "Failed to load models");
      }
    } catch (error) {
      toast.error("Failed to load models");
      console.error("Load models error:", error);
    } finally {
      setLoading(false);
    }
  }, [providerFilter, statusFilter, searchTerm]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleCreateModel = async () => {
    if (!formData.model_id || !formData.display_name) {
      toast.error("Please fill in all required fields");
      return;
    }

    setFormLoading(true);
    try {
      const result = await createVlmModel(formData);

      if (result.success) {
        toast.success("VLM model created successfully");
        setCreateDialogOpen(false);
        resetForm();
        loadModels();
      } else {
        toast.error(result.error || "Failed to create model");
      }
    } catch (error) {
      toast.error("Failed to create model");
      console.error("Create model error:", error);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdateModel = async () => {
    if (!editingModel) return;

    setFormLoading(true);
    try {
      const updateData: VlmModelUpdate = {
        display_name: formData.display_name,
        description: formData.description,
        max_tokens: formData.max_tokens,
        context_window: formData.context_window,
        temperature_default: formData.temperature_default,
        input_cost_per_1m: formData.input_cost_per_1m,
        output_cost_per_1m: formData.output_cost_per_1m,
        supports_vision: formData.supports_vision,
        supports_tools: formData.supports_tools,
        is_active: formData.is_active,
        sort_order: formData.sort_order,
      };

      const result = await updateVlmModel(editingModel.id, updateData);

      if (result.success) {
        toast.success("VLM model updated successfully");
        setEditDialogOpen(false);
        setEditingModel(null);
        resetForm();
        loadModels();
      } else {
        toast.error(result.error || "Failed to update model");
      }
    } catch (error) {
      toast.error("Failed to update model");
      console.error("Update model error:", error);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteModel = (model: VlmModel) => {
    setModelToDelete({
      id: model.id,
      display_name: model.display_name,
      model_id: model.model_id,
      provider_type: model.provider_type,
    });
    setDeleteDialogOpen(true);
  };

  const confirmDeleteModel = async () => {
    if (!modelToDelete) return;

    setIsDeleting(true);
    try {
      const result = await deleteVlmModel(modelToDelete.id);

      if (result.success) {
        toast.success("VLM model deleted successfully");
        setDeleteDialogOpen(false);
        setModelToDelete(null);
        loadModels();
      } else {
        toast.error(result.error || "Failed to delete model");
      }
    } catch (error) {
      toast.error("Failed to delete model");
      console.error("Delete model error:", error);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      const result = await setDefaultVlmModel(id);

      if (result.success) {
        toast.success("Model set as default");
        loadModels();
      } else {
        toast.error(result.error || "Failed to set default model");
      }
    } catch (error) {
      toast.error("Failed to set default model");
      console.error("Set default error:", error);
    }
  };

  const handleDeprecateModel = async () => {
    if (!deprecatingModel) return;

    setFormLoading(true);
    try {
      const result = await deprecateVlmModel(
        deprecatingModel.id,
        replacementModelId || undefined
      );

      if (result.success) {
        toast.success("Model marked as deprecated");
        setDeprecateDialogOpen(false);
        setDeprecatingModel(null);
        setReplacementModelId("");
        loadModels();
      } else {
        toast.error(result.error || "Failed to deprecate model");
      }
    } catch (error) {
      toast.error("Failed to deprecate model");
      console.error("Deprecate model error:", error);
    } finally {
      setFormLoading(false);
    }
  };

  const handleEditModel = (model: VlmModel) => {
    setEditingModel(model);
    setFormData({
      provider_type: model.provider_type,
      model_id: model.model_id,
      display_name: model.display_name,
      description: model.description || "",
      max_tokens: model.max_tokens,
      context_window: model.context_window || 200000,
      temperature_default: model.temperature_default,
      input_cost_per_1m: model.input_cost_per_1m,
      output_cost_per_1m: model.output_cost_per_1m,
      supports_vision: model.supports_vision,
      supports_tools: model.supports_tools,
      is_default: model.is_default,
      is_active: model.is_active,
      sort_order: model.sort_order,
    });
    setEditDialogOpen(true);
  };

  const resetForm = () => {
    setFormData({
      provider_type: "anthropic",
      model_id: "",
      display_name: "",
      description: "",
      max_tokens: 8192,
      context_window: 200000,
      temperature_default: 0.1,
      input_cost_per_1m: 3.0,
      output_cost_per_1m: 15.0,
      supports_vision: true,
      supports_tools: true,
      is_default: false,
      is_active: true,
      sort_order: 100,
    });
  };

  // Calculate stats
  const totalModels = models.length;
  const activeModels = models.filter((m) => m.is_active).length;
  const deprecatedModels = models.filter((m) => m.is_deprecated).length;
  const providerCount = new Set(models.map((m) => m.provider_type)).size;

  return (
    <div className="container mx-auto pb-6 max-w-7xl" style={{ backgroundColor: colors.offWhiteBg }}>
      {/* Header */}
      <div className="mb-12">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight" style={{ color: colors.primaryText }}>
              VLM <span className="font-normal">Models</span>
            </h1>
            <p className="text-sm" style={{ color: colors.secondaryText }}>
              Manage available VLM models for the platform
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={loadModels}
              disabled={loading}
              style={{ borderColor: colors.borderGray, color: colors.secondaryText }}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button style={{ backgroundColor: colors.primaryBrandBlue, color: colors.pureWhite }} className="hover:opacity-90">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Model
                </Button>
              </DialogTrigger>
              <ModelFormDialog
                title="Add VLM Model"
                description="Add a new model to the platform registry"
                formData={formData}
                onFormDataChange={setFormData}
                onSubmit={handleCreateModel}
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
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Models</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{totalModels}</p>
                  <p className="text-xs mt-1" style={{ color: colors.primaryBrandBlue }}>{activeModels} active</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                  <Cpu className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Providers</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{providerCount}</p>
                  <p className="text-xs mt-1" style={{ color: colors.success }}>with models</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.successBg }}>
                  <Settings className="h-6 w-6" style={{ color: colors.success }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Deprecated</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{deprecatedModels}</p>
                  <p className="text-xs mt-1" style={{ color: colors.warning }}>need migration</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.warningBg }}>
                  <AlertTriangle className="h-6 w-6" style={{ color: colors.warning }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Avg Cost</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    ${(models.reduce((sum, m) => sum + m.input_cost_per_1m, 0) / (models.length || 1)).toFixed(2)}
                  </p>
                  <p className="text-xs mt-1" style={{ color: colors.info }}>per 1M input tokens</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.infoBg }}>
                  <DollarSign className="h-6 w-6" style={{ color: colors.info }} strokeWidth={1.5} />
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
                  placeholder="Search models..."
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

              {/* Provider Filter */}
              <div className="w-full sm:w-[200px]">
                <Select value={providerFilter} onValueChange={setProviderFilter}>
                  <SelectTrigger className="h-10" style={{ borderColor: colors.borderGray }}>
                    <div className="flex items-center gap-2">
                      <Filter className="h-4 w-4" style={{ color: colors.secondaryText }} />
                      <SelectValue placeholder="Provider" />
                    </div>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Providers</SelectItem>
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
            </div>

            {/* Results Count */}
            <div className="mt-4 text-sm" style={{ color: colors.secondaryText }}>
              Showing <span className="font-medium" style={{ color: colors.deepNavy }}>{models.length}</span> models
            </div>
          </CardContent>
        </Card>

        {/* Models Table */}
        {loading ? (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardContent className="py-12">
              <div className="flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin" style={{ color: colors.primaryBrandBlue }} />
                <span className="ml-2" style={{ color: colors.secondaryText }}>Loading models...</span>
              </div>
            </CardContent>
          </Card>
        ) : models.length === 0 ? (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardContent className="py-12">
              <div className="text-center">
                <Cpu className="h-12 w-12 mx-auto mb-4" style={{ color: colors.disabledGray }} strokeWidth={1.5} />
                <h3 className="text-lg font-normal mb-2" style={{ color: colors.deepNavy }}>No Models Found</h3>
                <p className="text-sm" style={{ color: colors.secondaryText }}>
                  Add your first VLM model to get started.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card style={{ borderColor: colors.borderGray }}>
            <CardHeader style={{ backgroundColor: colors.offWhiteBg, borderBottom: `1px solid ${colors.borderGray}` }}>
              <CardTitle className="text-base" style={{ color: colors.deepNavy }}>VLM Models Registry</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border" style={{ borderColor: colors.borderGray }}>
                <Table>
                  <TableHeader>
                    <TableRow style={{ backgroundColor: colors.hoverGray }}>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Model</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Provider</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Pricing ($/1M)</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Capabilities</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Status</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider" style={{ color: colors.secondaryText }}>Order</TableHead>
                      <TableHead className="text-xs font-medium uppercase tracking-wider text-right" style={{ color: colors.secondaryText }}>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {models.map((model) => (
                      <ModelRow
                        key={model.id}
                        model={model}
                        onEdit={handleEditModel}
                        onDelete={handleDeleteModel}
                        onSetDefault={handleSetDefault}
                        onDeprecate={(m) => {
                          setDeprecatingModel(m);
                          setDeprecateDialogOpen(true);
                        }}
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
        <ModelFormDialog
          title="Edit VLM Model"
          description="Update model configuration"
          formData={formData}
          onFormDataChange={setFormData}
          onSubmit={handleUpdateModel}
          onCancel={() => {
            setEditDialogOpen(false);
            setEditingModel(null);
            resetForm();
          }}
          isLoading={formLoading}
          isEditing={true}
        />
      </Dialog>

      {/* Deprecate Dialog */}
      <Dialog open={deprecateDialogOpen} onOpenChange={setDeprecateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deprecate Model</DialogTitle>
            <DialogDescription>
              Mark this model as deprecated. Users will be notified to migrate to another model.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-orange-700">
                <strong>Model:</strong> {deprecatingModel?.display_name}
              </p>
              <p className="text-sm text-orange-700">
                <strong>ID:</strong> {deprecatingModel?.model_id}
              </p>
            </div>

            <div className="space-y-2">
              <Label>Replacement Model ID (Optional)</Label>
              <Input
                value={replacementModelId}
                onChange={(e) => setReplacementModelId(e.target.value)}
                placeholder="e.g., claude-sonnet-5-20260101"
              />
              <p className="text-xs text-[#6B7280]">
                Recommend a model for users to migrate to
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeprecateDialogOpen(false);
                setDeprecatingModel(null);
                setReplacementModelId("");
              }}
              disabled={formLoading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleDeprecateModel}
              disabled={formLoading}
              className="bg-orange-500 hover:bg-orange-600"
            >
              {formLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Deprecate Model
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="max-w-md">
          <AlertDialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="h-12 w-12 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="h-6 w-6 text-red-600" />
              </div>
              <AlertDialogTitle className="text-xl">Delete VLM Model</AlertDialogTitle>
            </div>
            <AlertDialogDescription asChild>
              <div className="text-base space-y-3 pt-2">
                <div>
                  Are you sure you want to delete <span className="font-semibold text-gray-900">{modelToDelete?.display_name}</span>?
                </div>
                <div className="text-sm space-y-1" style={{ color: colors.secondaryText }}>
                  <div><span className="font-medium">Model ID:</span> <span className="font-mono">{modelToDelete?.model_id}</span></div>
                  <div><span className="font-medium">Provider:</span> {PROVIDER_TYPES.find((p) => p.value === modelToDelete?.provider_type)?.label || modelToDelete?.provider_type}</div>
                </div>
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  This action cannot be undone. Any providers currently using this model will need to be reconfigured.
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel
              disabled={isDeleting}
              className="mt-0"
              onClick={() => {
                setModelToDelete(null);
              }}
            >
              Cancel
            </AlertDialogCancel>
            <Button
              onClick={confirmDeleteModel}
              disabled={isDeleting}
              variant="destructive"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Model
                </>
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// Model Table Row Component
function ModelRow({
  model,
  onEdit,
  onDelete,
  onSetDefault,
  onDeprecate,
}: {
  model: VlmModel;
  onEdit: (model: VlmModel) => void;
  onDelete: (model: VlmModel) => void;
  onSetDefault: (id: string) => void;
  onDeprecate: (model: VlmModel) => void;
}) {
  const getStatusBadge = () => {
    if (!model.is_active) {
      return (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.hoverGray, color: colors.secondaryText, borderColor: colors.borderGray }}>
          Inactive
        </div>
      );
    }
    if (model.is_deprecated) {
      return (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder }}>
          <AlertTriangle className="h-3 w-3" />
          Deprecated
        </div>
      );
    }
    if (model.is_default) {
      return (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.infoBg, color: colors.infoText, borderColor: colors.infoBorder }}>
          <Star className="h-3 w-3" />
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

  const getProviderLabel = (type: string) => {
    return PROVIDER_TYPES.find((p) => p.value === type)?.label || type;
  };

  return (
    <TableRow className="hover:bg-gray-50/50">
      <TableCell>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: colors.lightBlueTint }}>
            <Cpu className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} />
          </div>
          <div>
            <div className="font-medium flex items-center gap-2" style={{ color: colors.deepNavy }}>
              {model.display_name}
              {model.is_default && <Star className="h-4 w-4 text-yellow-500" fill="currentColor" />}
            </div>
            <div className="text-sm font-mono" style={{ color: colors.secondaryText }}>{model.model_id}</div>
            {model.description && (
              <div className="text-xs mt-1 max-w-xs truncate" style={{ color: colors.secondaryText }}>{model.description}</div>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
          style={{ backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: "#C7DBED" }}>
          {getProviderLabel(model.provider_type)}
        </div>
      </TableCell>
      <TableCell>
        <div className="text-sm" style={{ color: colors.deepNavy }}>
          <div>In: ${model.input_cost_per_1m}</div>
          <div style={{ color: colors.secondaryText }}>Out: ${model.output_cost_per_1m}</div>
        </div>
      </TableCell>
      <TableCell>
        <div className="flex gap-1">
          {model.supports_vision && (
            <div className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
              style={{ backgroundColor: colors.hoverGray, color: colors.secondaryText, borderColor: colors.borderGray }}>
              Vision
            </div>
          )}
          {model.supports_tools && (
            <div className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
              style={{ backgroundColor: colors.hoverGray, color: colors.secondaryText, borderColor: colors.borderGray }}>
              Tools
            </div>
          )}
        </div>
      </TableCell>
      <TableCell>{getStatusBadge()}</TableCell>
      <TableCell style={{ color: colors.deepNavy }}>{model.sort_order}</TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" style={{ borderColor: colors.borderGray, color: colors.secondaryText }}>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => onEdit(model)}>
              <Edit className="h-4 w-4 mr-2" />
              Edit Model
            </DropdownMenuItem>
            {!model.is_default && model.is_active && (
              <DropdownMenuItem onClick={() => onSetDefault(model.id)}>
                <Star className="h-4 w-4 mr-2" />
                Set as Default
              </DropdownMenuItem>
            )}
            {!model.is_deprecated && (
              <DropdownMenuItem onClick={() => onDeprecate(model)}>
                <AlertTriangle className="h-4 w-4 mr-2" />
                Mark Deprecated
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onDelete(model)} className="text-red-600">
              <Trash2 className="h-4 w-4 mr-2" />
              Delete Model
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}

// Model Form Dialog Component
function ModelFormDialog({
  title,
  description,
  formData,
  onFormDataChange,
  onSubmit,
  onCancel,
  isLoading,
  isEditing = false,
}: {
  title: string;
  description: string;
  formData: VlmModelCreate;
  onFormDataChange: (data: VlmModelCreate) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isLoading: boolean;
  isEditing?: boolean;
}) {
  const updateFormData = (updates: Partial<VlmModelCreate>) => {
    onFormDataChange({ ...formData, ...updates });
  };

  return (
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Provider Type *</Label>
            <Select
              value={formData.provider_type}
              onValueChange={(v) => updateFormData({ provider_type: v })}
              disabled={isEditing}
            >
              <SelectTrigger>
                <SelectValue />
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

          <div className="space-y-2">
            <Label>Model ID *</Label>
            <Input
              value={formData.model_id}
              onChange={(e) => updateFormData({ model_id: e.target.value })}
              placeholder="claude-sonnet-4-20250514"
              disabled={isEditing}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Display Name *</Label>
            <Input
              value={formData.display_name}
              onChange={(e) => updateFormData({ display_name: e.target.value })}
              placeholder="Claude Sonnet 4"
            />
          </div>

          <div className="space-y-2">
            <Label>Sort Order</Label>
            <Input
              type="number"
              value={formData.sort_order}
              onChange={(e) => updateFormData({ sort_order: parseInt(e.target.value) || 100 })}
              placeholder="100"
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Description</Label>
          <Textarea
            value={formData.description}
            onChange={(e) => updateFormData({ description: e.target.value })}
            placeholder="Brief description of the model capabilities..."
            rows={2}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Max Output Tokens</Label>
            <Input
              type="number"
              value={formData.max_tokens}
              onChange={(e) => updateFormData({ max_tokens: parseInt(e.target.value) || 8192 })}
            />
          </div>

          <div className="space-y-2">
            <Label>Context Window</Label>
            <Input
              type="number"
              value={formData.context_window}
              onChange={(e) => updateFormData({ context_window: parseInt(e.target.value) || 200000 })}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label>Default Temperature</Label>
            <Input
              type="number"
              step="0.1"
              value={formData.temperature_default}
              onChange={(e) => updateFormData({ temperature_default: parseFloat(e.target.value) || 0.1 })}
            />
          </div>

          <div className="space-y-2">
            <Label>Input Cost ($/1M)</Label>
            <Input
              type="number"
              step="0.01"
              value={formData.input_cost_per_1m}
              onChange={(e) => updateFormData({ input_cost_per_1m: parseFloat(e.target.value) || 0 })}
            />
          </div>

          <div className="space-y-2">
            <Label>Output Cost ($/1M)</Label>
            <Input
              type="number"
              step="0.01"
              value={formData.output_cost_per_1m}
              onChange={(e) => updateFormData({ output_cost_per_1m: parseFloat(e.target.value) || 0 })}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center space-x-2">
            <Switch
              id="supports_vision"
              checked={formData.supports_vision}
              onCheckedChange={(v) => updateFormData({ supports_vision: v })}
            />
            <Label htmlFor="supports_vision">Supports Vision</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Switch
              id="supports_tools"
              checked={formData.supports_tools}
              onCheckedChange={(v) => updateFormData({ supports_tools: v })}
            />
            <Label htmlFor="supports_tools">Supports Tools</Label>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Switch
            id="is_active"
            checked={formData.is_active}
            onCheckedChange={(v) => updateFormData({ is_active: v })}
          />
          <Label htmlFor="is_active">Active (available for selection)</Label>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={onSubmit}
          disabled={isLoading || !formData.model_id || !formData.display_name}
        >
          {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {isEditing ? "Update" : "Create"} Model
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
