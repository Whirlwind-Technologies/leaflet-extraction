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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  FileText,
  ArrowLeft,
  Shield,
  Search,
  Download,
  Filter,
  User,
  Clock,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Eye,
  RefreshCw,
  Database,
  Key,
  Settings,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import {
  getAuditLogs,
  getUsers,
  getOrganizations,
  getPlatformProviders,
  exportComplianceReport,
} from "@/lib/actions/admin";
import { brandColors as colors } from "@/lib/brand-colors";

// Interface matching the backend AuditLogResponse schema exactly
interface AuditLog {
  id: string;
  user_id?: string;
  organization_id?: string;
  event_type: string;
  event_status: string;
  session_id?: string;
  provider_type?: string;
  provider_id?: string;
  platform_provider_id?: string;
  model_name?: string;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
  processing_time_ms?: number;
  error_category?: string;
  error_message?: string;
  ip_address?: string;
  user_agent?: string;
  request_metadata?: Record<string, unknown>;
  response_metadata?: Record<string, unknown>;
  created_at: string;
  // UI-derived field - we'll use event_type as resource_type
  resource_type?: string;
}


interface User {
  id: string;
  email: string;
  name?: string;
}

interface Organization {
  id: string;
  name: string;
  slug: string;
}

interface PlatformProvider {
  id: string;
  name: string;
  provider_type: string;
}

interface AuditLogFilters {
  search: string;
  user_id: string;
  organization_id: string;
  action: string;
  resource_type: string;
  success: string;
  start_date: string;
  end_date: string;
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [providers, setProviders] = useState<PlatformProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [isDetailDialogOpen, setIsDetailDialogOpen] = useState(false);

