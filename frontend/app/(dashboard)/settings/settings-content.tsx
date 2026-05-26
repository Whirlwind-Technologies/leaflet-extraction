'use client';

import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ApiKeysSettings } from '@/components/settings/api-keys-settings';
import { WebhooksSettings } from '@/components/settings/webhooks-settings';
import { VlmProvidersSettings } from '@/components/settings/vlm-providers-settings';
import { AccountSettings } from '@/components/settings/account-settings';

const VALID_TABS = ['account', 'api-keys', 'webhooks', 'vlm-providers'];
const TAB_ALIASES: Record<string, string> = { 'ai-providers': 'vlm-providers' };

function resolveTab(param: string | null): string {
  if (!param) return 'account';
  const resolved = TAB_ALIASES[param] || param;
  return VALID_TABS.includes(resolved) ? resolved : 'account';
}

export function SettingsContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab');

  const [activeTab, setActiveTab] = useState(resolveTab(tabParam));

  // Update tab when URL parameter changes
  useEffect(() => {
    if (tabParam) {
      const resolved = resolveTab(tabParam);
      Promise.resolve().then(() => setActiveTab(resolved));
    }
  }, [tabParam]);

  return (
    <div className="container mx-auto pb-6 max-w-7xl">
      <div className="mb-10">
        <h1 className="text-2xl font-semibold text-slate-800 mb-1 tracking-tight">Settings</h1>
        <p className="text-sm font-light text-slate-500">
          Manage your account, API keys, webhooks, and AI providers
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="account">Account</TabsTrigger>
          <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          <TabsTrigger value="webhooks">Webhooks</TabsTrigger>
          <TabsTrigger value="vlm-providers">AI Providers</TabsTrigger>
        </TabsList>

        <TabsContent value="account">
          <AccountSettings />
        </TabsContent>

        <TabsContent value="api-keys">
          <ApiKeysSettings />
        </TabsContent>

        <TabsContent value="webhooks">
          <WebhooksSettings />
        </TabsContent>

        <TabsContent value="vlm-providers">
          <VlmProvidersSettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
