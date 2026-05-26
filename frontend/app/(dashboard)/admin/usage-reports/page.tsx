"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";


import {
  BarChart3,
  ArrowLeft,
  TrendingUp,
  FileBarChart,
  Calendar,
  Download,
  Filter,
  Users,
  DollarSign,
  Clock,
  Zap,
  Database,
  RefreshCw,
  Activity,
  Target,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { toast } from "sonner";
import {
  getUsageReports,
  getUsageAnalytics,
  exportUsageReport,
  getUsageReportFilterOptions,
} from "@/lib/actions/admin";
import { brandColors as colors } from "@/lib/brand-colors";

interface UsageReport {
  id: string;
  organization_id?: string;
  organization_name?: string;
  user_id?: string;
  user_email?: string;
  platform_provider_id?: string;
  provider_name?: string;
  provider_type?: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  avg_cost_per_request: number;
  avg_tokens_per_request: number;
  success_rate: number;
  error_count: number;
  peak_hour?: string;
  peak_requests?: number;
  created_at: string;
}

interface UsageMetrics {
  total_requests: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_cost_per_request: number;
  success_rate: number;
  unique_users: number;
  unique_organizations: number;
  top_provider: {
    name: string;
    requests: number;
    percentage: number;
  };
  cost_trend: "increasing" | "decreasing" | "stable";
}

interface ReportFilters {
  start_date: string;
  end_date: string;
  organization_id: string;
  user_id: string;
  provider_id: string;
  period_type: string;
}

interface Organization {
  id: string;
  name: string;
}

interface PlatformProvider {
  id: string;
  name: string;
  provider_type: string;
}

export default function UsageReportsPage() {
  const [reports, setReports] = useState<UsageReport[]>([]);
  const [metrics, setMetrics] = useState<UsageMetrics | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [providers, setProviders] = useState<PlatformProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [filters, setFilters] = useState<ReportFilters>({
    start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0], // 30 days ago
    end_date: new Date().toISOString().split("T")[0], // Today
    organization_id: "",
    user_id: "",
    provider_id: "",
    period_type: "daily",
  });

  useEffect(() => {
    fetchFilterOptions();
  }, []);

  const fetchReports = useCallback(async () => {
    try {
      setLoading(true);
      const filterParams = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value)
      );

      const result = await getUsageReports(filterParams);

      if (result.success && result.data) {
        setReports((result.data.items || []) as unknown as UsageReport[]);
      } else {
        throw new Error(result.error || "Failed to fetch usage reports");
      }
    } catch (error) {
      console.error("Error fetching reports:", error);
      toast.error("Failed to load usage reports");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const fetchMetrics = useCallback(async () => {
    try {
      // Map frontend filter names to backend parameter names
      const analyticsParams: {
        organization_id?: string;
        provider_id?: string;
        start_date?: string;
        end_date?: string;
      } = {};

      if (filters.organization_id) analyticsParams.organization_id = filters.organization_id;
      if (filters.provider_id) analyticsParams.provider_id = filters.provider_id;
      if (filters.start_date) analyticsParams.start_date = filters.start_date;
      if (filters.end_date) analyticsParams.end_date = filters.end_date;

      const result = await getUsageAnalytics(analyticsParams);

      if (result.success && result.data) {
        setMetrics(result.data as unknown as UsageMetrics);
      }
    } catch (error) {
      console.error("Error fetching metrics:", error);
    }
  }, [filters]);

  // Auto-refresh when filters change
  useEffect(() => {
    fetchReports();
    fetchMetrics();
  }, [fetchReports, fetchMetrics]);

  const fetchFilterOptions = async () => {
    try {
      const result = await getUsageReportFilterOptions();

      if (result.success && result.data) {
        setOrganizations(result.data.organizations || []);
        setProviders(result.data.providers || []);
      }
    } catch (error) {
      console.error("Error fetching filter options:", error);
    }
  };

  const handleFilterChange = (key: keyof ReportFilters, value: string) => {
    setFilters({ ...filters, [key]: value });
  };

  const generateReport = async () => {
    setGenerating(true);
    try {
      await fetchReports();
      await fetchMetrics();
      toast.success("Usage report generated successfully");
    } catch (error) {
      console.error("Error generating report:", error);
      toast.error("Failed to generate usage report");
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async (format: "csv" | "excel" | "json") => {
    try {
      setExporting(true);
      const filterParams = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value)
      );

      const result = await exportUsageReport(filterParams, format);

      if (result.success && result.data) {
        // Create a temporary link to trigger download
        const a = document.createElement("a");
        a.href = result.data.download_url;
        a.download = `usage-report-${new Date().toISOString().split("T")[0]}.${format === "excel" ? "xlsx" : format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        toast.success(`Usage report exported as ${format.toUpperCase()}`);
      } else {
        throw new Error(result.error || "Failed to export usage report");
      }
    } catch (error) {
      console.error("Error exporting report:", error);
      toast.error("Failed to export usage report");
    } finally {
      setExporting(false);
    }
  };

  const clearFilters = () => {
    setFilters({
      start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
      end_date: new Date().toISOString().split("T")[0],
      organization_id: "",
      user_id: "",
      provider_id: "",
      period_type: "daily",
    });
  };

  const formatCurrency = (amount: number | undefined | null) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 4,
    }).format(amount ?? 0);
  };

  const formatNumber = (num: number | undefined | null) => {
    return new Intl.NumberFormat("en-US").format(num ?? 0);
  };

  const formatPercentage = (num: number | undefined | null) => {
    if (num === undefined || num === null) return "0.0%";
    return `${num.toFixed(1)}%`;
  };

  const getTrendIcon = (trend: string | undefined | null) => {
    switch (trend) {
      case "increasing":
        return <TrendingUp className="h-4 w-4" style={{ color: colors.error }} />;
      case "decreasing":
        return <TrendingUp className="h-4 w-4 rotate-180" style={{ color: colors.success }} />;
      default:
        return <Activity className="h-4 w-4" style={{ color: colors.secondaryText }} />;
    }
  };

  if (loading && reports.length === 0) {
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
                Usage <span className="font-normal">Reports</span>
              </h1>
              <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
                Comprehensive usage analytics and reporting for VLM consumption
              </p>
            </div>
          </div>
        </div>
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto" style={{ borderColor: colors.primaryBrandBlue }}></div>
            <p className="mt-4" style={{ color: colors.secondaryText }}>Loading usage reports...</p>
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
              Usage <span className="font-normal">Reports</span>
            </h1>
            <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
              Comprehensive usage analytics and reporting for VLM consumption
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={generateReport}
              disabled={generating}
              style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }}
              className="hover:opacity-90"
            >
              {generating ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <BarChart3 className="h-4 w-4 mr-2" />
              )}
              Generate Report
            </Button>
          </div>
        </div>
      </div>

      {/* Metrics Overview */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Requests</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    {formatNumber(metrics.total_requests)}
                  </p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                  <Activity className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Cost</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    {formatCurrency(metrics.total_cost)}
                  </p>
                  <div className="flex items-center gap-1 mt-1">
                    {getTrendIcon(metrics.cost_trend)}
                    <span className="text-xs capitalize" style={{ color: colors.secondaryText }}>
                      {metrics.cost_trend}
                    </span>
                  </div>
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
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Success Rate</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    {formatPercentage(metrics.success_rate)}
                  </p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.successBg }}>
                  <CheckCircle className="h-6 w-6" style={{ color: colors.success }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Active Users</p>
                  <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{metrics.unique_users}</p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.infoBg }}>
                  <Users className="h-6 w-6" style={{ color: colors.info }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Additional Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Tokens</p>
                  <p className="text-xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    {formatNumber(metrics.total_input_tokens + metrics.total_output_tokens)}
                  </p>
                  <div className="text-xs mt-1" style={{ color: colors.secondaryText }}>
                    In: {formatNumber(metrics.total_input_tokens)} | Out: {formatNumber(metrics.total_output_tokens)}
                  </div>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                  <Zap className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Avg Cost/Request</p>
                  <p className="text-xl font-light mt-1" style={{ color: colors.deepNavy }}>
                    {formatCurrency(metrics.avg_cost_per_request)}
                  </p>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.warningBg }}>
                  <Target className="h-6 w-6" style={{ color: colors.warning }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Top Provider</p>
                  <p className="text-lg font-light mt-1" style={{ color: colors.deepNavy }}>
                    {metrics.top_provider?.name || "N/A"}
                  </p>
                  <div className="text-xs mt-1" style={{ color: colors.secondaryText }}>
                    {formatNumber(metrics.top_provider?.requests)} ({formatPercentage(metrics.top_provider?.percentage)})
                  </div>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                  <Database className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card className="bg-white mb-6" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
            <Filter className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
            Report Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="flex flex-wrap gap-4 mb-4">
            <div className="flex-1 min-w-[140px] max-w-[200px]">
              <Label htmlFor="start_date" style={{ color: colors.primaryText }}>Start Date</Label>
              <Input
                type="date"
                id="start_date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange("start_date", e.target.value)}
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <div className="flex-1 min-w-[140px] max-w-[200px]">
              <Label htmlFor="end_date" style={{ color: colors.primaryText }}>End Date</Label>
              <Input
                type="date"
                id="end_date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange("end_date", e.target.value)}
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <div className="flex-1 min-w-[140px] max-w-[200px]">
              <Label htmlFor="period_type" style={{ color: colors.primaryText }}>Period Type</Label>
              <Select value={filters.period_type} onValueChange={(value) => handleFilterChange("period_type", value)}>
                <SelectTrigger style={{ borderColor: colors.borderGray }}>
                  <Calendar className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hourly">Hourly</SelectItem>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex-1 min-w-[160px] max-w-[220px]">
              <Label htmlFor="organization_id" style={{ color: colors.primaryText }}>Organization</Label>
              <Select
                value={filters.organization_id || "all"}
                onValueChange={(value) => handleFilterChange("organization_id", value === "all" ? "" : value)}
              >
                <SelectTrigger style={{ borderColor: colors.borderGray }}>
                  <Users className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                  <SelectValue placeholder="All Organizations" />
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

            <div className="flex-1 min-w-[160px] max-w-[220px]">
              <Label htmlFor="provider_id" style={{ color: colors.primaryText }}>Provider</Label>
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
            </div>

            <div className="flex items-end min-w-[100px]">
              <Button variant="outline" onClick={clearFilters} className="w-full" style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Clear
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Reports Table */}
      <Card className="bg-white mb-6" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <div className="flex justify-between items-center">
            <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
              <FileBarChart className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
              Usage Reports ({reports.length})
            </CardTitle>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport("csv")}
                disabled={exporting}
                style={{ borderColor: colors.borderGray, color: colors.primaryText }}
              >
                <Download className="h-4 w-4 mr-1" />
                CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport("excel")}
                disabled={exporting}
                style={{ borderColor: colors.borderGray, color: colors.primaryText }}
              >
                <Download className="h-4 w-4 mr-1" />
                Excel
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {reports.length === 0 ? (
            <div className="text-center p-12">
              <div className="p-6 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center" style={{ backgroundColor: colors.offWhiteBg }}>
                <BarChart3 className="h-12 w-12" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
              </div>
              <h3 className="text-xl font-light mb-4" style={{ color: colors.primaryText }}>No Usage Data</h3>
              <p className="max-w-md mx-auto mb-8" style={{ color: colors.secondaryText }}>
                No usage reports found for the selected period. Try adjusting your date range or filters.
              </p>
              <Button onClick={generateReport} disabled={generating} style={{ backgroundColor: colors.primaryBrandBlue, color: "white" }} className="hover:opacity-90">
                <BarChart3 className="h-4 w-4 mr-2" />
                Generate Report
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow style={{ borderColor: colors.borderGray }}>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Period</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Organization/User</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Provider</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Requests</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Tokens</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Cost</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Success Rate</TableHead>
                  <TableHead className="font-light" style={{ color: colors.secondaryText }}>Avg/Request</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id} className="transition-colors" style={{ borderColor: colors.borderGray }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                    <TableCell>
                      <div className="text-sm">
                        <div className="font-medium" style={{ color: colors.primaryText }}>
                          {new Date(report.period_start).toLocaleDateString()}
                        </div>
                        <div className="flex items-center gap-1" style={{ color: colors.secondaryText }}>
                          <Clock className="h-3 w-3" />
                          to {new Date(report.period_end).toLocaleDateString()}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        {report.organization_name && (
                          <div className="font-medium text-sm" style={{ color: colors.primaryText }}>
                            {report.organization_name}
                          </div>
                        )}
                        {report.user_email && (
                          <div className="text-xs" style={{ color: colors.secondaryText }}>
                            {report.user_email}
                          </div>
                        )}
                        {!report.organization_name && !report.user_email && (
                          <span className="text-sm" style={{ color: colors.secondaryText }}>Platform-wide</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div className="font-medium" style={{ color: colors.primaryText }}>
                          {report.provider_name || "All Providers"}
                        </div>
                        {report.provider_type && (
                          <div className="text-xs capitalize" style={{ color: colors.secondaryText }}>
                            {report.provider_type.replace("_", " ")}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-medium" style={{ color: colors.primaryText }}>
                          {formatNumber(report.total_requests)}
                        </span>
                        {report.error_count > 0 && (
                          <div className="inline-flex items-center px-2 py-0.5 rounded-full text-xs border" style={{ color: colors.error, borderColor: colors.errorBorder }}>
                            <AlertCircle className="h-2 w-2 mr-1" />
                            {report.error_count}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>
                          {formatNumber(report.total_input_tokens + report.total_output_tokens)}
                        </div>
                        <div className="text-xs" style={{ color: colors.secondaryText }}>
                          In: {formatNumber(report.total_input_tokens)} | Out: {formatNumber(report.total_output_tokens)}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium" style={{ color: colors.primaryText }}>
                        {formatCurrency(report.total_cost)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div
                        className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
                        style={
                          report.success_rate >= 95
                            ? { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }
                            : report.success_rate >= 85
                            ? { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder }
                            : { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder }
                        }
                      >
                        {formatPercentage(report.success_rate)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        <div style={{ color: colors.primaryText }}>
                          {formatCurrency(report.avg_cost_per_request)}
                        </div>
                        <div className="text-xs" style={{ color: colors.secondaryText }}>
                          {formatNumber(report.avg_tokens_per_request)} tokens
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
