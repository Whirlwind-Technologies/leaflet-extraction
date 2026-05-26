'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import {
  CheckCircle,
  Clock,
  FileText,
  Package,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  Calendar as CalendarIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { format, subDays, startOfMonth, endOfMonth, subMonths } from 'date-fns';
import { DateRange } from 'react-day-picker';
import {
  getAnalyticsSummary,
  type AnalyticsSummary,
} from '@/lib/actions/analytics';

// ---------------------------------------------------------------------------
// Date-range preset definitions
// ---------------------------------------------------------------------------

type PresetKey =
  | 'last_7_days'
  | 'last_30_days'
  | 'this_month'
  | 'last_month'
  | 'all_time';

interface DatePreset {
  key: PresetKey;
  label: string;
  getRange: () => { startDate: string | undefined; endDate: string | undefined };
}

function toISODate(d: Date): string {
  return format(d, 'yyyy-MM-dd');
}

const DATE_PRESETS: DatePreset[] = [
  {
    key: 'all_time',
    label: 'All Time',
    getRange: () => ({ startDate: undefined, endDate: undefined }),
  },
  {
    key: 'last_7_days',
    label: 'Last 7 Days',
    getRange: () => ({
      startDate: toISODate(subDays(new Date(), 7)),
      endDate: toISODate(new Date()),
    }),
  },
  {
    key: 'last_30_days',
    label: 'Last 30 Days',
    getRange: () => ({
      startDate: toISODate(subDays(new Date(), 30)),
      endDate: toISODate(new Date()),
    }),
  },
  {
    key: 'this_month',
    label: 'This Month',
    getRange: () => ({
      startDate: toISODate(startOfMonth(new Date())),
      endDate: toISODate(new Date()),
    }),
  },
  {
    key: 'last_month',
    label: 'Last Month',
    getRange: () => {
      const prev = subMonths(new Date(), 1);
      return {
        startDate: toISODate(startOfMonth(prev)),
        endDate: toISODate(endOfMonth(prev)),
      };
    },
  },
];

// ---------------------------------------------------------------------------
// Relative-time helper
// ---------------------------------------------------------------------------

