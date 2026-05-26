import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import { AnalyticsContent } from './analytics-content';

function AnalyticsFallback() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight text-slate-800">
            Analytics
          </h1>
          <p className="text-sm font-light text-slate-500">
            Review performance and extraction metrics
          </p>
        </div>
      </div>
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold mb-1 tracking-tight text-slate-800">
            Analytics
          </h1>
          <p className="text-sm font-light text-slate-500">
            Review performance and extraction metrics
          </p>
        </div>
      </div>

      <Suspense fallback={<AnalyticsFallback />}>
        <AnalyticsContent />
      </Suspense>
    </div>
  );
}
