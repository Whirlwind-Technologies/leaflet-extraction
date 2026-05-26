'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckCircle, AlertTriangle, TrendingUp, Loader2 } from 'lucide-react';
import { getQualityMetrics, type QualityMetrics as QualityMetricsData } from '@/lib/actions/analytics';

interface QualityMetricsProps {
  period: number;
}

export function QualityMetrics({ period }: QualityMetricsProps) {
  const [loading, setLoading] = useState(true);
  const [quality, setQuality] = useState<QualityMetricsData | null>(null);

  useEffect(() => {
    const fetchQuality = async () => {
      setLoading(true);
      try {
        const data = await getQualityMetrics(period);
        setQuality(data);
      } catch (error) {
        console.error('Failed to fetch quality:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchQuality();
  }, [period]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  const metrics = [
    { 
      label: 'Extraction Success Rate', 
      value: quality?.extraction_success_rate || 0, 
      color: 'bg-green-500',
      icon: CheckCircle,
      description: 'Percentage of leaflets successfully processed'
    },
    { 
      label: 'Auto-Approval Rate', 
      value: quality?.auto_approval_rate || 0, 
      color: 'bg-blue-500',
      icon: TrendingUp,
      description: 'Products approved without manual review'
    },
    { 
      label: 'Validation Pass Rate', 
      value: quality?.validation_pass_rate || 0, 
      color: 'bg-purple-500',
      icon: CheckCircle,
      description: 'Products passing all validation rules'
    },
    { 
      label: 'Average Confidence', 
      value: quality?.avg_confidence || 0, 
      color: 'bg-indigo-500',
      icon: TrendingUp,
      description: 'Average extraction confidence score'
    },
    { 
      label: 'Error Rate', 
      value: quality?.error_rate || 0, 
      color: 'bg-red-500',
      icon: AlertTriangle,
      description: 'Percentage of products with errors'
    },
    { 
      label: 'Correction Rate', 
      value: quality?.correction_rate || 0, 
      color: 'bg-yellow-500',
      icon: AlertTriangle,
      description: 'Products requiring manual correction'
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.label}>
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Icon className={`h-5 w-5 ${
                    metric.color.replace('bg-', 'text-').replace('500', '600')
                  }`} />
                  <span className="font-medium">{metric.label}</span>
                </div>
                <div className="text-3xl font-bold mb-2">{metric.value.toFixed(1)}%</div>
                <div className="h-2 bg-gray-200 rounded-full mb-2">
                  <div
                    className={`h-full ${metric.color} rounded-full transition-all`}
                    style={{ width: `${Math.min(metric.value, 100)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-500">{metric.description}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quality Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h4 className="font-medium text-green-600 flex items-center gap-2">
                <CheckCircle className="h-4 w-4" />
                Strengths
              </h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>• High extraction success rate ({(quality?.extraction_success_rate || 0).toFixed(1)}%)</li>
                <li>• Strong average confidence ({(quality?.avg_confidence || 0).toFixed(1)}%)</li>
                <li>• Good validation pass rate ({(quality?.validation_pass_rate || 0).toFixed(1)}%)</li>
              </ul>
            </div>
            <div className="space-y-4">
              <h4 className="font-medium text-yellow-600 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Areas for Improvement
              </h4>
              <ul className="space-y-2 text-sm text-gray-600">
                {quality?.improvement_suggestions?.length ? (
                  quality.improvement_suggestions.map((suggestion, i) => (
                    <li key={i}>• {suggestion}</li>
                  ))
                ) : (
                  <>
                    <li>• Increase auto-approval rate (currently {(quality?.auto_approval_rate || 0).toFixed(1)}%)</li>
                    <li>• Reduce correction rate (currently {(quality?.correction_rate || 0).toFixed(1)}%)</li>
                    <li>• Lower error rate (currently {(quality?.error_rate || 0).toFixed(1)}%)</li>
                  </>
                )}
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}