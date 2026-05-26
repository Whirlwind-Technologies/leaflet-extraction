'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Key,
  Plus,
  Copy,
  Trash2,
  Loader2,
  Check,
  AlertCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  getApiKeys,
  createApiKey,
  revokeApiKey,
  type ApiKey,
} from '@/lib/actions/settings';

const AVAILABLE_SCOPES = [
  { value: 'read', label: 'Read', description: 'Read leaflets and products' },
  { value: 'write', label: 'Write', description: 'Create and update resources' },
  { value: 'upload', label: 'Upload', description: 'Upload new leaflets' },
  { value: 'export', label: 'Export', description: 'Export data' },
  { value: 'delete', label: 'Delete', description: 'Delete resources' },
];

export function ApiKeysSettings() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [, setIsCreating] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newKeyData, setNewKeyData] = useState({
    name: '',
    scopes: ['read'],
    rate_limit: 60,
    expires_in_days: undefined as number | undefined,
  });
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    fetchApiKeysData();
  }, []);

  const fetchApiKeysData = async () => {
    setLoading(true);
    try {
      const keys = await getApiKeys();
      setApiKeys(keys);
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
      toast.error('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    setIsCreating(true);
    try {
      const result = await createApiKey({
        name: newKeyData.name,
        scopes: newKeyData.scopes,
        rate_limit: newKeyData.rate_limit,
        expires_in_days: newKeyData.expires_in_days,
      });
      
      if (result.success && result.data) {
        setCreatedKey(result.data.plain_key);
        setApiKeys([result.data.api_key, ...apiKeys]);
        toast.success('API key created successfully');
      } else {
        toast.error(result.error || 'Failed to create API key');
      }
    } catch (error) {
      console.error('Failed to create API key:', error);
      toast.error('An error occurred');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(key);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleRevokeKey = async (id: string) => {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
      return;
    }
    
    try {
      const result = await revokeApiKey(id);
      if (result.success) {
        setApiKeys(apiKeys.filter(k => k.id !== id));
        toast.success('API key revoked');
      } else {
        toast.error(result.error || 'Failed to revoke key');
      }
    } catch {
      toast.error('Failed to revoke API key');
    }
  };

  const toggleScope = (scope: string) => {
    const scopes = newKeyData.scopes.includes(scope)
      ? newKeyData.scopes.filter(s => s !== scope)
      : [...newKeyData.scopes, scope];
    setNewKeyData({ ...newKeyData, scopes });
  };

  return (
    <div className="space-y-6">
      <Card className="border-slate-200">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2 text-slate-800">
              <Key className="h-5 w-5 text-slate-600" />
              API Keys
            </CardTitle>
            <CardDescription className="text-slate-500">
              Manage API keys for programmatic access to the platform.{' '}
              <a href="/api-docs" className="text-blue-600 hover:underline">
                View API documentation →
              </a>
            </CardDescription>
          </div>
          <Dialog open={createDialogOpen} onOpenChange={(open) => {
            setCreateDialogOpen(open);
            if (!open) {
              setCreatedKey(null);
              setNewKeyData({
                name: '',
                scopes: ['read'],
                rate_limit: 60,
                expires_in_days: undefined,
              });
            }
          }}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create API Key
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>
                  {createdKey ? 'API Key Created' : 'Create API Key'}
                </DialogTitle>
                <DialogDescription>
                  {createdKey
                    ? 'Save this key now - it won\'t be shown again!'
                    : 'Create a new API key for your application'}
                </DialogDescription>
              </DialogHeader>
              
              {createdKey ? (
                <div className="space-y-4">
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                    <div className="flex items-center gap-2 text-green-600 mb-2">
                      <Check className="h-4 w-4" />
                      <span className="font-medium">Key created successfully</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 p-2 bg-white rounded border text-sm break-all">
                        {createdKey}
                      </code>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCopyKey(createdKey)}
                      >
                        {copiedKey === createdKey ? (
                          <Check className="h-4 w-4" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex gap-2">
                    <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
                    <p className="text-sm text-yellow-700">
                      Make sure to copy your API key now. You won&apos;t be able to see it again!
                    </p>
                  </div>
                  <div className="pt-2 border-t">
                    <a 
                      href="/api-docs" 
                      className="inline-flex items-center text-sm text-primary hover:underline"
                    >
                      View API documentation to get started →
                    </a>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="key-name">Name</Label>
                    <Input
                      id="key-name"
                      value={newKeyData.name}
                      onChange={(e) => setNewKeyData({ ...newKeyData, name: e.target.value })}
                      placeholder="e.g., Production API Key"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Permissions</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {AVAILABLE_SCOPES.map((scope) => (
                        <label
                          key={scope.value}
                          className={`flex items-center gap-2 p-2 border rounded cursor-pointer hover:bg-slate-50 ${
                            newKeyData.scopes.includes(scope.value)
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-slate-200'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={newKeyData.scopes.includes(scope.value)}
                            onChange={() => toggleScope(scope.value)}
                            className="sr-only"
                          />
                          <div>
                            <div className="font-medium text-sm text-slate-800">{scope.label}</div>
                            <div className="text-xs text-slate-500">{scope.description}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="rate-limit">Rate Limit (req/min)</Label>
                      <Input
                        id="rate-limit"
                        type="number"
                        value={newKeyData.rate_limit}
                        onChange={(e) => setNewKeyData({ ...newKeyData, rate_limit: parseInt(e.target.value) })}
                        min={1}
                        max={1000}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="expires">Expires In</Label>
                      <Select
                        value={newKeyData.expires_in_days?.toString() || 'never'}
                        onValueChange={(v) => setNewKeyData({ ...newKeyData, expires_in_days: v === 'never' ? undefined : parseInt(v) })}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="never">Never</SelectItem>
                          <SelectItem value="30">30 days</SelectItem>
                          <SelectItem value="90">90 days</SelectItem>
                          <SelectItem value="365">1 year</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              )}
              
              <DialogFooter>
                {createdKey ? (
                  <Button onClick={() => setCreateDialogOpen(false)}>
                    Done
                  </Button>
                ) : (
                  <Button
                    onClick={handleCreateKey}
                    disabled={!newKeyData.name || newKeyData.scopes.length === 0}
                  >
                    Create Key
                  </Button>
                )}
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : apiKeys.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              No API keys yet. Create one to get started.
            </div>
          ) : (
            <div className="space-y-4">
              {apiKeys.map((key) => (
                <div
                  key={key.id}
                  className={`p-4 border rounded-lg ${
                    key.is_active ? 'border-slate-200' : 'border-red-200 bg-red-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-slate-800">{key.name}</h4>
                        {!key.is_active && (
                          <Badge variant="destructive" className="text-xs">
                            Revoked
                          </Badge>
                        )}
                      </div>
                      <code className="text-sm text-slate-500">{key.key_prefix}</code>
                    </div>
                    
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCopyKey(key.key_prefix)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                      {key.is_active && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleRevokeKey(key.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                  
                  <div className="mt-3 flex flex-wrap gap-1">
                    {key.scopes.map((scope) => (
                      <Badge key={scope} variant="secondary" className="text-xs">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                  
                  <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-slate-500">Rate Limit:</span>
                      <span className="ml-1 font-medium text-slate-800">{key.rate_limit}/min</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Total Requests:</span>
                      <span className="ml-1 font-medium text-slate-800">{key.total_requests.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Today:</span>
                      <span className="ml-1 font-medium text-slate-800">{key.requests_today}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Last Used:</span>
                      <span className="ml-1 font-medium text-slate-800">
                        {key.last_used_at
                          ? new Date(key.last_used_at).toLocaleDateString()
                          : 'Never'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}