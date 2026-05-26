'use client';

import { useState, useEffect, useTransition } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Brain,
  Plus,
  Trash2,
  Star,
  Loader2,
  DollarSign,
  Activity,
  Settings,
  TestTube,
  Shield,
  Info,
  AlertCircle,
  Calendar,
  TrendingUp,
  BarChart3,
  Zap,
  ExternalLink,
  ArrowUpCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { DateRange } from 'react-day-picker';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { format } from 'date-fns';
import {
  getVlmProviders,
  createVlmProvider,
  updateVlmProvider,
  deleteVlmProvider,
  setDefaultVlmProvider,
  testVlmProvider,
  getUsageStats,
  getUsageCosts,
  getProviderTypes,
  getVlmStatus,
  getPlatformQuota,
  type VlmProvider,
  type UsageStats,
  type ProviderTypeInfo,
  type PlatformFallbackInfo,
  type VLMCostResponse,
  type CostPeriod,
  type CostGroupBy,
  type PlatformQuota,
} from '@/lib/actions/settings';
import { dispatchVlmStatusChanged, PLATFORM_QUOTA_CHANGED_EVENT } from '@/components/dashboard/vlm-status-banner';

// Fallback provider types in case API call fails (Updated March 2026)
const FALLBACK_PROVIDER_TYPES: ProviderTypeInfo[] = [
  {
    type: 'anthropic',
    display_name: 'Anthropic Claude',
    default_model: 'claude-sonnet-4-5-20250929',
    default_max_tokens: 16384,
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    requires_endpoint: false,
    models: [
      { model_id: 'claude-sonnet-4-5-20250929', display_name: 'Claude Sonnet 4.5', max_tokens: 16384, is_default: true, is_deprecated: false, input_cost_per_1m: 3.0, output_cost_per_1m: 15.0 },
      { model_id: 'claude-sonnet-4-20250514', display_name: 'Claude Sonnet 4', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 3.0, output_cost_per_1m: 15.0 },
      { model_id: 'claude-opus-4-5-20251124', display_name: 'Claude Opus 4.5', max_tokens: 16384, is_default: false, is_deprecated: false, input_cost_per_1m: 15.0, output_cost_per_1m: 75.0 },
    ],
  },
  {
    type: 'openai',
    display_name: 'OpenAI',
    default_model: 'gpt-4.1',
    default_max_tokens: 8192,
    input_cost_per_1m: 2.0,
    output_cost_per_1m: 8.0,
    requires_endpoint: false,
    models: [
      { model_id: 'gpt-4.1', display_name: 'GPT-4.1', max_tokens: 8192, is_default: true, is_deprecated: false, input_cost_per_1m: 2.0, output_cost_per_1m: 8.0 },
      { model_id: 'gpt-4.1-mini', display_name: 'GPT-4.1 Mini', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 0.4, output_cost_per_1m: 1.6 },
      { model_id: 'gpt-4.1-nano', display_name: 'GPT-4.1 Nano', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 0.1, output_cost_per_1m: 0.4 },
      { model_id: 'o3', display_name: 'o3 (Reasoning)', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 10.0, output_cost_per_1m: 40.0 },
      { model_id: 'o4-mini', display_name: 'o4-mini (Reasoning)', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 1.1, output_cost_per_1m: 4.4 },
      { model_id: 'gpt-4o-2025-03-26', display_name: 'GPT-4o (March 2025)', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 2.5, output_cost_per_1m: 10.0 },
      { model_id: 'gpt-4o-mini', display_name: 'GPT-4o Mini', max_tokens: 4096, is_default: false, is_deprecated: false, input_cost_per_1m: 0.15, output_cost_per_1m: 0.6 },
      { model_id: 'gpt-4-turbo', display_name: 'GPT-4 Turbo', max_tokens: 4096, is_default: false, is_deprecated: true, replacement_model_id: 'gpt-4.1', input_cost_per_1m: 10.0, output_cost_per_1m: 30.0 },
    ],
  },
  {
    type: 'google',
    display_name: 'Google Gemini',
    default_model: 'gemini-2.5-pro',
    default_max_tokens: 1000000,
    input_cost_per_1m: 1.25,
    output_cost_per_1m: 5.0,
    requires_endpoint: false,
    models: [
      { model_id: 'gemini-2.5-pro', display_name: 'Gemini 2.5 Pro', max_tokens: 1000000, is_default: true, is_deprecated: false, input_cost_per_1m: 1.25, output_cost_per_1m: 5.0 },
      { model_id: 'gemini-2.0-flash', display_name: 'Gemini 2.0 Flash', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 0.075, output_cost_per_1m: 0.3 },
    ],
  },
  {
    type: 'azure_openai',
    display_name: 'Azure OpenAI',
    default_model: 'gpt-4.1',
    default_max_tokens: 8192,
    input_cost_per_1m: 2.0,
    output_cost_per_1m: 8.0,
    requires_endpoint: true,
    models: [
      { model_id: 'gpt-4.1', display_name: 'GPT-4.1 (Azure)', max_tokens: 8192, is_default: true, is_deprecated: false, input_cost_per_1m: 2.0, output_cost_per_1m: 8.0 },
      { model_id: 'gpt-4o-2025-03-26', display_name: 'GPT-4o (Azure, March 2025)', max_tokens: 8192, is_default: false, is_deprecated: false, input_cost_per_1m: 2.5, output_cost_per_1m: 10.0 },
    ],
  },
  {
    type: 'aws_bedrock',
    display_name: 'AWS Bedrock',
    default_model: 'anthropic.claude-sonnet-4-5-20250929-v1:0',
    default_max_tokens: 16384,
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    requires_endpoint: false,
    models: [
      { model_id: 'anthropic.claude-sonnet-4-5-20250929-v1:0', display_name: 'Claude Sonnet 4.5 (Bedrock)', max_tokens: 16384, is_default: true, is_deprecated: false, input_cost_per_1m: 3.0, output_cost_per_1m: 15.0 },
      { model_id: 'anthropic.claude-opus-4-5-20251124-v1:0', display_name: 'Claude Opus 4.5 (Bedrock)', max_tokens: 16384, is_default: false, is_deprecated: false, input_cost_per_1m: 15.0, output_cost_per_1m: 75.0 },
    ],
  },
];

/**
 * Formats a cost value as "$X.XX" with exactly 2 decimal places.
 * Handles null, undefined, and NaN gracefully by falling back to $0.00.
 */
function formatCost(value: number | null | undefined): string {
  const num = value ?? 0;
  return `$${Number.isFinite(num) ? num.toFixed(2) : '0.00'}`;
}

