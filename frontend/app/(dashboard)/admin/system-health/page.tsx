"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity,
  Database,
  Server,
  HardDrive,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronLeft,
  Loader2,
  Cpu,
} from "lucide-react";
import { getDetailedSystemHealth, SystemHealthData } from "@/lib/actions/admin";

function getStatusIcon(status: string) {
  switch (status) {
    case "healthy":
      return <CheckCircle className="h-5 w-5 text-green-600" strokeWidth={1.5} />;
    case "degraded":
      return <AlertTriangle className="h-5 w-5 text-yellow-600" strokeWidth={1.5} />;
    case "unhealthy":
      return <XCircle className="h-5 w-5 text-red-600" strokeWidth={1.5} />;
    default:
      return <Activity className="h-5 w-5 text-gray-400" strokeWidth={1.5} />;
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "healthy":
      return <Badge className="bg-green-50 text-green-700 border-green-200">Healthy</Badge>;
    case "degraded":
      return <Badge className="bg-yellow-50 text-yellow-700 border-yellow-200">Degraded</Badge>;
    case "unhealthy":
      return <Badge className="bg-red-50 text-red-700 border-red-200">Unhealthy</Badge>;
    default:
      return <Badge variant="secondary">Unknown</Badge>;
  }
}

function getComponentIcon(name: string) {
  if (name.toLowerCase().includes("database") || name.toLowerCase().includes("postgres")) {
    return <Database className="h-6 w-6" strokeWidth={1.5} />;
  }
  if (name.toLowerCase().includes("redis") || name.toLowerCase().includes("cache")) {
    return <Server className="h-6 w-6" strokeWidth={1.5} />;
  }
  if (name.toLowerCase().includes("storage") || name.toLowerCase().includes("s3")) {
    return <HardDrive className="h-6 w-6" strokeWidth={1.5} />;
  }
  if (name.toLowerCase().includes("celery") || name.toLowerCase().includes("worker")) {
    return <Cpu className="h-6 w-6" strokeWidth={1.5} />;
  }
  return <Activity className="h-6 w-6" strokeWidth={1.5} />;
}

export default function SystemHealthPage() {
  const [health, setHealth] = useState<SystemHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadHealth = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    const result = await getDetailedSystemHealth();
    if (result.success && result.data) {
      setHealth(result.data);
    } else {
      toast.error("Failed to load system health");
    }

    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    // loadHealth is async -- setState calls happen after await, not synchronously
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadHealth();
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => loadHealth(true), 30000);
    return () => clearInterval(interval);
  }, [loadHealth]);

  return (
    <div className="container mx-auto pb-6 max-w-5xl bg-gray-50">
      {/* Header */}
      <div className="mb-8">
        <Link href="/admin">
          <Button variant="ghost" size="sm" className="mb-4 text-gray-600">
            <ChevronLeft className="h-4 w-4 mr-1" strokeWidth={1.5} />
            Back to Admin
          </Button>
        </Link>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
              System <span className="font-normal">Health</span>
            </h1>
            <p className="text-sm text-gray-500">
              Monitor the health of all system components
            </p>
          </div>
          <div className="flex items-center gap-3">
            {health && getStatusBadge(health.overall_status)}
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadHealth(true)}
              disabled={refreshing}
              className="border-gray-200"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} strokeWidth={1.5} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-gray-500">Loading system health...</span>
        </div>
      ) : health ? (
        <div className="space-y-6">
          {/* Overall Status */}
          <Card className="bg-white border-gray-200">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`p-4 rounded-lg ${
                    health.overall_status === "healthy" ? "bg-green-50" :
                    health.overall_status === "degraded" ? "bg-yellow-50" : "bg-red-50"
                  }`}>
                    {getStatusIcon(health.overall_status)}
                  </div>
                  <div>
                    <h2 className="text-xl font-medium text-gray-900">
                      System Status: {health.overall_status.charAt(0).toUpperCase() + health.overall_status.slice(1)}
                    </h2>
                    <p className="text-sm text-gray-500">
                      {health.components.filter(c => c.status === "healthy").length} of {health.components.length} components healthy
                    </p>
                  </div>
                </div>
                <div className="text-right text-sm text-gray-500">
                  <div className="flex items-center gap-1">
                    <Clock className="h-4 w-4" strokeWidth={1.5} />
                    Last checked: {new Date(health.timestamp).toLocaleTimeString()}
                  </div>
                  <div className="mt-1">
                    Version: {health.version} ({health.environment})
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Component Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {health.components.map((component, index) => (
              <Card key={index} className={`bg-white border-gray-200 ${
                component.status === "unhealthy" ? "border-red-200" :
                component.status === "degraded" ? "border-yellow-200" : ""
              }`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${
                        component.status === "healthy" ? "bg-green-50 text-green-600" :
                        component.status === "degraded" ? "bg-yellow-50 text-yellow-600" :
                        "bg-red-50 text-red-600"
                      }`}>
                        {getComponentIcon(component.name)}
                      </div>
                      <CardTitle className="text-base font-medium text-gray-900">
                        {component.name}
                      </CardTitle>
                    </div>
                    {getStatusBadge(component.status)}
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-gray-600 mb-3">{component.message}</p>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    {component.latency_ms !== undefined && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" strokeWidth={1.5} />
                        {component.latency_ms}ms latency
                      </span>
                    )}
                    {component.details && (
                      <span className="text-gray-400">
                        {Object.entries(component.details).map(([key, value]) => (
                          <span key={key} className="ml-2">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Info */}
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="p-4">
              <p className="text-sm text-blue-800">
                <strong>Auto-refresh:</strong> This page automatically refreshes every 30 seconds.
                System health is also checked by Docker health checks and monitoring tools.
              </p>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="bg-white border-gray-200">
          <CardContent className="p-12 text-center">
            <XCircle className="h-12 w-12 mx-auto mb-4 text-red-400" strokeWidth={1.5} />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load Health Data</h3>
            <p className="text-gray-500 mb-4">Unable to retrieve system health information.</p>
            <Button onClick={() => loadHealth()} className="bg-blue-600 hover:bg-blue-700">
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
