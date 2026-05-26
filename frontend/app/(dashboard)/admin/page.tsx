"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Users,
  Brain,
  DollarSign,
  CheckCircle,
  Shield,
  BarChart3,
  FileText,
  Bell,
  ChevronRight,
  Settings,
  Activity,
  Archive,
  Clock,
  Loader2,
  Trash2,
  Info,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// Import admin actions
import { getSystemStats, getUsers, SystemStats, UserResponse } from "@/lib/actions/admin";

export default function AdminDashboard() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // Load system stats
      const statsResult = await getSystemStats();
      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      } else {
        toast.error("Failed to load system statistics");
      }

      // Load recent users
      const usersResult = await getUsers({ page: 1, page_size: 5 });
      if (usersResult.success && usersResult.data) {
        setUsers(usersResult.data);
      } else {
        toast.error("Failed to load user data");
      }
    } catch (error) {
      toast.error("Failed to load dashboard data");
      console.error("Dashboard error:", error);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="container mx-auto pb-6 max-w-7xl bg-gray-50">
      <div className="mb-12">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
              Admin <span className="font-normal">Dashboard</span>
            </h1>
            <p className="text-sm text-gray-500">
              Manage your platform and monitor system performance
            </p>
          </div>
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle className="h-4 w-4 mr-1" strokeWidth={1.5} />
            System Healthy
          </Badge>
        </div>
      </div>

      <div className="space-y-6">

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Total Users</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {loading ? "..." : stats?.total_users?.toLocaleString() || "0"}
                </p>
                <p className="text-xs mt-1 text-blue-600">
                  {loading ? "" : `${stats?.active_users || 0} active`}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-blue-50">
                <Users className="h-6 w-6 text-blue-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Total Leaflets</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {loading ? "..." : stats?.total_leaflets?.toLocaleString() || "0"}
                </p>
                <p className="text-xs mt-1 text-green-600">
                  {loading ? "" : `${stats?.leaflets_today || 0} today`}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-green-50">
                <FileText className="h-6 w-6 text-green-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-light text-gray-500">Total Products</p>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {loading ? "..." : stats?.total_products?.toLocaleString() || "0"}
                </p>
                <p className="text-xs mt-1 text-gray-500">
                  {loading ? "" : `${stats?.avg_products_per_leaflet || 0} avg per leaflet`}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-blue-50">
                <BarChart3 className="h-6 w-6 text-gray-700" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-1">
                  <p className="text-sm font-light text-gray-500">Total Cost</p>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3.5 w-3.5 text-gray-400 cursor-help" strokeWidth={1.5} />
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p>Total processing cost across all leaflets on the platform.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <p className="text-3xl font-light mt-1 text-gray-900">
                  {loading ? "..." : `$${stats?.total_cost?.toFixed(2) || "0.00"}`}
                </p>
                <p className="text-xs mt-1 text-green-600">
                  {loading ? "" : `${stats?.processing_success_rate || 0}% success rate`}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-green-50">
                <DollarSign className="h-6 w-6 text-green-600" strokeWidth={1.5} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Admin Navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="bg-white border-gray-200">
          <CardHeader className="border-b border-gray-200 bg-gray-50">
            <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
              <Shield className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
              User & Access
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              <Link href="/admin/users">
                <Button
                  variant="outline"
                  className="w-full justify-between hover:bg-gray-50 border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    User Management
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/registrations">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Business Registrations
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/deletion-requests">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Trash2 className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Deletion Requests
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardHeader className="border-b border-gray-200 bg-gray-50">
            <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
              <Brain className="h-5 w-5 text-green-600" strokeWidth={1.5} />
              VLM System
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              <Link href="/admin/vlm-models">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Settings className="h-4 w-4 text-green-600" strokeWidth={1.5} />
                    VLM Models Registry
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/platform-providers">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-green-600" strokeWidth={1.5} />
                    Platform Providers
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/provider-backups">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Archive className="h-4 w-4 text-green-600" strokeWidth={1.5} />
                    Provider Backups
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardHeader className="border-b border-gray-200 bg-gray-50">
            <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
              <Bell className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
              Monitoring & Alerts
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              <Link href="/admin/usage-reports">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Usage Reports
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/budget-alerts">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Budget Alerts
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/audit-logs">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Audit Logs
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200">
          <CardHeader className="border-b border-gray-200 bg-gray-50">
            <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
              <Settings className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
              System Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              <Link href="/admin/system-health">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    System Health
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
              <Link href="/admin/platform-settings">
                <Button
                  variant="outline"
                  className="w-full justify-between border-gray-200 text-gray-700"
                >
                  <span className="flex items-center gap-2">
                    <Settings className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                    Platform Settings
                  </span>
                  <ChevronRight className="h-4 w-4 text-gray-400" strokeWidth={1.5} />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card className="bg-white border-gray-200">
        <CardHeader className="border-b border-gray-200 bg-gray-50">
          <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
            <Activity className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-4">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                <span className="ml-2 text-gray-500">Loading recent activity...</span>
              </div>
            ) : users.length > 0 ? (
              users.slice(0, 5).map((user) => (
                <div
                  key={user.id}
                  className="flex items-center gap-4 p-3 rounded-lg transition-colors cursor-pointer border border-gray-200"
                >
                  <div className="p-2 rounded-lg bg-blue-50">
                    <Users className="h-4 w-4 text-blue-600" strokeWidth={1.5} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">
                      User: {user.full_name || user.email}
                    </p>
                    <p className="text-xs text-gray-500">
                      {user.leaflet_count} leaflets • {user.product_count} products • ${user.total_cost.toFixed(2)} spent
                      {user.is_superuser && " • Admin"}
                      {!user.is_active && " • Inactive"}
                    </p>
                  </div>
                  <div className="text-xs text-gray-500">
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : "Never"}
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8">
                <Users className="h-12 w-12 mx-auto mb-4 opacity-50 text-gray-400" strokeWidth={1.5} />
                <h3 className="text-lg font-light mb-2 text-gray-900">No Recent Activity</h3>
                <p className="text-gray-500">User activity will appear here once you have users in the system.</p>
              </div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-gray-200">
            <Link href="/admin/users">
              <Button
                variant="outline"
                className="w-full border-gray-200 text-gray-700"
              >
                <Clock className="h-4 w-4 mr-2 text-blue-600" strokeWidth={1.5} />
                View All Users
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* System Status */}
      <Card className="bg-white border-gray-200">
        <CardHeader className="border-b border-gray-200 bg-gray-50">
          <CardTitle className="text-lg font-light flex items-center gap-3 text-gray-900">
            <Settings className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center p-4 rounded-lg border border-gray-200">
              <div className="p-3 rounded-lg w-fit mx-auto mb-3 bg-green-50">
                <CheckCircle className="h-6 w-6 text-green-600" strokeWidth={1.5} />
              </div>
              <h4 className="font-medium mb-1 text-gray-900">API Health</h4>
              <p className="text-sm text-gray-500">All endpoints operational</p>
              <Badge className="mt-2 bg-green-50 text-green-700 border-green-200">Healthy</Badge>
            </div>

            <div className="text-center p-4 rounded-lg border border-gray-200">
              <div className="p-3 rounded-lg w-fit mx-auto mb-3 bg-blue-50">
                <Activity className="h-6 w-6 text-blue-600" strokeWidth={1.5} />
              </div>
              <h4 className="font-medium mb-1 text-gray-900">Database</h4>
              <p className="text-sm text-gray-500">Connected and responsive</p>
              <Badge className="mt-2 bg-blue-50 text-blue-700 border-blue-200">Online</Badge>
            </div>

            <div className="text-center p-4 rounded-lg border border-gray-200">
              <div className="p-3 rounded-lg w-fit mx-auto mb-3 bg-green-50">
                <Shield className="h-6 w-6 text-green-600" strokeWidth={1.5} />
              </div>
              <h4 className="font-medium mb-1 text-gray-900">Security</h4>
              <p className="text-sm text-gray-500">No threats detected</p>
              <Badge className="mt-2 bg-green-50 text-green-700 border-green-200">Secure</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </div>
  );
}
