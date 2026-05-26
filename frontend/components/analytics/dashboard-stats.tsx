'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Package, Zap, DollarSign, Loader2, Info } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { getDashboardStats, type DashboardStats } from '@/lib/actions/analytics';

interface DashboardStatsProps {
  period: number;
}

export function DashboardStatsComponent({ period }: DashboardStatsProps) {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      try {
        const data = await getDashboardStats(period);
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [period]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-blue-50">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-slate-800">{stats?.leaflets?.period_total || 0}</p>
                <p className="text-sm text-slate-500">Leaflets ({period}d)</p>
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
                <p className="text-3xl font-bold text-slate-800">{stats?.products?.period_total || 0}</p>
                <p className="text-sm text-slate-500">Products ({period}d)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-violet-50">
                <Zap className="h-6 w-6 text-violet-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-slate-800">{stats?.quality?.auto_approval_rate || 0}%</p>
                <p className="text-sm text-slate-500">Auto-Approval</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-amber-50">
                <DollarSign className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-3xl font-bold text-slate-800">${stats?.costs?.period_cost?.toFixed(2) || '0.00'}</p>
                <div className="flex items-center gap-1">
                  <p className="text-sm text-slate-500">Cost ({period}d)</p>
                  <Tooltip>
                    <TooltipTrigger className="cursor-help inline-flex" aria-label="About period cost">
                      <Info className="h-3.5 w-3.5 text-slate-400" />
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs">
                      <p>Includes all VLM API usage across all providers, including the platform default provider.</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="text-base text-slate-800">Lifetime Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-slate-500">Total Leaflets Processed</span>
                <span className="font-bold text-slate-800">{stats?.leaflets?.total || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Total Products Extracted</span>
                <span className="font-bold text-slate-800">{stats?.products?.total || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Total Auto-Approved</span>
                <span className="font-bold text-slate-800">{stats?.products?.auto_approved || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="flex items-center gap-1 text-slate-500">
                  Total API Cost
                  <Tooltip>
                    <TooltipTrigger className="cursor-help inline-flex" aria-label="About total API cost">
                      <Info className="h-3.5 w-3.5 text-slate-400" />
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs">
                      <p>Includes all VLM API usage across all providers, including the platform default provider.</p>
                    </TooltipContent>
                  </Tooltip>
                </span>
                <span className="font-bold text-slate-800">${stats?.costs?.total_cost?.toFixed(2) || '0.00'}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="text-base text-slate-800">Quality Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-600">Average Confidence</span>
                  <span className="font-bold text-slate-800">{stats?.quality?.avg_confidence || 0}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${stats?.quality?.avg_confidence || 0}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-600">Auto-Approval Rate</span>
                  <span className="font-bold text-slate-800">{stats?.quality?.auto_approval_rate || 0}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full">
                  <div
                    className="h-full bg-emerald-500 rounded-full"
                    style={{ width: `${stats?.quality?.auto_approval_rate || 0}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Keep backward compatible export
export { DashboardStatsComponent as DashboardStats };