  const [filters, setFilters] = useState<AuditLogFilters>({
    search: "",
    user_id: "",
    organization_id: "",
    action: "",
    resource_type: "",
    success: "",
    start_date: "",
    end_date: "",
  });

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalLogs, setTotalLogs] = useState(0);
  const logsPerPage = 50;

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const filterParams = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value)
      );

      const result = await getAuditLogs({
        skip: (currentPage - 1) * logsPerPage,
        limit: logsPerPage,
        ...filterParams,
      });

      if (result.success && result.data) {
        setLogs((result.data.items || []) as unknown as AuditLog[]);
        setTotalPages(Math.ceil(result.data.total / logsPerPage) || 1);
        setTotalLogs(result.data.total || 0);
      } else {
        throw new Error(result.error || "Failed to fetch audit logs");
      }
    } catch (error) {
      console.error("Error fetching logs:", error);
      toast.error("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  }, [currentPage, filters]);

  useEffect(() => {
    fetchLogs();
    fetchUsers();
    fetchOrganizations();
    fetchProviders();
  }, [fetchLogs]);

  const fetchUsers = async () => {
    try {
      const result = await getUsers({});

      if (result.success && result.data) {
        // getUsers returns UserResponse[] directly
        setUsers(result.data);
      }
    } catch (error) {
      console.error("Error fetching users:", error);
    }
  };

  const fetchOrganizations = async () => {
    try {
      const result = await getOrganizations({});

      if (result.success && result.data) {
        // Check if it's a paginated response or direct array
        const organizations = Array.isArray(result.data) ? result.data : (result.data.items || []);
        setOrganizations(organizations);
      }
    } catch (error) {
      console.error("Error fetching organizations:", error);
    }
  };

  const fetchProviders = async () => {
    try {
      const result = await getPlatformProviders({});

      if (result.success && result.data) {
        // getPlatformProviders returns PlatformProvider[] directly
        setProviders(result.data);
      }
    } catch (error) {
      console.error("Error fetching providers:", error);
    }
  };

  const handleFilterChange = (key: keyof AuditLogFilters, value: string) => {
    setFilters({ ...filters, [key]: value });
    setCurrentPage(1); // Reset to first page when filtering
  };

  const clearFilters = () => {
    setFilters({
      search: "",
      user_id: "",
      organization_id: "",
      action: "",
      resource_type: "",
      success: "",
      start_date: "",
      end_date: "",
    });
    setCurrentPage(1);
  };

  const handleExport = async (format: "csv" | "json") => {
    try {
      setExporting(true);

      // Provide default date range if not specified
      const startDate = filters.start_date || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; // 30 days ago
      const endDate = filters.end_date || new Date().toISOString().split('T')[0]; // today

      const result = await exportComplianceReport({
        start_date: startDate,
        end_date: endDate,
        format,
        organization_id: filters.organization_id || undefined,
      });

      if (result.success && result.data) {
        // Create a temporary link to trigger download
        const a = document.createElement("a");
        a.href = result.data.download_url;
        a.download = `audit-logs-${new Date().toISOString().split("T")[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        toast.success(`Audit logs exported as ${format.toUpperCase()}`);
      } else {
        throw new Error(result.error || "Failed to export audit logs");
      }
    } catch (error) {
      console.error("Error exporting logs:", error);
      toast.error("Failed to export audit logs");
    } finally {
      setExporting(false);
    }
  };

  const getActionIcon = (action: string) => {
    const actionLower = action.toLowerCase();
    if (actionLower.includes("create")) return <Info className="h-4 w-4" style={{ color: colors.success }} />;
    if (actionLower.includes("update")) return <Settings className="h-4 w-4" style={{ color: colors.info }} />;
    if (actionLower.includes("delete")) return <XCircle className="h-4 w-4" style={{ color: colors.error }} />;
    if (actionLower.includes("api_call")) return <Zap className="h-4 w-4" style={{ color: colors.primaryBrandBlue }} />;
    if (actionLower.includes("login")) return <User className="h-4 w-4" style={{ color: colors.info }} />;
    return <Activity className="h-4 w-4" style={{ color: colors.secondaryText }} />;
  };

  const getResourceTypeIcon = (resourceType: string) => {
    const typeLower = resourceType.toLowerCase();
    if (typeLower.includes("user")) return <User className="h-4 w-4" style={{ color: colors.info }} />;
    if (typeLower.includes("provider")) return <Database className="h-4 w-4" style={{ color: colors.success }} />;
    if (typeLower.includes("api")) return <Key className="h-4 w-4" style={{ color: colors.primaryBrandBlue }} />;
    if (typeLower.includes("organization")) return <Shield className="h-4 w-4" style={{ color: colors.warning }} />;
    return <FileText className="h-4 w-4" style={{ color: colors.secondaryText }} />;
  };

  const getResourceTypeBadgeStyle = (resourceType: string) => {
    const typeLower = resourceType.toLowerCase();
    if (typeLower.includes("user")) return { backgroundColor: colors.infoBg, color: colors.infoText, borderColor: colors.infoBorder };
    if (typeLower.includes("vlm_provider")) return { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder };
    if (typeLower.includes("platform_provider")) return { backgroundColor: colors.lightBlueTint, color: colors.primaryBrandBlue, borderColor: colors.primaryBrandBlue };
    if (typeLower.includes("organization")) return { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder };
    if (typeLower.includes("api_key")) return { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder };
    if (typeLower.includes("leaflet")) return { backgroundColor: colors.warningBg, color: colors.warningText, borderColor: colors.warningBorder };
    return { backgroundColor: colors.offWhiteBg, color: colors.secondaryText, borderColor: colors.borderGray };
  };

  const getUserEmail = (userId?: string) => {
    if (!userId) return "Unknown User";
    const user = users.find(u => u.id === userId);
    return user?.email || "Unknown User";
  };

  const getOrganizationName = (orgId: string | undefined) => {
    if (!orgId) return "N/A";
    const org = organizations.find(o => o.id === orgId);
    return org?.name || "Unknown Organization";
  };

  const getProviderName = (providerId: string | undefined) => {
    if (!providerId) return "N/A";
    const provider = providers.find(p => p.id === providerId);
    return provider?.name || "Unknown Provider";
  };

  const openDetailDialog = (log: AuditLog) => {
    setSelectedLog(log);
    setIsDetailDialogOpen(true);
  };

  const formatDuration = (ms: number | undefined) => {
    if (!ms) return "N/A";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (loading && logs.length === 0) {
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
                Audit <span className="font-normal">Logs</span>
              </h1>
              <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
                View and analyze system audit logs for security and compliance
              </p>
            </div>
          </div>
        </div>
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto" style={{ borderColor: colors.primaryBrandBlue }}></div>
            <p className="mt-4" style={{ color: colors.secondaryText }}>Loading audit logs...</p>
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
              Audit <span className="font-normal">Logs</span>
            </h1>
            <p className="text-sm font-light" style={{ color: colors.secondaryText }}>
              View and analyze system audit logs for security and compliance
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => handleExport("csv")}
              disabled={exporting}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
            <Button
              variant="outline"
              onClick={() => handleExport("json")}
              disabled={exporting}
              style={{ borderColor: colors.borderGray, color: colors.primaryText }}
            >
              <Download className="h-4 w-4 mr-2" />
              Export JSON
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Total Logs</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>{totalLogs.toLocaleString()}</p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                <FileText className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
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
                  {logs.length > 0 ? ((logs.filter(l => l.event_status === "success").length / logs.length) * 100).toFixed(1) : 0}%
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
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>Errors</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {logs.filter(l => l.event_status !== "success").length}
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
                <p className="text-sm font-light" style={{ color: colors.secondaryText }}>API Calls</p>
                <p className="text-3xl font-light mt-1" style={{ color: colors.deepNavy }}>
                  {logs.filter(l => l.event_type.includes("api_call") || l.event_type.includes("extraction")).length}
                </p>
              </div>
              <div className="p-3 rounded-lg" style={{ backgroundColor: colors.lightBlueTint }}>
                <Zap className="h-6 w-6" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="bg-white mb-6" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
            <Filter className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4" style={{ color: colors.secondaryText }} />
              <Input
                placeholder="Search logs..."
                value={filters.search}
                onChange={(e) => handleFilterChange("search", e.target.value)}
                className="pl-10"
                style={{ borderColor: colors.borderGray }}
              />
            </div>

            <Select
              value={filters.user_id || "all"}
              onValueChange={(value) => handleFilterChange("user_id", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <User className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Users" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Users</SelectItem>
                {users.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={filters.organization_id || "all"}
              onValueChange={(value) => handleFilterChange("organization_id", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <Shield className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
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

            <Select
              value={filters.action || "all"}
              onValueChange={(value) => handleFilterChange("action", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <Activity className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Actions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Actions</SelectItem>
                <SelectItem value="create">Create</SelectItem>
                <SelectItem value="update">Update</SelectItem>
                <SelectItem value="delete">Delete</SelectItem>
                <SelectItem value="api_call">API Call</SelectItem>
                <SelectItem value="login">Login</SelectItem>
                <SelectItem value="logout">Logout</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <Select
              value={filters.resource_type || "all"}
              onValueChange={(value) => handleFilterChange("resource_type", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <Database className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Resources" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Resources</SelectItem>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="vlm_provider">VLM Provider</SelectItem>
                <SelectItem value="platform_provider">Platform Provider</SelectItem>
                <SelectItem value="organization">Organization</SelectItem>
                <SelectItem value="api_key">API Key</SelectItem>
                <SelectItem value="leaflet">Leaflet</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={filters.success || "all"}
              onValueChange={(value) => handleFilterChange("success", value === "all" ? "" : value)}
            >
              <SelectTrigger style={{ borderColor: colors.borderGray }}>
                <CheckCircle className="h-4 w-4 mr-2" style={{ color: colors.secondaryText }} />
                <SelectValue placeholder="All Results" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Results</SelectItem>
                <SelectItem value="true">Success</SelectItem>
                <SelectItem value="false">Error</SelectItem>
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

            <div>
              <Input
                type="date"
                placeholder="End Date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange("end_date", e.target.value)}
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

      {/* Audit Logs Table */}
      <Card className="bg-white" style={{ borderColor: colors.borderGray }}>
        <CardHeader className="border-b" style={{ borderColor: colors.borderGray, backgroundColor: colors.offWhiteBg }}>
          <CardTitle className="text-lg font-light flex items-center gap-3" style={{ color: colors.primaryText }}>
            <FileText className="h-5 w-5" style={{ color: colors.primaryBrandBlue }} strokeWidth={1.5} />
            Audit Logs ({logs.length} of {totalLogs.toLocaleString()})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {logs.length === 0 ? (
            <div className="text-center p-12">
              <div className="p-6 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center" style={{ backgroundColor: colors.offWhiteBg }}>
                <FileText className="h-12 w-12" style={{ color: colors.secondaryText }} strokeWidth={1.5} />
              </div>
              <h3 className="text-xl font-light mb-4" style={{ color: colors.primaryText }}>No Audit Logs</h3>
              <p className="max-w-md mx-auto mb-8" style={{ color: colors.secondaryText }}>
                No audit logs found matching your current filters. Try adjusting the filter criteria.
              </p>
              <Button onClick={clearFilters} variant="outline" style={{ borderColor: colors.borderGray, color: colors.primaryText }}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Clear Filters
              </Button>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow style={{ borderColor: colors.borderGray }}>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>Timestamp</TableHead>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>User & Organization</TableHead>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>Action & Resource</TableHead>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>Provider</TableHead>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>Result</TableHead>
                    <TableHead className="font-light" style={{ color: colors.secondaryText }}>Performance</TableHead>
                    <TableHead className="font-light text-right" style={{ color: colors.secondaryText }}>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id} className="transition-colors" style={{ borderColor: colors.borderGray }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = colors.hoverGray} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                      <TableCell>
                        <div className="text-sm">
                          <div className="font-medium" style={{ color: colors.primaryText }}>
                            {new Date(log.created_at).toLocaleDateString()}
                          </div>
                          <div className="flex items-center gap-1" style={{ color: colors.secondaryText }}>
                            <Clock className="h-3 w-3" />
                            {new Date(log.created_at).toLocaleTimeString()}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium text-sm" style={{ color: colors.primaryText }}>
                            {getUserEmail(log.user_id)}
                          </div>
                          <div className="text-xs flex items-center gap-1" style={{ color: colors.secondaryText }}>
                            <Shield className="h-3 w-3" />
                            {getOrganizationName(log.organization_id)}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            {getActionIcon(log.event_type)}
                            <span className="text-sm font-medium" style={{ color: colors.primaryText }}>
                              {log.event_type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                            </span>
                          </div>
                          <div
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border"
                            style={getResourceTypeBadgeStyle(log.event_type)}
                          >
                            {getResourceTypeIcon(log.event_type)}
                            {log.event_type.replace(/_/g, " ").toUpperCase()}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm" style={{ color: colors.secondaryText }}>
                          {getProviderName(log.platform_provider_id)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div
                            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border"
                            style={log.event_status === "success"
                              ? { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }
                              : { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder }
                            }
                          >
                            {log.event_status === "success" ? (
                              <CheckCircle className="h-3 w-3 mr-1" />
                            ) : (
                              <XCircle className="h-3 w-3 mr-1" />
                            )}
                            {log.event_status === "success" ? "Success" : "Error"}
                          </div>
                          {log.event_status !== "success" && log.error_message && (
                            <div className="text-xs max-w-[150px] truncate" style={{ color: colors.error }}>
                              {log.error_message}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm space-y-1">
                          {log.processing_time_ms && (
                            <div style={{ color: colors.secondaryText }}>
                              {formatDuration(log.processing_time_ms)}
                            </div>
                          )}
                          {(log.input_tokens || log.output_tokens) && (
                            <div className="text-xs" style={{ color: colors.secondaryText }}>
                              {((log.input_tokens || 0) + (log.output_tokens || 0)).toLocaleString()} tokens
                            </div>
                          )}
                          {log.cost && (
                            <div className="text-xs" style={{ color: colors.secondaryText }}>
                              ${log.cost.toFixed(4)}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDetailDialog(log)}
                          className="h-8 w-8 p-0"
                          style={{ borderColor: colors.borderGray }}
                        >
                          <Eye className="h-4 w-4" style={{ color: colors.info }} />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-6 py-4 border-t" style={{ borderColor: colors.borderGray }}>
                  <div className="text-sm" style={{ color: colors.secondaryText }}>
                    Showing {((currentPage - 1) * logsPerPage) + 1} to {Math.min(currentPage * logsPerPage, totalLogs)} of {totalLogs.toLocaleString()} logs
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                      style={{ borderColor: colors.borderGray, color: colors.primaryText }}
                    >
                      Previous
                    </Button>
                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                        const page = i + 1;
                        return (
                          <Button
                            key={page}
                            variant={currentPage === page ? "default" : "outline"}
                            size="sm"
                            onClick={() => setCurrentPage(page)}
                            className="w-8 h-8 p-0"
                            style={currentPage === page
                              ? { backgroundColor: colors.primaryBrandBlue, color: "white" }
                              : { borderColor: colors.borderGray, color: colors.primaryText }
                            }
                          >
                            {page}
                          </Button>
                        );
                      })}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      style={{ borderColor: colors.borderGray, color: colors.primaryText }}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={isDetailDialogOpen} onOpenChange={setIsDetailDialogOpen}>
        <DialogContent className="sm:max-w-[700px]">
          <DialogHeader>
            <DialogTitle style={{ color: colors.primaryText }}>Audit Log Details</DialogTitle>
            <DialogDescription style={{ color: colors.secondaryText }}>
              Detailed information about this audit log entry.
            </DialogDescription>
          </DialogHeader>

          {selectedLog && (
            <div className="space-y-6 py-4">
              {/* Basic Info */}
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Basic Information</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Timestamp</Label>
                    <div className="font-mono" style={{ color: colors.primaryText }}>{new Date(selectedLog.created_at).toLocaleString()}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>User</Label>
                    <div style={{ color: colors.primaryText }}>{getUserEmail(selectedLog.user_id)}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Organization</Label>
                    <div style={{ color: colors.primaryText }}>{getOrganizationName(selectedLog.organization_id)}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>IP Address</Label>
                    <div className="font-mono" style={{ color: colors.primaryText }}>{selectedLog.ip_address}</div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Action</Label>
                    <div className="flex items-center gap-2" style={{ color: colors.primaryText }}>
                      {getActionIcon(selectedLog.event_type)}
                      {selectedLog.event_type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Resource Type</Label>
                    <div className="flex items-center gap-2" style={{ color: colors.primaryText }}>
                      {getResourceTypeIcon(selectedLog.resource_type || selectedLog.event_type)}
                      {(selectedLog.resource_type || selectedLog.event_type).replace(/_/g, " ").toUpperCase()}
                    </div>
                  </div>
                </div>
              </div>

              <Separator style={{ backgroundColor: colors.borderGray }} />

              {/* Result & Performance */}
              <div>
                <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Result & Performance</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Success</Label>
                    <div
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border mt-1"
                      style={selectedLog.event_status === "success"
                        ? { backgroundColor: colors.successBg, color: colors.successText, borderColor: colors.successBorder }
                        : { backgroundColor: colors.errorBg, color: colors.errorText, borderColor: colors.errorBorder }
                      }
                    >
                      {selectedLog.event_status === "success" ? (
                        <CheckCircle className="h-3 w-3 mr-1" />
                      ) : (
                        <XCircle className="h-3 w-3 mr-1" />
                      )}
                      {selectedLog.event_status === "success" ? "Success" : "Error"}
                    </div>
                  </div>
                  <div>
                    <Label style={{ color: colors.secondaryText }}>Execution Time</Label>
                    <div style={{ color: colors.primaryText }}>{formatDuration(selectedLog.processing_time_ms)}</div>
                  </div>
                  {(selectedLog.input_tokens || selectedLog.output_tokens) && (
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Tokens Used</Label>
                      <div style={{ color: colors.primaryText }}>{((selectedLog.input_tokens || 0) + (selectedLog.output_tokens || 0)).toLocaleString()}</div>
                    </div>
                  )}
                  {selectedLog.cost && (
                    <div>
                      <Label style={{ color: colors.secondaryText }}>Cost</Label>
                      <div style={{ color: colors.primaryText }}>${selectedLog.cost.toFixed(4)}</div>
                    </div>
                  )}
                </div>
              </div>

              {selectedLog.error_message && (
                <>
                  <Separator style={{ backgroundColor: colors.borderGray }} />
                  <div>
                    <h4 className="font-medium mb-3" style={{ color: colors.error }}>Error Message</h4>
                    <div className="border rounded-md p-3 text-sm" style={{ backgroundColor: colors.errorBg, borderColor: colors.errorBorder, color: colors.errorText }}>
                      {selectedLog.error_message}
                    </div>
                  </div>
                </>
              )}

              {/* User Agent */}
              {selectedLog.user_agent && (
                <>
                  <Separator style={{ backgroundColor: colors.borderGray }} />
                  <div>
                    <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>User Agent</h4>
                    <div className="border rounded-md p-3 text-sm font-mono break-all" style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray, color: colors.primaryText }}>
                      {selectedLog.user_agent}
                    </div>
                  </div>
                </>
              )}

              {/* Request/Response Data (if available) */}
              {(selectedLog.request_metadata || selectedLog.response_metadata) && (
                <>
                  <Separator style={{ backgroundColor: colors.borderGray }} />
                  <div>
                    <h4 className="font-medium mb-3" style={{ color: colors.primaryText }}>Additional Data</h4>
                    <div className="space-y-3">
                      {selectedLog.request_metadata && (
                        <div>
                          <Label style={{ color: colors.secondaryText }}>Request Metadata</Label>
                          <pre className="border rounded-md p-3 text-xs overflow-x-auto" style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray, color: colors.primaryText }}>
                            {JSON.stringify(selectedLog.request_metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                      {selectedLog.response_metadata && (
                        <div>
                          <Label style={{ color: colors.secondaryText }}>Response Metadata</Label>
                          <pre className="border rounded-md p-3 text-xs overflow-x-auto" style={{ backgroundColor: colors.offWhiteBg, borderColor: colors.borderGray, color: colors.primaryText }}>
                            {JSON.stringify(selectedLog.response_metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