function relativeTime(date: Date): string {
  const now = new Date();
  const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diffSec < 10) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  return `${diffHour}h ago`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AnalyticsContent() {
  // Data state
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Date range state
  const [activePreset, setActivePreset] = useState<PresetKey>('all_time');
  const [customRange, setCustomRange] = useState<DateRange | undefined>(undefined);
  const [calendarOpen, setCalendarOpen] = useState(false);

  // Refresh state
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [relativeLabel, setRelativeLabel] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const autoRefreshRef = useRef(autoRefresh);
  autoRefreshRef.current = autoRefresh;

  // ---------------------------------------------------------------------------
  // Fetch data
  // ---------------------------------------------------------------------------

  const fetchData = useCallback(async (presetKey?: PresetKey, range?: DateRange) => {
    const preset = presetKey ?? activePreset;
    setIsLoading(true);
    setError(null);

    let startDate: string | undefined;
    let endDate: string | undefined;

    if (preset === 'all_time') {
      // no date params
    } else if (range?.from) {
      // custom range from calendar (when called with explicit range arg)
      startDate = toISODate(range.from);
      endDate = range.to ? toISODate(range.to) : toISODate(range.from);
    } else {
      // built-in preset
      const found = DATE_PRESETS.find((p) => p.key === preset);
      if (found) {
        const r = found.getRange();
        startDate = r.startDate;
        endDate = r.endDate;
      }
    }

    try {
      const data = await getAnalyticsSummary({ startDate, endDate });
      if (data) {
        setSummary(data);
        setLastUpdated(new Date());
      } else {
        setError('Failed to load analytics. Please try again.');
      }
    } catch {
      setError('Failed to load analytics. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [activePreset]);

  // Initial load
  useEffect(() => {
    fetchData('all_time');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // Preset button handler
  // ---------------------------------------------------------------------------

  const handlePresetChange = useCallback(
    (key: PresetKey) => {
      setActivePreset(key);
      setCustomRange(undefined);
      fetchData(key);
    },
    [fetchData]
  );

  // ---------------------------------------------------------------------------
  // Custom calendar handler
  // ---------------------------------------------------------------------------

  const handleCustomDateChange = useCallback(
    (range: DateRange | undefined) => {
      setCustomRange(range);
      if (range?.from && range?.to) {
        setActivePreset('all_time'); // deselect presets visually — we override below
        setCalendarOpen(false);
        // We do NOT use a preset key; instead compute directly from range
        setIsLoading(true);
        setError(null);
        const startDate = toISODate(range.from);
        const endDate = toISODate(range.to);
        getAnalyticsSummary({ startDate, endDate })
          .then((data) => {
            if (data) {
              setSummary(data);
              setLastUpdated(new Date());
            } else {
              setError('Failed to load analytics. Please try again.');
            }
          })
          .catch(() => {
            setError('Failed to load analytics. Please try again.');
          })
          .finally(() => {
            setIsLoading(false);
          });
      }
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Refresh handler
  // ---------------------------------------------------------------------------

  const handleRefresh = useCallback(() => {
    if (customRange?.from && customRange?.to) {
      setIsLoading(true);
      setError(null);
      const startDate = toISODate(customRange.from);
      const endDate = toISODate(customRange.to);
      getAnalyticsSummary({ startDate, endDate })
        .then((data) => {
          if (data) {
            setSummary(data);
            setLastUpdated(new Date());
          } else {
            setError('Failed to load analytics. Please try again.');
          }
        })
        .catch(() => {
          setError('Failed to load analytics. Please try again.');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      fetchData(activePreset);
    }
  }, [customRange, activePreset, fetchData]);

  // ---------------------------------------------------------------------------
  // Relative time ticker (every 30s)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    function tick() {
      if (lastUpdated) {
        setRelativeLabel(relativeTime(lastUpdated));
      }
    }
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [lastUpdated]);

  // ---------------------------------------------------------------------------
  // Auto-refresh (60s)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      if (autoRefreshRef.current) {
        handleRefresh();
      }
    }, 60_000);
    return () => clearInterval(id);
  }, [autoRefresh, handleRefresh]);

  // ---------------------------------------------------------------------------
  // Derive display label for custom range
  // ---------------------------------------------------------------------------

  const customRangeLabel =
    customRange?.from && customRange?.to
      ? `${format(customRange.from, 'MMM d, yyyy')} - ${format(customRange.to, 'MMM d, yyyy')}`
      : null;

  const isCustomActive = !!(customRange?.from && customRange?.to);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Top toolbar: date range presets + custom picker + refresh */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        {/* Left: presets + custom picker */}
        <div className="flex flex-wrap items-center gap-2">
          {DATE_PRESETS.map((preset) => (
            <Button
              key={preset.key}
              variant={activePreset === preset.key && !isCustomActive ? 'default' : 'outline'}
              size="sm"
              onClick={() => handlePresetChange(preset.key)}
              className={cn(
                'text-xs',
                activePreset === preset.key && !isCustomActive
                  ? ''
                  : 'text-slate-600'
              )}
            >
              {preset.label}
            </Button>
          ))}

          {/* Custom date picker */}
          <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
            <PopoverTrigger asChild>
              <Button
                variant={isCustomActive ? 'default' : 'outline'}
                size="sm"
                className={cn(
                  'text-xs gap-1.5',
                  isCustomActive ? '' : 'text-slate-600'
                )}
              >
                <CalendarIcon className="h-3.5 w-3.5" />
                {customRangeLabel ?? 'Custom'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                initialFocus
                mode="range"
                defaultMonth={customRange?.from ?? new Date()}
                selected={customRange}
                onSelect={handleCustomDateChange}
                numberOfMonths={2}
                disabled={{ after: new Date() }}
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* Right: last-updated + auto-refresh + refresh button */}
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-slate-400 whitespace-nowrap">
              Updated {relativeLabel}
            </span>
          )}

          <button
            type="button"
            onClick={() => setAutoRefresh((prev) => !prev)}
            className={cn(
              'text-xs px-2 py-1 rounded-md border transition-colors whitespace-nowrap',
              autoRefresh
                ? 'bg-blue-50 border-blue-200 text-blue-600'
                : 'bg-white border-slate-200 text-slate-400 hover:text-slate-600 hover:border-slate-300'
            )}
            title={autoRefresh ? 'Auto-refresh is on (every 60s)' : 'Enable auto-refresh'}
          >
            Auto
          </button>

          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh data"
          >
            <RefreshCw
              className={cn('h-4 w-4', isLoading && 'animate-spin')}
            />
            <span className="sr-only">Refresh analytics data</span>
          </Button>
        </div>
      </div>

      {/* Error state */}
      {error && !summary && (
        <Card className="border-slate-200">
          <CardContent className="p-6 text-center text-slate-500">
            {error}
            <div className="mt-3">
              <Button variant="outline" size="sm" onClick={handleRefresh}>
                Try Again
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading skeleton (initial load only) */}
      {isLoading && !summary && <AnalyticsContentSkeleton />}

      {/* Data display (stale-while-revalidate: dim during refetch) */}
      {summary && (
        <div
          className={cn(
            'transition-opacity duration-200',
            isLoading ? 'opacity-50 pointer-events-none' : ''
          )}
        >
          <AnalyticsCards summary={summary} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Extracted render component for the analytics cards
// ---------------------------------------------------------------------------

function AnalyticsCards({ summary }: { summary: AnalyticsSummary }) {
  const {
    total_products: totalProducts,
    auto_approved: autoApproved,
    approved: manuallyApproved,
    pending,
    rejected,
    needs_correction: needsCorrection,
    total_approved: totalApproved,
    total_awaiting_review: totalAwaiting,
    auto_approval_rate: autoApprovalRate,
    avg_confidence: avgConfidence,
    validation_pass_rate: validationPassRate,
    high_priority_count: highPriorityCount,
    total_leaflets: totalLeaflets,
    leaflets_completed: completedLeaflets,
    leaflets_by_status: leafletsByStatus,
  } = summary;

  const statusCounts: Record<
    string,
    { count: number; label: string; color: string }
  > = {
    auto_approved: {
      count: autoApproved,
      label: 'Auto-Approved',
      color: 'bg-emerald-600',
    },
    approved: {
      count: manuallyApproved,
      label: 'Manually Approved',
      color: 'bg-emerald-400',
    },
    pending: {
      count: pending,
      label: 'Pending',
      color: 'bg-amber-500',
    },
    needs_correction: {
      count: needsCorrection,
      label: 'Needs Correction',
      color: 'bg-orange-500',
    },
    rejected: {
      count: rejected,
      label: 'Rejected',
      color: 'bg-red-500',
    },
  };

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-blue-50">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-3xl font-semibold text-slate-800">
                  {totalLeaflets}
                </p>
                <p className="text-sm font-light text-slate-500">
                  Total Leaflets
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-emerald-50">
                <Package className="h-6 w-6 text-emerald-600" />
              </div>
              <div>
                <p className="text-3xl font-semibold text-slate-800">
                  {totalProducts}
                </p>
                <p className="text-sm font-light text-slate-500">
                  Total Products
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-amber-50">
                <Clock className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-3xl font-semibold text-slate-800">
                  {totalAwaiting}
                </p>
                <p className="text-sm font-light text-slate-500">
                  Awaiting Review
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-teal-50">
                <ShieldCheck className="h-6 w-6 text-teal-600" />
              </div>
              <div>
                <p className="text-3xl font-semibold text-slate-800">
                  {autoApprovalRate.toFixed(1)}%
                </p>
                <p className="text-sm font-light text-slate-500">
                  Auto-Approval Rate
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Review Status Distribution + Quality Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="text-base text-slate-800">
              Review Status Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(statusCounts).map(
                ([status, { count, label, color }]) => {
                  const percentage =
                    totalProducts > 0
                      ? (count / totalProducts) * 100
                      : 0;

                  return (
                    <div key={status}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-light text-slate-800">
                          {label}
                        </span>
                        <span className="font-semibold text-slate-800">
                          {count} ({percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-3 rounded-full overflow-hidden bg-slate-100">
                        <div
                          className={`h-full transition-all ${color}`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="text-base text-slate-800">
              Quality Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="flex items-center gap-2 font-light text-slate-800">
                    <TrendingUp
                      className="h-4 w-4 text-blue-600"
                      strokeWidth={1.5}
                    />
                    Average Confidence
                  </span>
                  <span className="font-semibold text-lg text-slate-800">
                    {avgConfidence.toFixed(1)}%
                  </span>
                </div>
                <div className="h-3 rounded-full overflow-hidden bg-slate-100">
                  <div
                    className="h-full transition-all bg-blue-500"
                    style={{ width: `${avgConfidence}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="flex items-center gap-2 font-light text-slate-800">
                    <CheckCircle
                      className="h-4 w-4 text-emerald-600"
                      strokeWidth={1.5}
                    />
                    Validation Pass Rate
                  </span>
                  <span className="font-semibold text-lg text-slate-800">
                    {validationPassRate.toFixed(1)}%
                  </span>
                </div>
                <div className="h-3 rounded-full overflow-hidden bg-slate-100">
                  <div
                    className="h-full transition-all bg-emerald-500"
                    style={{ width: `${validationPassRate}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="flex items-center gap-2 font-light text-slate-800">
                    <AlertTriangle
                      className="h-4 w-4 text-amber-600"
                      strokeWidth={1.5}
                    />
                    High Priority Items
                  </span>
                  <span className="font-semibold text-lg text-slate-800">
                    {highPriorityCount}
                  </span>
                </div>
                <p className="text-xs font-light text-slate-500">
                  Products with priority score &ge; 70
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Leaflet Status */}
      <Card className="border-slate-200">
        <CardHeader>
          <CardTitle className="text-base text-slate-800">
            Leaflet Processing Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {(
              [
                'pending',
                'processing',
                'extracting',
                'reviewing',
                'completed',
              ] as const
            ).map((status) => {
              const count = leafletsByStatus[status] ?? 0;
              const statusStyles: Record<string, string> = {
                pending: 'bg-slate-100 text-slate-600',
                processing: 'bg-blue-50 text-blue-600',
                extracting: 'bg-sky-50 text-sky-600',
                reviewing: 'bg-amber-50 text-amber-600',
                completed: 'bg-emerald-50 text-emerald-600',
              };

              return (
                <div
                  key={status}
                  className={`p-4 rounded-lg ${statusStyles[status] || 'bg-slate-100 text-slate-600'}`}
                >
                  <p className="text-2xl font-semibold">{count}</p>
                  <p className="text-sm font-light capitalize">{status}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-4xl font-semibold text-emerald-600">
                {totalApproved}
              </p>
              <p className="text-sm font-light mt-1 text-slate-500">
                Approved Products
              </p>
              <p className="text-xs font-light mt-2 text-slate-500">
                {autoApproved} auto + {manuallyApproved} manual
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-4xl font-semibold text-amber-600">
                {totalAwaiting}
              </p>
              <p className="text-sm font-light mt-1 text-slate-500">
                Awaiting Review
              </p>
              <p className="text-xs font-light mt-2 text-slate-500">
                {pending} pending + {needsCorrection} need fixes
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-4xl font-semibold text-blue-600">
                {completedLeaflets}
              </p>
              <p className="text-sm font-light mt-1 text-slate-500">
                Completed Leaflets
              </p>
              <p className="text-xs font-light mt-2 text-slate-500">
                of {totalLeaflets} total (
                {totalLeaflets > 0
                  ? Math.round(
                      (completedLeaflets / totalLeaflets) * 100
                    )
                  : 0}
                %)
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton for initial load
// ---------------------------------------------------------------------------

function AnalyticsContentSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="border-slate-200">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="h-12 w-12 rounded-lg bg-slate-100 animate-pulse" />
                <div className="space-y-2">
                  <div className="h-7 w-16 bg-slate-100 rounded animate-pulse" />
                  <div className="h-4 w-24 bg-slate-100 rounded animate-pulse" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <Card key={i} className="border-slate-200">
            <CardHeader>
              <div className="h-5 w-40 bg-slate-100 rounded animate-pulse" />
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[...Array(4)].map((_, j) => (
                  <div key={j}>
                    <div className="h-4 w-full bg-slate-100 rounded animate-pulse mb-2" />
                    <div className="h-3 w-full bg-slate-100 rounded-full animate-pulse" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="border-slate-200">
        <CardHeader>
          <div className="h-5 w-48 bg-slate-100 rounded animate-pulse" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="p-4 rounded-lg bg-slate-50"
              >
                <div className="h-7 w-10 bg-slate-100 rounded animate-pulse mb-1" />
                <div className="h-4 w-16 bg-slate-100 rounded animate-pulse" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="border-slate-200">
            <CardContent className="p-6">
              <div className="flex flex-col items-center gap-2">
                <div className="h-10 w-20 bg-slate-100 rounded animate-pulse" />
                <div className="h-4 w-28 bg-slate-100 rounded animate-pulse" />
                <div className="h-3 w-32 bg-slate-100 rounded animate-pulse" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
