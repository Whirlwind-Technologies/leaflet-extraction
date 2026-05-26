'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Webhook,
  Plus,
  Trash2,
  Play,
  Loader2,
  Copy,
  ChevronDown,
  ChevronUp,
  Pencil,
  History,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  getWebhooks,
  createWebhook,
  updateWebhook,
  deleteWebhook,
  testWebhook,
  getWebhookDeliveries,
  type Webhook as WebhookType,
  type WebhookDelivery,
  type WebhookDeliveryListResponse,
} from '@/lib/actions/settings';

// ---------------------------------------------------------------------------
// Webhook Event Configuration
// ---------------------------------------------------------------------------

interface WebhookEventConfig {
  value: string;
  label: string;
  description: string;
}

interface WebhookEventGroup {
  category: string;
  events: WebhookEventConfig[];
}

const WEBHOOK_EVENT_GROUPS: WebhookEventGroup[] = [
  {
    category: 'Leaflet Events',
    events: [
      {
        value: 'leaflet.uploaded',
        label: 'Leaflet Uploaded',
        description: 'When a new leaflet is uploaded',
      },
      {
        value: 'leaflet.processing.started',
        label: 'Processing Started',
        description: 'When extraction begins',
      },
      {
        value: 'leaflet.processing.completed',
        label: 'Processing Completed',
        description: 'When extraction completes successfully',
      },
      {
        value: 'leaflet.processing.failed',
        label: 'Processing Failed',
        description: 'When extraction fails',
      },
    ],
  },
  {
    category: 'Review Events',
    events: [
      {
        value: 'leaflet.review.required',
        label: 'Review Required',
        description: 'When products need human review',
      },
      {
        value: 'leaflet.review.completed',
        label: 'Review Completed',
        description: 'When all product reviews are done',
      },
    ],
  },
  {
    category: 'Product Events',
    events: [
      {
        value: 'product.updated',
        label: 'Product Updated',
        description: 'When a product is updated during review',
      },
      {
        value: 'product.approved',
        label: 'Product Approved',
        description: 'When a product is approved',
      },
      {
        value: 'product.rejected',
        label: 'Product Rejected',
        description: 'When a product is rejected',
      },
    ],
  },
  {
    category: 'Export Events',
    events: [
      {
        value: 'leaflet.export.ready',
        label: 'Export Ready',
        description: 'When an export file is available for download',
      },
    ],
  },
];

const ALL_EVENTS = WEBHOOK_EVENT_GROUPS.flatMap((g) => g.events.map((e) => e.value));

/** Map event value to display-friendly label */
function getEventLabel(eventValue: string): string {
  for (const group of WEBHOOK_EVENT_GROUPS) {
    const found = group.events.find((e) => e.value === eventValue);
    if (found) return found.label;
  }
  return eventValue;
}

// ---------------------------------------------------------------------------
// Test Result state per webhook
// ---------------------------------------------------------------------------