const PERIOD_PRESETS: { value: CostPeriod; label: string }[] = [
  { value: 'last_7_days', label: '7 Days' },
  { value: 'last_30_days', label: '30 Days' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'this_year', label: 'This Year' },
  { value: 'all_time', label: 'All Time' },
  { value: 'custom', label: 'Custom' },
];

const GROUP_BY_OPTIONS: { value: CostGroupBy; label: string }[] = [
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
];

/**
 * Formats a token count for display.
 * > 1M: "X.XXM", > 1K: "X.Xk", otherwise raw number.
 */
function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return value.toLocaleString();
}

/**
 * Formats a date string from the daily_breakdown for display
 * based on the current group_by setting.
 */
function formatBreakdownDate(dateStr: string, groupBy: CostGroupBy): string {
  const date = new Date(dateStr + 'T00:00:00');
  if (groupBy === 'month') {
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  }
  if (groupBy === 'week') {
    const weekEnd = new Date(date);
    weekEnd.setDate(weekEnd.getDate() + 6);
    const startStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const endStr = weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `${startStr} - ${endStr}`;
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function isValidCostPeriod(value: string | null): value is CostPeriod {
  return value !== null && [
    'last_7_days', 'last_30_days', 'this_month',
    'last_month', 'this_year', 'all_time', 'custom',
  ].includes(value);
}

function isValidCostGroupBy(value: string | null): value is CostGroupBy {
  return value !== null && ['day', 'week', 'month'].includes(value);
}

export function VlmProvidersSettings() {
  const router = useRouter();
  const [providers, setProviders] = useState<VlmProvider[]>([]);
  const [providerTypes, setProviderTypes] = useState<ProviderTypeInfo[]>(FALLBACK_PROVIDER_TYPES);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  const [platformFallback, setPlatformFallback] = useState<PlatformFallbackInfo | null>(null);
  const [quota, setQuota] = useState<PlatformQuota | null>(null);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingProvider, setDeletingProvider] = useState<VlmProvider | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [testingProviderId, setTestingProviderId] = useState<string | null>(null);
  const [newProvider, setNewProvider] = useState({
    provider_type: 'anthropic',
    name: '',
    api_key: '',
    model_name: 'claude-sonnet-4-5-20250929',
    monthly_budget: undefined as number | undefined,
    api_endpoint: '', // For Azure OpenAI
    aws_region: 'us-east-1', // For AWS Bedrock
    aws_access_key_id: '', // For AWS Bedrock
    aws_secret_access_key: '', // For AWS Bedrock
  });
  const [isCreating, setIsCreating] = useState(false);

  // Change model dialog state
  const [changeModelDialogOpen, setChangeModelDialogOpen] = useState(false);
  const [changeModelProvider, setChangeModelProvider] = useState<VlmProvider | null>(null);
  const [changeModelTarget, setChangeModelTarget] = useState<string>('');
  const [isChangingModel, setIsChangingModel] = useState(false);

  // Cost & Usage state
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [, startTransition] = useTransition();
  const [costData, setCostData] = useState<VLMCostResponse | null>(null);
  const [costPeriod, setCostPeriod] = useState<CostPeriod>(
    isValidCostPeriod(searchParams.get('cost_period'))
      ? (searchParams.get('cost_period') as CostPeriod)
      : 'this_month'
  );
  const [costGroupBy, setCostGroupBy] = useState<CostGroupBy>(
    isValidCostGroupBy(searchParams.get('cost_group_by'))
      ? (searchParams.get('cost_group_by') as CostGroupBy)
      : 'day'
  );
  const [customDateRange, setCustomDateRange] = useState<DateRange | undefined>(undefined);
  const [costLoading, setCostLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  // Refetch quota when another component signals it changed (e.g. extraction
  // blocked by platform limit) or when the user returns to this tab/window.
  useEffect(() => {
    const refetchQuota = () => {
      getPlatformQuota().then(q => { if (q !== null) setQuota(q); });
    };

    // Listen for cross-component quota change events
    window.addEventListener(PLATFORM_QUOTA_CHANGED_EVENT, refetchQuota);

    // Refetch when the page becomes visible again (tab switch / window focus)
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refetchQuota();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener(PLATFORM_QUOTA_CHANGED_EVENT, refetchQuota);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [providersData, statsData, providerTypesData, vlmStatus, quotaData] = await Promise.all([
        getVlmProviders(),
        getUsageStats(),
        getProviderTypes(),
        getVlmStatus(),
        getPlatformQuota(),
      ]);
      setProviders(providersData);
      setUsageStats(statsData);
      setQuota(quotaData);

      // Use fetched provider types or fall back to defaults
      if (providerTypesData && providerTypesData.length > 0) {
        setProviderTypes(providerTypesData);
        // Update newProvider with the first provider's default model
        const firstProvider = providerTypesData[0];
        if (firstProvider) {
          setNewProvider(prev => ({
            ...prev,
            provider_type: firstProvider.type,
            model_name: firstProvider.default_model || firstProvider.models[0]?.model_id || '',
          }));
        }
      }

      // Set platform fallback from VLM status API response
      if (vlmStatus?.platform_fallback) {
        setPlatformFallback(vlmStatus.platform_fallback);
      } else {
        setPlatformFallback(null);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load AI providers');
    } finally {
      setLoading(false);
    }
  };

  // Cost & Usage data fetching
  const updateCostUrlParams = (newPeriod: CostPeriod, newGroupBy: CostGroupBy) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('cost_period', newPeriod);
    params.set('cost_group_by', newGroupBy);
    startTransition(() => {
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    });
  };

  const fetchCostData = async (
    period: CostPeriod,
    groupBy: CostGroupBy,
    dateRange?: DateRange
  ) => {
    setCostLoading(true);
    try {
      let startDate: string | undefined;
      let endDate: string | undefined;
      if (period === 'custom' && dateRange?.from) {
        startDate = format(dateRange.from, 'yyyy-MM-dd');
        endDate = dateRange.to
          ? format(dateRange.to, 'yyyy-MM-dd')
          : startDate;
      }
      const data = await getUsageCosts(period, groupBy, startDate, endDate);
      setCostData(data);
    } catch (error) {
      console.error('Failed to fetch cost data:', error);
      setCostData(null);
    } finally {
      setCostLoading(false);
    }
  };

  // Fetch cost data on mount and when period/groupBy/dateRange changes
  useEffect(() => {
    // Skip custom period fetch if no date range is set yet
    if (costPeriod === 'custom' && !customDateRange?.from) return;
    fetchCostData(costPeriod, costGroupBy, customDateRange);
    updateCostUrlParams(costPeriod, costGroupBy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [costPeriod, costGroupBy, customDateRange]);

  const handleCreateProvider = async () => {
    // Client-side validation before submission
    if (!newProvider.name?.trim()) {
      toast.error('Provider name is required');
      return;
    }
    if (!newProvider.api_key?.trim()) {
      toast.error('API key is required');
      return;
    }
    if (newProvider.api_key.trim().length < 10) {
      toast.error('API key must be at least 10 characters');
      return;
    }

    setIsCreating(true);
    try {
      const selectedProviderType = providerTypes.find(p => p.type === newProvider.provider_type);
      const isFirstProvider = providers.length === 0;
      const requiresAwsConfig = selectedProviderType?.type === 'aws_bedrock';

      // Build config for AWS Bedrock
      const config: Record<string, unknown> = {};
      if (requiresAwsConfig) {
        config.aws_region = newProvider.aws_region;
        config.aws_access_key_id = newProvider.aws_access_key_id;
        config.aws_secret_access_key = newProvider.aws_secret_access_key;
      }

      const result = await createVlmProvider({
        provider_type: newProvider.provider_type,
        name: newProvider.name,
        api_key: newProvider.api_key,
        model_name: newProvider.model_name,
        api_endpoint: selectedProviderType?.requires_endpoint ? newProvider.api_endpoint : undefined,
        monthly_budget: newProvider.monthly_budget,
        config: Object.keys(config).length > 0 ? config : undefined,
      });
      
      if (result.success && result.data) {
        setProviders([result.data, ...providers]);
        setCreateDialogOpen(false);
        resetNewProviderForm();
        
        // Show appropriate success message
        if (isFirstProvider || result.data.is_default) {
          toast.success('AI provider added and set as default');
        } else {
          toast.success('AI provider added successfully');
        }
        
        // Notify other components that VLM status changed
        dispatchVlmStatusChanged();
        router.refresh();
        // Refresh quota since adding a provider makes org unlimited
        getPlatformQuota().then(q => setQuota(q));
      } else {
        toast.error(result.error || 'Failed to create provider');
      }
    } catch (error) {
      console.error('Failed to create provider:', error);
      toast.error(error instanceof Error ? error.message : 'An unexpected error occurred');
    } finally {
      setIsCreating(false);
    }
  };
  
  const resetNewProviderForm = () => {
    const firstProvider = providerTypes[0];
    setNewProvider({
      provider_type: firstProvider?.type || 'anthropic',
      name: '',
      api_key: '',
      model_name: firstProvider?.default_model || firstProvider?.models[0]?.model_id || 'claude-sonnet-4-5-20250929',
      monthly_budget: undefined,
      api_endpoint: '',
      aws_region: 'us-east-1',
      aws_access_key_id: '',
      aws_secret_access_key: '',
    });
  };

  const handleTestProvider = async (id: string) => {
    setTestingProviderId(id);
    try {
      const result = await testVlmProvider(id);
      if (result.success && result.data?.success) {
        toast.success(result.data.message || 'Connection successful!');
      } else {
        toast.error(result.data?.message || result.error || 'Connection failed');
      }
    } catch (error) {
      console.error('Failed to test provider:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to test connection');
    } finally {
      setTestingProviderId(null);
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      const result = await setDefaultVlmProvider(id);
      if (result.success) {
        setProviders(providers.map(p => ({
          ...p,
          is_default: p.id === id,
        })));
        toast.success('Default provider updated');
      } else {
        toast.error(result.error || 'Failed to set default');
      }
    } catch (error) {
      console.error('Failed to set default provider:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to set default provider');
    }
  };

  const handleDeleteProvider = (provider: VlmProvider) => {
    setDeletingProvider(provider);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteProvider = async () => {
    if (!deletingProvider) return;

    setIsDeleting(true);
    try {
      const result = await deleteVlmProvider(deletingProvider.id);
      if (result.success) {
        // If we deleted the default, backend will auto-set a new one
        // So we need to fetch fresh data
        if (deletingProvider.is_default && providers.length > 1) {
          await fetchData();
          toast.success('Provider deleted. A new default has been set automatically.');
        } else {
          setProviders(providers.filter(p => p.id !== deletingProvider.id));
          toast.success('Provider deleted');
        }
        setDeleteDialogOpen(false);
        setDeletingProvider(null);
        // Notify other components that VLM status changed
        dispatchVlmStatusChanged();
        router.refresh();
        // Refresh quota since removing provider may re-enable the limit
        getPlatformQuota().then(q => setQuota(q));
      } else {
        toast.error(result.error || 'Failed to delete provider');
      }
    } catch (error) {
      console.error('Failed to delete provider:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to delete provider');
    } finally {
      setIsDeleting(false);
    }
  };

  /**
   * Opens the change model dialog for a provider with a deprecated model.
   * Pre-selects the recommended replacement model if one is specified.
   */
  const handleOpenChangeModel = (provider: VlmProvider) => {
    const pt = providerTypes.find((t) => t.type === provider.provider_type);
    const currentModelInfo = pt?.models.find((m) => m.model_id === provider.model_name);
    // Pre-select the replacement model, or the provider type's default model
    const targetModel =
      currentModelInfo?.replacement_model_id ||
      pt?.default_model ||
      pt?.models.find((m) => !m.is_deprecated)?.model_id ||
      '';
    setChangeModelProvider(provider);
    setChangeModelTarget(targetModel);
    setChangeModelDialogOpen(true);
  };

  const confirmChangeModel = async () => {
    if (!changeModelProvider || !changeModelTarget) return;

    setIsChangingModel(true);
    try {
      const result = await updateVlmProvider(changeModelProvider.id, {
        model_name: changeModelTarget,
      });
      if (result.success && result.data) {
        setProviders(
          providers.map((p) =>
            p.id === changeModelProvider.id
              ? { ...p, model_name: result.data!.model_name }
              : p
          )
        );
        setChangeModelDialogOpen(false);
        setChangeModelProvider(null);
        setChangeModelTarget('');
        toast.success('Model updated successfully');
        router.refresh();
      } else {
        toast.error(result.error || 'Failed to update model');
      }
    } catch (error) {
      console.error('Failed to change model:', error);
      toast.error(
        error instanceof Error ? error.message : 'Failed to update model'
      );
    } finally {
      setIsChangingModel(false);
    }
  };

  const selectedProviderType = providerTypes.find(p => p.type === newProvider.provider_type);
  const requiresAwsConfig = selectedProviderType?.type === 'aws_bedrock';

  return (
    <div className="space-y-6">
      {/* Platform Quota Banner */}
      {quota && !quota.is_unlimited && (
        <PlatformQuotaBanner
          quota={quota}
          onAddProvider={() => setCreateDialogOpen(true)}
        />
      )}

      <Card className="border-slate-200">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2 text-slate-800">
              <Brain className="h-5 w-5 text-slate-600" />
              AI Providers
            </CardTitle>
            <CardDescription className="text-slate-500">
              Configure Vision-Language Model providers for extraction
            </CardDescription>
          </div>
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Provider
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Add AI Provider</DialogTitle>
                <DialogDescription>
                  Configure a new AI provider for leaflet extraction
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Select
                    value={newProvider.provider_type}
                    onValueChange={(v) => {
                      const provider = providerTypes.find(p => p.type === v);
                      setNewProvider({
                        ...newProvider,
                        provider_type: v,
                        model_name: provider?.default_model || provider?.models[0]?.model_id || '',
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {providerTypes.map((provider) => (
                        <SelectItem key={provider.type} value={provider.type}>
                          {provider.display_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="provider-name">Name</Label>
                  <Input
                    id="provider-name"
                    value={newProvider.name}
                    onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
                    placeholder="e.g., Production Claude"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    value={newProvider.api_key}
                    onChange={(e) => setNewProvider({ ...newProvider, api_key: e.target.value })}
                    placeholder="sk-ant-..."
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Select
                    value={newProvider.model_name}
                    onValueChange={(v) => setNewProvider({ ...newProvider, model_name: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedProviderType?.models.map((model) => (
                        <SelectItem key={model.model_id} value={model.model_id}>
                          {model.display_name}
                          {model.is_deprecated && ' (Deprecated)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {/* Deprecation warning when a deprecated model is selected */}
                  {(() => {
                    const selectedModel = selectedProviderType?.models.find(
                      (m) => m.model_id === newProvider.model_name
                    );
                    if (!selectedModel?.is_deprecated) return null;
                    const replacementModel = selectedModel.replacement_model_id
                      ? selectedProviderType?.models.find(
                          (m) => m.model_id === selectedModel.replacement_model_id
                        )
                      : null;
                    return (
                      <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
                        <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0 text-amber-600 dark:text-amber-400" />
                        <div>
                          <p className="font-medium">This model is deprecated</p>
                          <p className="mt-0.5 text-xs text-amber-700 dark:text-amber-300">
                            {replacementModel
                              ? `Consider switching to ${replacementModel.display_name} (${replacementModel.model_id}) for better performance and pricing.`
                              : selectedModel.replacement_model_id
                                ? `Recommended replacement: ${selectedModel.replacement_model_id}`
                                : 'This model may be removed in a future update. Consider using a newer model.'}
                          </p>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Azure OpenAI Endpoint */}
                {selectedProviderType?.requires_endpoint && (
                  <div className="space-y-2">
                    <Label htmlFor="endpoint">Azure Endpoint URL *</Label>
                    <Input
                      id="endpoint"
                      type="url"
                      value={newProvider.api_endpoint}
                      onChange={(e) => setNewProvider({
                        ...newProvider,
                        api_endpoint: e.target.value,
                      })}
                      placeholder="https://your-resource.openai.azure.com"
                    />
                    <p className="text-xs text-slate-500">
                      Your Azure OpenAI resource endpoint URL
                    </p>
                  </div>
                )}

                {/* AWS Bedrock Config */}
                {requiresAwsConfig && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="aws_region">AWS Region</Label>
                      <Select
                        value={newProvider.aws_region}
                        onValueChange={(v) => setNewProvider({ ...newProvider, aws_region: v })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="us-east-1">US East (N. Virginia)</SelectItem>
                          <SelectItem value="us-west-2">US West (Oregon)</SelectItem>
                          <SelectItem value="eu-west-1">EU (Ireland)</SelectItem>
                          <SelectItem value="ap-southeast-1">Asia Pacific (Singapore)</SelectItem>
                          <SelectItem value="ap-northeast-1">Asia Pacific (Tokyo)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="aws_access_key">AWS Access Key ID *</Label>
                      <Input
                        id="aws_access_key"
                        type="password"
                        value={newProvider.aws_access_key_id}
                        onChange={(e) => setNewProvider({
                          ...newProvider,
                          aws_access_key_id: e.target.value,
                        })}
                        placeholder="AKIA..."
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="aws_secret">AWS Secret Access Key *</Label>
                      <Input
                        id="aws_secret"
                        type="password"
                        value={newProvider.aws_secret_access_key}
                        onChange={(e) => setNewProvider({
                          ...newProvider,
                          aws_secret_access_key: e.target.value,
                        })}
                        placeholder="Your AWS secret key"
                      />
                    </div>
                  </>
                )}
                
                <div className="space-y-2">
                  <Label htmlFor="budget">Monthly Budget (USD, optional)</Label>
                  <Input
                    id="budget"
                    type="number"
                    value={newProvider.monthly_budget || ''}
                    onChange={(e) => setNewProvider({
                      ...newProvider,
                      monthly_budget: e.target.value ? parseFloat(e.target.value) : undefined,
                    })}
                    placeholder="e.g., 100"
                  />
                </div>
                
                {selectedProviderType && (
                  <div className="p-3 bg-slate-50 rounded-lg text-sm">
                    <div className="font-medium mb-1 text-slate-800">Pricing (per 1M tokens)</div>
                    {(() => {
                      const selectedModel = selectedProviderType.models.find(m => m.model_id === newProvider.model_name);
                      const inputCost = selectedModel?.input_cost_per_1m ?? selectedProviderType.input_cost_per_1m;
                      const outputCost = selectedModel?.output_cost_per_1m ?? selectedProviderType.output_cost_per_1m;
                      return (
                        <div className="grid grid-cols-2 gap-2 text-slate-600">
                          <div>Input: ${inputCost}</div>
                          <div>Output: ${outputCost}</div>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
              
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateProvider}
                  disabled={
                    isCreating ||
                    !newProvider.name ||
                    !newProvider.api_key ||
                    (selectedProviderType?.requires_endpoint && !newProvider.api_endpoint) ||
                    (requiresAwsConfig && (!newProvider.aws_access_key_id || !newProvider.aws_secret_access_key))
                  }
                >
                  {isCreating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    'Add Provider'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : providers.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              No AI providers configured. Add one to start extracting leaflets.
            </div>
          ) : (
            <div className="space-y-4">
              {providers.map((provider) => (
                <div
                  key={provider.id}
                  className={`p-4 border rounded-lg ${
                    provider.is_default
                      ? 'border-blue-200 bg-blue-50'
                      : provider.is_active
                      ? 'border-slate-200'
                      : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-slate-800">{provider.name}</h4>
                        {provider.is_default && (
                          <Badge className="bg-blue-500">
                            <Star className="h-3 w-3 mr-1" />
                            Default
                          </Badge>
                        )}
                        <Badge variant="outline">
                          {provider.provider_display_name}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-500">
                        <span>Model: <code className="bg-slate-100 px-1 rounded">{provider.model_name}</code></span>
                        {(() => {
                          const pt = providerTypes.find((t) => t.type === provider.provider_type);
                          const modelInfo = pt?.models.find((m) => m.model_id === provider.model_name);
                          if (modelInfo?.is_deprecated) {
                            const replacementModel = modelInfo.replacement_model_id
                              ? pt?.models.find((m) => m.model_id === modelInfo.replacement_model_id)
                              : null;
                            return (
                              <span className="inline-flex items-center gap-1.5">
                                <Badge className="bg-amber-100 text-amber-800 border-amber-300 hover:bg-amber-100 text-xs">
                                  <AlertCircle className="h-3 w-3 mr-1" />
                                  Deprecated
                                </Badge>
                                <button
                                  type="button"
                                  onClick={() => handleOpenChangeModel(provider)}
                                  className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
                                >
                                  <ArrowUpCircle className="h-3 w-3" />
                                  {replacementModel
                                    ? `Upgrade to ${replacementModel.display_name}`
                                    : 'Change Model'}
                                </button>
                              </span>
                            );
                          }
                          return null;
                        })()}
                        <span>Key: <code className="bg-slate-100 px-1 rounded">{provider.masked_api_key}</code></span>
                      </div>
                    </div>
                    
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleTestProvider(provider.id)}
                        disabled={testingProviderId === provider.id}
                      >
                        {testingProviderId === provider.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <TestTube className="h-4 w-4" />
                        )}
                      </Button>
                      {!provider.is_default && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSetDefault(provider.id)}
                        >
                          <Star className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDeleteProvider(provider)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-3 bg-white rounded-lg border border-slate-200">
                      <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
                        <Activity className="h-3 w-3" />
                        Total Requests
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {provider.total_requests.toLocaleString()}
                      </div>
                    </div>

                    <div className="p-3 bg-white rounded-lg border border-slate-200">
                      <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
                        <DollarSign className="h-3 w-3" />
                        Total Spent
                        <Tooltip>
                          <TooltipTrigger className="cursor-help inline-flex" aria-label="About provider cost">
                            <Info className="h-3.5 w-3.5 text-slate-400" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p>Costs recorded for this provider only. Does not include usage routed through the platform default provider.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {formatCost(provider.total_spent)}
                      </div>
                    </div>

                    <div className="p-3 bg-white rounded-lg border border-slate-200">
                      <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
                        <DollarSign className="h-3 w-3" />
                        This Month
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {formatCost(provider.current_month_spent)}
                        {provider.monthly_budget && (
                          <span className="text-sm font-normal text-slate-500">
                            {' '}/ {formatCost(provider.monthly_budget)}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="p-3 bg-white rounded-lg border border-slate-200">
                      <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
                        <Settings className="h-3 w-3" />
                        Total Tokens
                      </div>
                      <div className="text-lg font-bold text-slate-800">
                        {((provider.total_input_tokens + provider.total_output_tokens) / 1000000).toFixed(2)}M
                      </div>
                    </div>
                  </div>
                  
                  {provider.monthly_budget && (
                    <div className="mt-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-slate-500">Budget Usage</span>
                        <span className="font-medium text-slate-800">
                          {Math.round((provider.current_month_spent / provider.monthly_budget) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${
                            (provider.current_month_spent / provider.monthly_budget) > 0.9
                              ? 'bg-red-500'
                              : (provider.current_month_spent / provider.monthly_budget) > 0.7
                              ? 'bg-yellow-500'
                              : 'bg-green-500'
                          }`}
                          style={{
                            width: `${Math.min(100, (provider.current_month_spent / provider.monthly_budget) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Platform Fallback Provider */}
      <Card className="border-slate-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-slate-800">
            <Shield className="h-5 w-5 text-slate-600" />
            Platform Fallback
          </CardTitle>
          <CardDescription className="text-slate-500">
            System-managed provider used when your configured providers are unavailable or exceed budget limits
          </CardDescription>
        </CardHeader>
        <CardContent>
          {platformFallback ? (
            <div className="space-y-4">
              <div className="p-4 border rounded-lg bg-blue-50 border-blue-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="font-medium">{platformFallback.provider_name}</div>
                    <Badge variant="outline" className="bg-blue-100 text-blue-800">
                      System Managed
                    </Badge>
                    <Badge className={platformFallback.is_healthy ? "bg-green-500" : "bg-red-500"}>
                      {platformFallback.is_healthy ? "Healthy" : "Issues"}
                    </Badge>
                  </div>
                  {platformFallback.is_available ? (
                    <Badge variant="default" className="bg-blue-500">
                      <Shield className="h-3 w-3 mr-1" />
                      Available
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <AlertCircle className="h-3 w-3 mr-1" />
                      Unavailable
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div className="p-3 bg-white rounded border border-slate-200">
                    <div className="text-sm text-slate-500 mb-1">Model</div>
                    <div className="font-medium text-slate-800">{platformFallback.model_name}</div>
                  </div>
                  {platformFallback.last_used && (
                    <div className="p-3 bg-white rounded border border-slate-200">
                      <div className="text-sm text-slate-500 mb-1">Last Used</div>
                      <div className="font-medium text-slate-800">
                        {new Date(platformFallback.last_used).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                  )}
                  {platformFallback.usage_cost_current_month !== undefined && platformFallback.usage_cost_current_month !== null && (
                    <div className="p-3 bg-white rounded border border-slate-200">
                      <div className="flex items-center gap-1 text-sm text-slate-500 mb-1">
                        <span>Fallback Cost (This Month)</span>
                        <Tooltip>
                          <TooltipTrigger className="cursor-help inline-flex" aria-label="About fallback cost">
                            <Info className="h-3.5 w-3.5 text-slate-400" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p>Cost incurred via the platform&apos;s shared API key when your personal provider is unavailable.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="font-medium text-slate-800">{formatCost(platformFallback.usage_cost_current_month)}</div>
                    </div>
                  )}
                </div>

              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="p-3 bg-slate-50 rounded">
                  <div className="flex items-center gap-2 text-slate-600 mb-2">
                    <Shield className="h-4 w-4" />
                    <span className="font-medium">What is Platform Fallback?</span>
                  </div>
                  <div className="text-slate-700 text-xs space-y-1">
                    <p>• Automatic backup when your providers fail or exceed budgets</p>
                    <p>• Ensures uninterrupted leaflet processing</p>
                    <p>• Usage is tracked and billed separately</p>
                    <p>• Managed and maintained by our platform team</p>
                  </div>
                </div>

                <div className="p-3 bg-slate-50 rounded">
                  <div className="flex items-center gap-2 text-slate-600 mb-2">
                    <Settings className="h-4 w-4" />
                    <span className="font-medium">How does it work?</span>
                  </div>
                  <div className="text-slate-700 text-xs space-y-1">
                    <p>• Activates when all your providers are unavailable</p>
                    <p>• Triggers when monthly budgets are exceeded</p>
                    <p>• Uses enterprise-grade API keys with higher limits</p>
                    <p>• Automatically switches back when your providers recover</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <div className="font-medium mb-2 text-slate-800">No Platform Fallback Configured</div>
              <p className="text-sm">Contact your administrator to enable platform fallback protection.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage Summary from Leaflets */}
      {usageStats && (
        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-slate-800">
              <Activity className="h-5 w-5 text-slate-600" />
              Overall Usage Summary
            </CardTitle>
            <CardDescription className="text-slate-500">
              Aggregated statistics from all processed leaflets
            </CardDescription>
          </CardHeader>
          <CardContent>
            {(() => {
              // Compute consistent totals from provider records (single source of truth)
              const providerTotalSpent = providers.reduce((sum, p) => sum + (p.total_spent || 0), 0);
              const providerMonthSpent = providers.reduce((sum, p) => sum + (p.current_month_spent || 0), 0);

              // Prefer provider-derived values if they differ from usage stats by more than $0.01
              const displayTotalCost = Math.abs(providerTotalSpent - (usageStats.estimated_cost || 0)) > 0.01
                ? providerTotalSpent
                : usageStats.estimated_cost;
              const displayMonthCost = Math.abs(providerMonthSpent - (usageStats.this_month_cost || 0)) > 0.01
                ? providerMonthSpent
                : usageStats.this_month_cost;

              // Build authoritative provider breakdown from provider records,
              // then append any system/fallback entries from usage stats that aren't in the providers list
              const providerBreakdown = providers.map(p => ({
                name: p.name || p.provider_display_name,
                provider_type: p.provider_type,
                total_spent: p.total_spent || 0,
                total_tokens: (p.total_input_tokens || 0) + (p.total_output_tokens || 0),
              }));

              // Include system/fallback entries from usage stats that don't correspond to a user provider
              const providerIds = new Set(providers.map(p => p.provider_type));
              const systemEntries = (usageStats.provider_breakdown || [])
                .filter(entry => entry.provider_type === 'system' && !providerIds.has(entry.provider_type))
                .map(entry => ({
                  name: entry.name,
                  provider_type: entry.provider_type,
                  total_spent: entry.total_spent || 0,
                  total_tokens: entry.total_tokens || 0,
                }));
              const allBreakdown = [...providerBreakdown, ...systemEntries];

              return (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                      <div className="text-sm text-blue-600 dark:text-blue-400 mb-1">Total Leaflets</div>
                      <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                        {usageStats.total_leaflets.toLocaleString()}
                      </div>
                    </div>
                    <div className="p-4 bg-green-50 dark:bg-green-950/30 rounded-lg">
                      <div className="text-sm text-green-600 dark:text-green-400 mb-1">Total Products</div>
                      <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                        {usageStats.total_products.toLocaleString()}
                      </div>
                    </div>
                    <div className="p-4 bg-sky-50 dark:bg-sky-950/30 rounded-lg">
                      <div className="text-sm text-sky-600 dark:text-sky-400 mb-1">Total Tokens</div>
                      <div className="text-2xl font-bold text-sky-700 dark:text-sky-300">
                        {(usageStats.total_tokens / 1000000).toFixed(2)}M
                      </div>
                    </div>
                    <div className="p-4 bg-orange-50 dark:bg-orange-950/30 rounded-lg">
                      <div className="flex items-center gap-1 text-sm text-orange-600 dark:text-orange-400 mb-1">
                        Total Cost
                        <Tooltip>
                          <TooltipTrigger className="cursor-help inline-flex" aria-label="About total cost">
                            <Info className="h-3.5 w-3.5 text-orange-400" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p>Sum of costs across your configured providers. Does not include platform default provider usage — see Analytics for the complete view.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="text-2xl font-bold text-orange-700 dark:text-orange-300">
                        {formatCost(displayTotalCost)}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                      <div className="text-xs text-slate-500 mb-1">This Month Leaflets</div>
                      <div className="text-lg font-semibold text-slate-800">{usageStats.this_month_leaflets}</div>
                    </div>
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                      <div className="flex items-center gap-1 text-xs text-slate-500 mb-1">
                        Total Cost (This Month)
                        <Tooltip>
                          <TooltipTrigger className="cursor-help inline-flex" aria-label="About monthly cost">
                            <Info className="h-3 w-3 text-slate-400" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p>Combined cost from your configured providers this month. Platform default provider costs are tracked separately in Analytics.</p>
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <div className="text-lg font-semibold text-slate-800">{formatCost(displayMonthCost)}</div>
                    </div>
                    <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                      <div className="text-xs text-slate-500 mb-1">Avg Tokens/Page</div>
                      <div className="text-lg font-semibold text-slate-800">{usageStats.average_tokens_per_page.toLocaleString()}</div>
                    </div>
                  </div>

                  {allBreakdown.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-3 text-slate-800">Usage by Provider</h4>
                      <div className="space-y-2">
                        {allBreakdown.map((entry, idx) => (
                          <div
                            key={idx}
                            className={`p-3 rounded-lg border ${
                              entry.provider_type === 'system'
                                ? 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800'
                                : 'bg-white dark:bg-slate-800 border-slate-200'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-medium text-slate-800">{entry.name}</span>
                                {entry.provider_type === 'system' && (
                                  <Badge variant="outline" className="ml-2 text-xs">Fallback</Badge>
                                )}
                              </div>
                              <div className="text-right">
                                <span className="font-bold text-slate-800">{formatCost(entry.total_spent)}</span>
                                <span className="text-slate-500 text-sm ml-2">
                                  ({(entry.total_tokens / 1000).toFixed(1)}k tokens)
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {/* Cost & Usage (Date Range) */}
      <Card className="border-slate-200">
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <CardTitle className="text-base flex items-center gap-2 text-slate-800">
                <TrendingUp className="h-5 w-5 text-slate-600" />
                Cost &amp; Usage
                {costLoading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
              </CardTitle>
              <CardDescription className="text-slate-500">
                {costData?.period.label
                  ? `Showing data for: ${costData.period.label}`
                  : 'Detailed cost and usage breakdown by time period'}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Period Selector */}
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {PERIOD_PRESETS.map((preset) => (
                <Button
                  key={preset.value}
                  size="sm"
                  variant={costPeriod === preset.value ? 'default' : 'outline'}
                  onClick={() => setCostPeriod(preset.value)}
                  className="text-xs"
                >
                  {preset.label}
                </Button>
              ))}
            </div>

            {/* Custom Date Range Picker */}
            {costPeriod === 'custom' && (
              <DateRangePicker
                date={customDateRange}
                onDateChange={setCustomDateRange}
                placeholder="Select custom date range"
              />
            )}
          </div>

          {/* Cost Data Content — keep stale data visible during refetch */}
          <div className={cn(
            "transition-opacity duration-150",
            costLoading && costData ? "opacity-50 pointer-events-none" : ""
          )}>
            {!costData && costLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
              </div>
            ) : costData ? (
              <>
                {/* Summary Stats Grid */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-4 bg-blue-50 rounded-lg col-span-2 lg:col-span-1">
                    <div className="text-sm text-blue-600 mb-1">Total Cost</div>
                    <div className="text-2xl font-bold text-blue-700">
                      {formatCost(costData.summary.total_cost)}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Total Requests</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {costData.summary.total_requests.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Total Tokens</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {formatTokens(costData.summary.total_tokens)}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Leaflets Processed</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {costData.summary.leaflets_processed.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Pages Processed</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {costData.summary.pages_processed.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Products Extracted</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {costData.summary.products_extracted.toLocaleString()}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Avg Cost / Leaflet</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {formatCost(costData.summary.avg_cost_per_leaflet)}
                    </div>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <div className="text-xs text-slate-500 mb-1">Avg Cost / Request</div>
                    <div className="text-lg font-semibold text-slate-800">
                      {formatCost(costData.summary.avg_cost_per_request)}
                    </div>
                  </div>
                </div>

                {/* Provider Breakdown */}
                {costData.by_provider.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium mb-3 text-slate-800">Provider Breakdown</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="text-left py-2 px-3 text-slate-600">Provider</th>
                            <th className="text-right py-2 px-3 text-slate-600">Cost</th>
                            <th className="text-right py-2 px-3 text-slate-600">Requests</th>
                            <th className="text-right py-2 px-3 text-slate-600">Tokens</th>
                            <th className="text-right py-2 px-3 text-slate-600">% of Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {costData.by_provider.map((provider, idx) => (
                            <tr
                              key={provider.provider_id ?? idx}
                              className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
                            >
                              <td className="py-2 px-3 font-medium text-slate-800">
                                {provider.provider_name}
                                {provider.provider_type === 'system' && (
                                  <Badge variant="outline" className="ml-2 text-xs">Fallback</Badge>
                                )}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-800">
                                {formatCost(provider.cost)}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {provider.requests.toLocaleString()}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {formatTokens(provider.tokens)}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {provider.percentage_of_total.toFixed(1)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Time Series Breakdown */}
                {costData.daily_breakdown.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium text-slate-800 flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-slate-500" />
                        Time Breakdown
                      </h4>
                      <div className="flex gap-1">
                        {GROUP_BY_OPTIONS.map((option) => (
                          <Button
                            key={option.value}
                            size="sm"
                            variant={costGroupBy === option.value ? 'default' : 'outline'}
                            onClick={() => setCostGroupBy(option.value)}
                            className="text-xs h-7 px-2"
                          >
                            {option.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="text-left py-2 px-3 text-slate-600">Date</th>
                            <th className="text-right py-2 px-3 text-slate-600">Cost</th>
                            <th className="text-right py-2 px-3 text-slate-600">Requests</th>
                            <th className="text-right py-2 px-3 text-slate-600">Tokens</th>
                            <th className="text-right py-2 px-3 text-slate-600">Leaflets</th>
                          </tr>
                        </thead>
                        <tbody>
                          {costData.daily_breakdown.map((point, idx) => (
                            <tr
                              key={point.date}
                              className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
                            >
                              <td className="py-2 px-3 text-slate-800">
                                {formatBreakdownDate(point.date, costGroupBy)}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-800">
                                {formatCost(point.cost)}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {point.requests.toLocaleString()}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {formatTokens(point.tokens)}
                              </td>
                              <td className="py-2 px-3 text-right text-slate-600">
                                {point.leaflets.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <BarChart3 className="h-10 w-10 mx-auto mb-3 opacity-40" />
                <p className="text-sm">No cost data available for this period.</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Provider Comparison */}
      <Card className="border-slate-200" data-provider-comparison>
        <CardHeader>
          <CardTitle className="text-base text-slate-800">Provider Comparison</CardTitle>
          <CardDescription className="text-slate-500">
            Compare pricing and capabilities across providers
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2 px-3 text-slate-600">Provider</th>
                  <th className="text-left py-2 px-3 text-slate-600">Models</th>
                  <th className="text-right py-2 px-3 text-slate-600">Input ($/1M)</th>
                  <th className="text-right py-2 px-3 text-slate-600">Output ($/1M)</th>
                </tr>
              </thead>
              <tbody>
                {providerTypes.map((provider) => (
                  <tr key={provider.type} className="border-b border-slate-100">
                    <td className="py-2 px-3 font-medium text-slate-800">{provider.display_name}</td>
                    <td className="py-2 px-3 text-slate-500">
                      {provider.models.map(m => m.display_name).join(', ')}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-800">${provider.input_cost_per_1m}</td>
                    <td className="py-2 px-3 text-right text-slate-800">${provider.output_cost_per_1m}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Change Model Dialog */}
      <Dialog open={changeModelDialogOpen} onOpenChange={(open) => {
        if (!isChangingModel) {
          setChangeModelDialogOpen(open);
          if (!open) {
            setChangeModelProvider(null);
            setChangeModelTarget('');
          }
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-slate-800">
              <ArrowUpCircle className="h-5 w-5 text-blue-600" />
              Change Model
            </DialogTitle>
            <DialogDescription className="pt-2">
              Update the model for this AI provider. Your API key and usage history will be preserved.
            </DialogDescription>
          </DialogHeader>

          {changeModelProvider && (() => {
            const pt = providerTypes.find((t) => t.type === changeModelProvider.provider_type);
            const currentModelInfo = pt?.models.find((m) => m.model_id === changeModelProvider.model_name);
            const targetModelInfo = pt?.models.find((m) => m.model_id === changeModelTarget);
            const availableModels = pt?.models.filter((m) => !m.is_deprecated) || [];

            return (
              <div className="space-y-4">
                {/* Current model info */}
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <div className="text-xs font-medium text-amber-800 mb-1">Current Model (Deprecated)</div>
                  <div className="text-sm text-amber-900 font-medium">
                    {currentModelInfo?.display_name || changeModelProvider.model_name}
                  </div>
                  <div className="text-xs text-amber-700 mt-1">
                    Pricing: ${currentModelInfo?.input_cost_per_1m ?? '?'} input / ${currentModelInfo?.output_cost_per_1m ?? '?'} output per 1M tokens
                  </div>
                </div>

                {/* Model selector */}
                {availableModels.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No supported replacement models found for this provider type.
                  </p>
                ) : (
                  <div className="space-y-2">
                    <Label>New Model</Label>
                    <Select
                      value={changeModelTarget}
                      onValueChange={setChangeModelTarget}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select a model" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableModels.map((model) => (
                          <SelectItem key={model.model_id} value={model.model_id}>
                            {model.display_name}
                            {model.model_id === currentModelInfo?.replacement_model_id && ' (Recommended)'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {/* New model pricing preview */}
                {targetModelInfo && (
                  <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="text-xs font-medium text-blue-800 mb-1">New Model</div>
                    <div className="text-sm text-blue-900 font-medium">
                      {targetModelInfo.display_name}
                    </div>
                    <div className="text-xs text-blue-700 mt-1">
                      Pricing: ${targetModelInfo.input_cost_per_1m} input / ${targetModelInfo.output_cost_per_1m} output per 1M tokens
                    </div>
                    {currentModelInfo && (
                      <div className="text-xs text-blue-600 mt-1">
                        {targetModelInfo.input_cost_per_1m < currentModelInfo.input_cost_per_1m
                          ? `Saves ~$${(currentModelInfo.input_cost_per_1m - targetModelInfo.input_cost_per_1m).toFixed(2)}/1M input tokens`
                          : targetModelInfo.input_cost_per_1m > currentModelInfo.input_cost_per_1m
                          ? `Costs ~$${(targetModelInfo.input_cost_per_1m - currentModelInfo.input_cost_per_1m).toFixed(2)}/1M input tokens more`
                          : 'Same input pricing'}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setChangeModelDialogOpen(false);
                setChangeModelProvider(null);
                setChangeModelTarget('');
              }}
              disabled={isChangingModel}
            >
              Cancel
            </Button>
            <Button
              onClick={confirmChangeModel}
              disabled={isChangingModel || !changeModelTarget || changeModelTarget === changeModelProvider?.model_name}
            >
              {isChangingModel ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                <>
                  <ArrowUpCircle className="h-4 w-4 mr-2" />
                  Update Model
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!isDeleting) {
          setDeleteDialogOpen(open);
          if (!open) setDeletingProvider(null);
        }
      }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertCircle className="h-5 w-5" />
              Delete AI Provider
            </DialogTitle>
            <DialogDescription className="pt-2">
              Are you sure you want to delete this AI provider? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          {deletingProvider && (
            <div className="my-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Name:</span>
                  <span className="text-sm font-medium text-slate-800">{deletingProvider.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Type:</span>
                  <Badge variant="outline" className="bg-blue-50 text-blue-700">
                    {deletingProvider.provider_display_name}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Model:</span>
                  <span className="text-sm text-slate-700">{deletingProvider.model_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Total Requests:</span>
                  <span className="text-sm text-slate-700">{deletingProvider.total_requests.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-slate-500">Total Spent:</span>
                  <span className="text-sm text-slate-700">{formatCost(deletingProvider.total_spent)}</span>
                </div>
              </div>
            </div>
          )}

          {deletingProvider?.is_default && providers.length > 1 && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-amber-800">
                This is your default provider. Another provider will be automatically set as default after deletion.
              </p>
            </div>
          )}

          {deletingProvider && providers.length === 1 && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-amber-800">
                This is your only AI provider. After deletion, the platform fallback provider will be used for extractions.
              </p>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false);
                setDeletingProvider(null);
              }}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDeleteProvider}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700"
            >
              {isDeleting ? (
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

// ============== PLATFORM QUOTA BANNER ==============

interface PlatformQuotaBannerProps {
  quota: PlatformQuota;
  onAddProvider: () => void;
}

function PlatformQuotaBanner({ quota, onAddProvider }: PlatformQuotaBannerProps) {
  const remaining = quota.remaining ?? 0;

  // Limit reached: remaining === 0
  if (remaining === 0) {
    return (
      <Card className="border-red-300 bg-red-50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              <AlertCircle className="h-5 w-5 text-red-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-red-800 text-sm">
                Platform AI limit reached ({quota.used}/{quota.limit} used)
              </h3>
              <p className="text-sm text-red-700 mt-1">
                You must add your own AI provider to continue extracting leaflets.
              </p>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <Button
                  size="sm"
                  onClick={onAddProvider}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  <Plus className="h-4 w-4 mr-1.5" />
                  Add AI Provider
                </Button>
                <a
                  href="#provider-comparison"
                  onClick={(e) => {
                    e.preventDefault();
                    document.querySelector('[data-provider-comparison]')?.scrollIntoView({ behavior: 'smooth' });
                  }}
                  className="inline-flex items-center gap-1 text-sm text-red-700 hover:text-red-900 font-medium"
                >
                  Compare providers
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Low remaining: 1-2 left
  if (remaining <= 2) {
    return (
      <Card className="border-amber-300 bg-amber-50">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              <AlertCircle className="h-5 w-5 text-amber-600" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-amber-800 text-sm">
                Only {remaining} free extraction{remaining === 1 ? '' : 's'} left!
              </h3>
              <p className="text-sm text-amber-700 mt-1">
                Add your own AI provider to continue extracting after the limit.
              </p>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onAddProvider}
                  className="border-amber-600 text-amber-800 hover:bg-amber-100"
                >
                  <Plus className="h-4 w-4 mr-1.5" />
                  Add AI Provider
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Plenty remaining: info banner
  return (
    <Card className="border-blue-200 bg-blue-50">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <Zap className="h-5 w-5 text-blue-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-blue-800 text-sm">
              Platform AI: {quota.used}/{quota.limit} free extractions used. {remaining} remaining.
            </h3>
            <p className="text-sm text-blue-700 mt-0.5">
              Add your own AI provider for unlimited extractions.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}