import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import { SettingsContent } from './settings-content';

function SettingsFallback() {
  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-10">
        <h1 className="text-2xl font-semibold text-slate-800 mb-1 tracking-tight">Settings</h1>
        <p className="text-sm font-light text-slate-500">
          Manage your account, API keys, webhooks, and AI providers
        </p>
      </div>
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<SettingsFallback />}>
      <SettingsContent />
    </Suspense>
  );
}