interface TestResult {
  success: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// URL validation helper
// ---------------------------------------------------------------------------

function isValidHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:';
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function WebhooksSettings() {
  const [webhooks, setWebhooks] = useState<WebhookType[]>([]);
  const [loading, setLoading] = useState(true);

  // Create dialog
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [secretVisible, setSecretVisible] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    url: '',
    description: '',
    events: ['leaflet.processing.completed'] as string[],
  });
  const [createError, setCreateError] = useState<string | null>(null);

  // Edit dialog
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookType | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [editForm, setEditForm] = useState({
    name: '',
    url: '',
    description: '',
    events: [] as string[],
  });
  const [editError, setEditError] = useState<string | null>(null);

  // Delete confirmation
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingWebhookId, setDeletingWebhookId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Test result per webhook
  const [testingWebhookId, setTestingWebhookId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});

  // Delivery log expansion
  const [expandedWebhookId, setExpandedWebhookId] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Fetch webhooks on mount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    fetchWebhooksData();
  }, []);

  const fetchWebhooksData = async () => {
    setLoading(true);
    try {
      const data = await getWebhooks();
      setWebhooks(data);
    } catch (error) {
      console.error('Failed to fetch webhooks:', error);
      toast.error('Failed to load webhooks');
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Create Webhook
  // ---------------------------------------------------------------------------

  const resetCreateForm = () => {
    setCreateForm({
      name: '',
      url: '',
      description: '',
      events: ['leaflet.processing.completed'],
    });
    setCreateError(null);
    setCreatedSecret(null);
    setSecretVisible(false);
  };

  const handleCreateWebhook = async () => {
    setCreateError(null);

    // Client-side validation
    if (!createForm.name.trim()) {
      setCreateError('Name is required');
      return;
    }
    if (!isValidHttpUrl(createForm.url)) {
      setCreateError('Please enter a valid URL starting with https:// or http://');
      return;
    }
    if (createForm.events.length === 0) {
      setCreateError('At least one event must be selected');
      return;
    }

    setIsCreating(true);
    try {
      const result = await createWebhook({
        name: createForm.name.trim(),
        url: createForm.url.trim(),
        description: createForm.description.trim() || undefined,
        events: createForm.events,
      });

      if (result.success && result.data) {
        setWebhooks([result.data.webhook, ...webhooks]);
        // Show secret in the dialog, don't close yet
        setCreatedSecret(result.data.secret);
        toast.success('Webhook created successfully');
      } else {
        setCreateError(result.error || 'Failed to create webhook');
      }
    } catch (error) {
      console.error('Failed to create webhook:', error);
      setCreateError('An unexpected error occurred');
    } finally {
      setIsCreating(false);
    }
  };

  const handleCreateDialogClose = (open: boolean) => {
    if (!open) {
      resetCreateForm();
    }
    setCreateDialogOpen(open);
  };

  // ---------------------------------------------------------------------------
  // Edit Webhook
  // ---------------------------------------------------------------------------

  const openEditDialog = (webhook: WebhookType) => {
    setEditingWebhook(webhook);
    setEditForm({
      name: webhook.name,
      url: webhook.url,
      description: webhook.description || '',
      events: [...webhook.events],
    });
    setEditError(null);
    setEditDialogOpen(true);
  };

  const handleUpdateWebhook = async () => {
    if (!editingWebhook) return;
    setEditError(null);

    if (!editForm.name.trim()) {
      setEditError('Name is required');
      return;
    }
    if (!isValidHttpUrl(editForm.url)) {
      setEditError('Please enter a valid URL starting with https:// or http://');
      return;
    }
    if (editForm.events.length === 0) {
      setEditError('At least one event must be selected');
      return;
    }

    setIsUpdating(true);
    try {
      const result = await updateWebhook(editingWebhook.id, {
        name: editForm.name.trim(),
        url: editForm.url.trim(),
        description: editForm.description.trim() || undefined,
        events: editForm.events,
      });

      if (result.success && result.data) {
        setWebhooks(webhooks.map((w) => (w.id === editingWebhook.id ? result.data! : w)));
        setEditDialogOpen(false);
        toast.success('Webhook updated');
      } else {
        setEditError(result.error || 'Failed to update webhook');
      }
    } catch (error) {
      console.error('Failed to update webhook:', error);
      setEditError('An unexpected error occurred');
    } finally {
      setIsUpdating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Toggle Active
  // ---------------------------------------------------------------------------

  const handleToggleActive = async (id: string, currentActive: boolean) => {
    try {
      const result = await updateWebhook(id, { is_active: !currentActive });
      if (result.success && result.data) {
        setWebhooks(webhooks.map((w) => (w.id === id ? result.data! : w)));
        toast.success(`Webhook ${!currentActive ? 'enabled' : 'disabled'}`);
      } else {
        toast.error(result.error || 'Failed to update webhook');
      }
    } catch {
      toast.error('Failed to update webhook');
    }
  };

  // ---------------------------------------------------------------------------
  // Delete Webhook
  // ---------------------------------------------------------------------------

  const openDeleteDialog = (id: string) => {
    setDeletingWebhookId(id);
    setDeleteDialogOpen(true);
  };

  const handleDeleteWebhook = async () => {
    if (!deletingWebhookId) return;
    setIsDeleting(true);
    try {
      const result = await deleteWebhook(deletingWebhookId);
      if (result.success) {
        setWebhooks(webhooks.filter((w) => w.id !== deletingWebhookId));
        if (expandedWebhookId === deletingWebhookId) {
          setExpandedWebhookId(null);
        }
        toast.success('Webhook deleted');
      } else {
        toast.error(result.error || 'Failed to delete webhook');
      }
    } catch {
      toast.error('Failed to delete webhook');
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
      setDeletingWebhookId(null);
    }
  };

  // ---------------------------------------------------------------------------
  // Test Webhook
  // ---------------------------------------------------------------------------

  const handleTestWebhook = async (id: string) => {
    setTestingWebhookId(id);
    // Clear previous test result for this webhook
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    try {
      const result = await testWebhook(id);
      if (result.success && result.data) {
        setTestResults((prev) => ({
          ...prev,
          [id]: { success: result.data!.success, message: result.data!.message },
        }));
      } else {
        setTestResults((prev) => ({
          ...prev,
          [id]: { success: false, message: result.error || 'Test failed' },
        }));
      }
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [id]: { success: false, message: 'Failed to send test webhook' },
      }));
    } finally {
      setTestingWebhookId(null);
    }
  };

  // ---------------------------------------------------------------------------
  // Toggle event in form
  // ---------------------------------------------------------------------------

  const toggleCreateEvent = (event: string) => {
    setCreateForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  const toggleEditEvent = (event: string) => {
    setEditForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  const selectAllCreateEvents = () => setCreateForm((prev) => ({ ...prev, events: [...ALL_EVENTS] }));
  const deselectAllCreateEvents = () => setCreateForm((prev) => ({ ...prev, events: [] }));
  const selectAllEditEvents = () => setEditForm((prev) => ({ ...prev, events: [...ALL_EVENTS] }));
  const deselectAllEditEvents = () => setEditForm((prev) => ({ ...prev, events: [] }));

  // ---------------------------------------------------------------------------
  // Copy to clipboard
  // ---------------------------------------------------------------------------

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard');
    } catch {
      toast.error('Failed to copy');
    }
  };

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  /** The event checkbox grid used in both create and edit forms */
  function renderEventCheckboxes(
    selectedEvents: string[],
    toggleFn: (event: string) => void,
    selectAllFn: () => void,
    deselectAllFn: () => void
  ) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label>Events</Label>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={selectAllFn} className="text-xs h-7">
              Select All
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={deselectAllFn} className="text-xs h-7">
              Deselect All
            </Button>
          </div>
        </div>
        <div className="max-h-64 overflow-y-auto space-y-4 pr-1">
          {WEBHOOK_EVENT_GROUPS.map((group) => (
            <div key={group.category}>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                {group.category}
              </h4>
              <div className="space-y-1.5">
                {group.events.map((event) => (
                  <label
                    key={event.value}
                    className={cn(
                      'flex items-start gap-3 p-2.5 border rounded-lg cursor-pointer transition-colors',
                      selectedEvents.includes(event.value)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-slate-200 hover:bg-slate-50'
                    )}
                  >
                    <Checkbox
                      checked={selectedEvents.includes(event.value)}
                      onCheckedChange={() => toggleFn(event.value)}
                      className="mt-0.5"
                      aria-label={event.label}
                    />
                    <div className="min-w-0">
                      <div className="font-medium text-sm text-slate-800">{event.label}</div>
                      <div className="text-xs text-slate-500">{event.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
        {selectedEvents.length === 0 && (
          <p className="text-xs text-red-600">At least one event must be selected</p>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main JSX
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      <Card className="border-slate-200">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2 text-slate-800">
              <Webhook className="h-5 w-5 text-slate-600" />
              Webhooks
            </CardTitle>
            <CardDescription className="text-slate-500">
              Receive real-time notifications when events occur in your account
            </CardDescription>
          </div>
          <Dialog open={createDialogOpen} onOpenChange={handleCreateDialogClose}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Webhook
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create Webhook</DialogTitle>
                <DialogDescription>
                  Add a new webhook endpoint to receive event notifications
                </DialogDescription>
              </DialogHeader>

              {/* If the secret has been created, show it instead of the form */}
              {createdSecret ? (
                <div className="space-y-4">
                  <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-amber-800">
                          Save your signing secret
                        </p>
                        <p className="text-sm text-amber-700 mt-1">
                          This secret is shown only once. Use it to verify webhook signatures
                          with HMAC-SHA256.
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Signing Secret</Label>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 p-3 bg-slate-100 border border-slate-200 rounded text-sm font-mono break-all">
                        {secretVisible ? createdSecret : '••••••••••••••••••••••••'}
                      </code>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSecretVisible(!secretVisible)}
                        aria-label={secretVisible ? 'Hide secret' : 'Show secret'}
                      >
                        {secretVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copyToClipboard(createdSecret)}
                        aria-label="Copy secret"
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button onClick={() => handleCreateDialogClose(false)}>Done</Button>
                  </DialogFooter>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="webhook-name">Name</Label>
                    <Input
                      id="webhook-name"
                      value={createForm.name}
                      onChange={(e) =>
                        setCreateForm({ ...createForm, name: e.target.value })
                      }
                      placeholder="e.g., Production Webhook"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="webhook-url">Endpoint URL</Label>
                    <Input
                      id="webhook-url"
                      type="url"
                      value={createForm.url}
                      onChange={(e) =>
                        setCreateForm({ ...createForm, url: e.target.value })
                      }
                      placeholder="https://yourapp.example.com/webhooks"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="webhook-description">Description (optional)</Label>
                    <Textarea
                      id="webhook-description"
                      value={createForm.description}
                      onChange={(e) =>
                        setCreateForm({ ...createForm, description: e.target.value })
                      }
                      placeholder="Describe the purpose of this webhook"
                      rows={2}
                    />
                  </div>

                  {renderEventCheckboxes(
                    createForm.events,
                    toggleCreateEvent,
                    selectAllCreateEvents,
                    deselectAllCreateEvents
                  )}

                  {createError && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                      {createError}
                    </div>
                  )}

                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => handleCreateDialogClose(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleCreateWebhook}
                      disabled={
                        isCreating ||
                        !createForm.name.trim() ||
                        !createForm.url.trim() ||
                        createForm.events.length === 0
                      }
                    >
                      {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                      Create Webhook
                    </Button>
                  </DialogFooter>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : webhooks.length === 0 ? (
            <div className="text-center py-12">
              <Webhook className="h-10 w-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-600 font-medium">No webhooks configured</p>
              <p className="text-sm text-slate-500 mt-1">
                Create one to receive real-time notifications about leaflet processing,
                product reviews, and exports.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {webhooks.map((webhook) => (
                <WebhookCard
                  key={webhook.id}
                  webhook={webhook}
                  isTesting={testingWebhookId === webhook.id}
                  testResult={testResults[webhook.id] ?? null}
                  isExpanded={expandedWebhookId === webhook.id}
                  onTest={() => handleTestWebhook(webhook.id)}
                  onToggleActive={() =>
                    handleToggleActive(webhook.id, webhook.is_active)
                  }
                  onEdit={() => openEditDialog(webhook)}
                  onDelete={() => openDeleteDialog(webhook.id)}
                  onToggleExpand={() =>
                    setExpandedWebhookId(
                      expandedWebhookId === webhook.id ? null : webhook.id
                    )
                  }
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Webhook Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Webhook</DialogTitle>
            <DialogDescription>
              Update your webhook endpoint configuration
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-webhook-name">Name</Label>
              <Input
                id="edit-webhook-name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-webhook-url">Endpoint URL</Label>
              <Input
                id="edit-webhook-url"
                type="url"
                value={editForm.url}
                onChange={(e) => setEditForm({ ...editForm, url: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-webhook-description">Description (optional)</Label>
              <Textarea
                id="edit-webhook-description"
                value={editForm.description}
                onChange={(e) =>
                  setEditForm({ ...editForm, description: e.target.value })
                }
                rows={2}
              />
            </div>

            {renderEventCheckboxes(
              editForm.events,
              toggleEditEvent,
              selectAllEditEvents,
              deselectAllEditEvents
            )}

            {editError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {editError}
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleUpdateWebhook}
                disabled={
                  isUpdating ||
                  !editForm.name.trim() ||
                  !editForm.url.trim() ||
                  editForm.events.length === 0
                }
              >
                {isUpdating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                Save Changes
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Webhook</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this webhook and all its delivery history.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteWebhook}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Webhook Documentation */}
      <Card className="border-slate-200">
        <CardHeader>
          <CardTitle className="text-base text-slate-800">Webhook Payload Format</CardTitle>
          <CardDescription className="text-slate-500">
            All webhooks are sent as HTTP POST requests with a JSON body
          </CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg text-sm overflow-x-auto">
{`{
  "event": "leaflet.processing.completed",
  "timestamp": "2026-02-07T12:00:00Z",
  "data": {
    "leaflet_id": "LEAF_2026_XYZ",
    "status": "completed",
    "total_products": 48,
    "auto_approved": 35,
    "review_required": 13
  }
}`}
          </pre>
          <p className="mt-3 text-sm text-slate-500">
            All webhooks include an{' '}
            <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">
              X-Webhook-Signature
            </code>{' '}
            header for request verification using HMAC-SHA256 with your signing secret.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WebhookCard — Individual webhook row with expandable delivery log
// ---------------------------------------------------------------------------

interface WebhookCardProps {
  webhook: WebhookType;
  isTesting: boolean;
  testResult: TestResult | null;
  isExpanded: boolean;
  onTest: () => void;
  onToggleActive: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggleExpand: () => void;
}

function WebhookCard({
  webhook,
  isTesting,
  testResult,
  isExpanded,
  onTest,
  onToggleActive,
  onEdit,
  onDelete,
  onToggleExpand,
}: WebhookCardProps) {
  return (
    <div
      className={cn(
        'border rounded-lg transition-colors',
        webhook.is_active ? 'border-slate-200' : 'border-slate-200 bg-slate-50/50'
      )}
    >
      {/* Main card content */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-medium text-slate-800">{webhook.name}</h4>
              <Badge variant={webhook.is_active ? 'default' : 'secondary'}>
                {webhook.is_active ? 'Active' : 'Inactive'}
              </Badge>
              {webhook.failure_count > 0 && (
                <Badge variant="destructive" className="text-xs">
                  {webhook.failure_count} consecutive failures
                </Badge>
              )}
            </div>
            <code className="text-sm text-slate-500 break-all block">{webhook.url}</code>
            {webhook.description && (
              <p className="text-sm text-slate-500">{webhook.description}</p>
            )}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center">
                  <Switch
                    checked={webhook.is_active}
                    onCheckedChange={() => onToggleActive()}
                    aria-label={webhook.is_active ? 'Disable webhook' : 'Enable webhook'}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent>
                {webhook.is_active ? 'Disable' : 'Enable'}
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onTest}
                  disabled={isTesting}
                  aria-label="Send test webhook"
                >
                  {isTesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Test</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onEdit}
                  aria-label="Edit webhook"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Edit</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onToggleExpand}
                  aria-label="View delivery history"
                >
                  <History className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delivery History</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onDelete}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  aria-label="Delete webhook"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete</TooltipContent>
            </Tooltip>
          </div>
        </div>

        {/* Event badges */}
        <div className="mt-3 flex flex-wrap gap-1">
          {webhook.events.map((event) => (
            <Badge key={event} variant="outline" className="text-xs">
              {getEventLabel(event)}
            </Badge>
          ))}
        </div>

        {/* Stats row */}
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-slate-500">Deliveries:</span>
            <span className="ml-1 font-medium text-slate-800">{webhook.total_deliveries}</span>
          </div>
          <div>
            <span className="text-slate-500">Failures:</span>
            <span className="ml-1 font-medium text-slate-800">{webhook.total_failures}</span>
          </div>
          <div>
            <span className="text-slate-500">Success Rate:</span>
            <span className="ml-1 font-medium text-slate-800">
              {webhook.total_deliveries > 0
                ? Math.round(
                    ((webhook.total_deliveries - webhook.total_failures) /
                      webhook.total_deliveries) *
                      100
                  )
                : 100}
              %
            </span>
          </div>
          <div>
            <span className="text-slate-500">Last Triggered:</span>
            <span className="ml-1 font-medium text-slate-800">
              {webhook.last_triggered_at
                ? new Date(webhook.last_triggered_at).toLocaleDateString()
                : 'Never'}
            </span>
          </div>
        </div>

        {/* Inline test result */}
        {testResult && (
          <div
            className={cn(
              'mt-3 p-2.5 rounded-lg text-sm flex items-center gap-2',
              testResult.success
                ? 'bg-green-50 border border-green-200 text-green-700'
                : 'bg-red-50 border border-red-200 text-red-700'
            )}
          >
            {testResult.success ? (
              <CheckCircle className="h-4 w-4 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{testResult.message}</span>
          </div>
        )}

        {/* Last error display */}
        {webhook.last_error && !testResult && (
          <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>Last error: {webhook.last_error}</span>
          </div>
        )}
      </div>

      {/* Expandable delivery log */}
      {isExpanded && (
        <div className="border-t border-slate-200">
          <DeliveryLogPanel webhookId={webhook.id} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delivery Log Panel
// ---------------------------------------------------------------------------

interface DeliveryLogPanelProps {
  webhookId: string;
}

function DeliveryLogPanel({ webhookId }: DeliveryLogPanelProps) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<WebhookDeliveryListResponse | null>(null);
  const [, setCurrentPage] = useState(1);
  const [expandedDeliveryId, setExpandedDeliveryId] = useState<string | null>(null);
  const pageSize = 10;

  const fetchDeliveries = useCallback(
    async (page: number) => {
      setLoading(true);
      try {
        const result = await getWebhookDeliveries(webhookId, page, pageSize);
        setData(result);
        setCurrentPage(page);
      } catch (error) {
        console.error('Failed to fetch deliveries:', error);
      } finally {
        setLoading(false);
      }
    },
    [webhookId]
  );

  useEffect(() => {
    fetchDeliveries(1);
  }, [fetchDeliveries]);

  if (loading && !data) {
    return (
      <div className="flex justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!data || data.deliveries.length === 0) {
    return (
      <div className="text-center py-6 text-slate-500 text-sm">
        <History className="h-6 w-6 text-slate-300 mx-auto mb-2" />
        No deliveries yet. Use the Test button to send a sample payload.
      </div>
    );
  }

  return (
    <div className={cn('relative', loading && 'opacity-60 pointer-events-none')}>
      <div className="px-4 pt-3 pb-1">
        <h4 className="text-sm font-medium text-slate-700">
          Delivery History ({data.total} total)
        </h4>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead>Event</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Response Time</TableHead>
              <TableHead>Timestamp</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.deliveries.map((delivery) => (
              <DeliveryRow
                key={delivery.id}
                delivery={delivery}
                isExpanded={expandedDeliveryId === delivery.id}
                onToggle={() =>
                  setExpandedDeliveryId(
                    expandedDeliveryId === delivery.id ? null : delivery.id
                  )
                }
              />
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {data.pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
          <span className="text-xs text-slate-500">
            Page {data.page} of {data.pages}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={data.page <= 1 || loading}
              onClick={() => fetchDeliveries(data.page - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={data.page >= data.pages || loading}
              onClick={() => fetchDeliveries(data.page + 1)}
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual Delivery Row
// ---------------------------------------------------------------------------

interface DeliveryRowProps {
  delivery: WebhookDelivery;
  isExpanded: boolean;
  onToggle: () => void;
}

function DeliveryRow({ delivery, isExpanded, onToggle }: DeliveryRowProps) {
  const statusCode = delivery.status_code;

  /** Color for the status code based on HTTP category */
  function getStatusColor(): string {
    if (!statusCode) return 'text-slate-500';
    if (statusCode >= 200 && statusCode < 300) return 'text-green-700 bg-green-50';
    if (statusCode >= 300 && statusCode < 400) return 'text-yellow-700 bg-yellow-50';
    return 'text-red-700 bg-red-50';
  }

  return (
    <>
      <TableRow
        className="cursor-pointer"
        onClick={onToggle}
        aria-expanded={isExpanded}
      >
        <TableCell className="w-10 pr-0">
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </TableCell>
        <TableCell>
          <Badge variant="outline" className="text-xs font-mono">
            {delivery.event_type}
          </Badge>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-2">
            {delivery.success ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <XCircle className="h-4 w-4 text-red-600" />
            )}
            {statusCode ? (
              <span
                className={cn(
                  'text-xs font-mono px-1.5 py-0.5 rounded',
                  getStatusColor()
                )}
              >
                {statusCode}
              </span>
            ) : (
              <span className="text-xs text-slate-400">No response</span>
            )}
          </div>
        </TableCell>
        <TableCell>
          {delivery.response_time_ms != null ? (
            <span className="text-sm text-slate-600 flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {delivery.response_time_ms}ms
            </span>
          ) : (
            <span className="text-sm text-slate-400">-</span>
          )}
        </TableCell>
        <TableCell>
          <span className="text-sm text-slate-600">
            {new Date(delivery.created_at).toLocaleString()}
          </span>
        </TableCell>
      </TableRow>

      {/* Expanded detail */}
      {isExpanded && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={5} className="py-0">
            <div className="py-3 pl-10 space-y-2">
              {delivery.error_message && (
                <div className="text-sm">
                  <span className="font-medium text-slate-600">Error: </span>
                  <span className="text-red-600">{delivery.error_message}</span>
                </div>
              )}
              {!delivery.error_message && delivery.success && (
                <p className="text-sm text-slate-500">
                  Delivered successfully in {delivery.response_time_ms}ms
                </p>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
