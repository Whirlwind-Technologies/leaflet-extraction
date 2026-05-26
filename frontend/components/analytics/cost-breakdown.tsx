'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DollarSign, TrendingUp, Loader2, Info } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { getCostBreakdown, type CostBreakdown as CostBreakdownData } from '@/lib/actions/analytics';

interface CostBreakdownProps {
  period: number;
}

export function CostBreakdown({ period }: CostBreakdownProps) {
  const [loading, setLoading] = useState(true);
  const [costs, setCosts] = useState<CostBreakdownData | null>(null);

  useEffect(() => {
    const fetchCosts = async () => {
      setLoading(true);
      try {
        const data = await getCostBreakdown(period);
        setCosts(data);
      } catch (error) {
        console.error('Failed to fetch costs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCosts();
  }, [period]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const maxCost = Math.max(...(costs?.daily_costs?.map((d) => d.cost) || [0]), 0.001);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <DollarSign className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-3xl font-bold">${costs?.period_cost?.toFixed(2) || '0.00'}</p>
                <div className="flex items-center gap-1">
                  <p className="text-sm text-gray-500">Period Cost</p>
                  <Tooltip>
                    <TooltipTrigger className="cursor-help inline-flex" aria-label="About period cost">
                      <Info className="h-3.5 w-3.5 text-gray-400" />
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

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-3xl font-bold">{((costs?.period_input_tokens || 0) / 1000000).toFixed(2)}M</p>
                <p className="text-sm text-gray-500">Input Tokens</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <TrendingUp className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-3xl font-bold">{((costs?.period_output_tokens || 0) / 1000000).toFixed(2)}M</p>
                <p className="text-sm text-gray-500">Output Tokens</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Daily Costs</CardTitle>
        </CardHeader>
        <CardContent>
          {costs?.daily_costs?.length ? (
            <div className="h-64 flex items-end gap-1">
              {costs.daily_costs.map((day) => (
                <div
                  key={day.date}
                  className="flex-1 bg-blue-500 rounded-t hover:bg-blue-600 transition-colors relative group"
                  style={{ height: `${(day.cost / maxCost) * 100}%`, minHeight: '4px' }}
                >
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    ${day.cost.toFixed(2)} - {day.date}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No cost data available
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cost by Provider</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {costs?.by_provider?.length ? (
                costs.by_provider.map((item) => (
                  <div key={item.provider_type} className="flex justify-between items-center">
                    <span className="capitalize">{item.provider_name || item.provider_type}</span>
                    <span className="font-bold">${item.cost.toFixed(2)} ({item.percentage.toFixed(1)}%)</span>
                  </div>
                ))
              ) : (
                <p className="text-gray-500">No data available</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cost by Model</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {costs?.by_model?.length ? (
                costs.by_model.map((item) => (
                  <div key={item.model_name} className="flex justify-between items-center">
                    <span className="font-mono text-sm">{item.model_name}</span>
                    <span className="font-bold">${item.cost.toFixed(2)} ({item.percentage.toFixed(1)}%)</span>
                  </div>
                ))
              ) : (
                <p className="text-gray-500">No data available</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}