'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Package, DollarSign, Loader2 } from 'lucide-react';
import { getUsageTrends, type UsageTrends as UsageTrendsData } from '@/lib/actions/analytics';

interface UsageTrendsProps {
  period: number;
}

export function UsageTrends({ period }: UsageTrendsProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<UsageTrendsData | null>(null);

  useEffect(() => {
    const fetchTrends = async () => {
      setLoading(true);
      try {
        const trendsData = await getUsageTrends(period);
        setData(trendsData);
      } catch (error) {
        console.error('Failed to fetch trends:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchTrends();
  }, [period]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  // Transform API trends data for charts
  const leafletTrends = data?.trends?.map(t => ({ date: t.date, value: t.leaflets })) || [];
  const productTrends = data?.trends?.map(t => ({ date: t.date, value: t.products })) || [];
  const costTrends = data?.trends?.map(t => ({ date: t.date, value: t.cost })) || [];

  const TrendChart = ({ 
    chartData, 
    color, 
    label, 
    formatValue 
  }: { 
    chartData: Array<{ date: string; value: number }>; 
    color: string; 
    label: string;
    formatValue: (v: number) => string;
  }) => {
    if (!chartData.length) {
      return (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{label}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40 flex items-center justify-center text-gray-500">
              No data available
            </div>
          </CardContent>
        </Card>
      );
    }
    
    const maxValue = Math.max(...chartData.map(d => d.value), 1);
    const total = chartData.reduce((sum, d) => sum + d.value, 0);
    const avg = total / chartData.length;
    
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex justify-between items-center">
            <span>{label}</span>
            <span className="text-sm font-normal text-gray-500">
              Total: {formatValue(total)} | Avg: {formatValue(avg)}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-40 flex items-end gap-0.5">
            {chartData.map((day) => (
              <div
                key={day.date}
                className={`flex-1 ${color} rounded-t hover:opacity-80 transition-opacity relative group`}
                style={{ height: `${Math.max(4, (day.value / maxValue) * 100)}%` }}
              >
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                  {formatValue(day.value)} - {day.date}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between text-xs text-gray-500">
            <span>{chartData[0]?.date}</span>
            <span>{chartData[chartData.length - 1]?.date}</span>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{data?.total_leaflets || 0}</p>
              <p className="text-sm text-gray-500">Total Leaflets</p>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 rounded-lg">
              <Package className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{data?.total_products || 0}</p>
              <p className="text-sm text-gray-500">Total Products</p>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <DollarSign className="h-5 w-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">
                ${(data?.total_cost || 0).toFixed(2)}
              </p>
              <p className="text-sm text-gray-500">Total Cost</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <TrendChart
        chartData={leafletTrends}
        color="bg-blue-500"
        label="Leaflets Processed"
        formatValue={(v) => Math.round(v).toString()}
      />

      <TrendChart
        chartData={productTrends}
        color="bg-green-500"
        label="Products Extracted"
        formatValue={(v) => Math.round(v).toString()}
      />

      <TrendChart
        chartData={costTrends}
        color="bg-yellow-500"
        label="API Costs"
        formatValue={(v) => `$${v.toFixed(2)}`}
      />
    </div>
  );
}