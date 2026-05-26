"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import type { Retailer, RetailerUpdate } from "@/lib/types";
import { updateRetailer } from "@/lib/actions/retailers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { brandColors as colors } from "@/lib/brand-colors";

// Balkans/Adriatic region countries with their default currency and language
const BALKANS_COUNTRIES = [
  { code: "SI", name: "Slovenia", currency: "EUR", language: "sl" },
  { code: "HR", name: "Croatia", currency: "EUR", language: "hr" },
  { code: "RS", name: "Serbia", currency: "RSD", language: "sr" },
  { code: "BA", name: "Bosnia and Herzegovina", currency: "BAM", language: "bs" },
  { code: "ME", name: "Montenegro", currency: "EUR", language: "sr" },
  { code: "MK", name: "North Macedonia", currency: "MKD", language: "mk" },
  { code: "AL", name: "Albania", currency: "ALL", language: "sq" },
  { code: "XK", name: "Kosovo", currency: "EUR", language: "sq" },
  { code: "BG", name: "Bulgaria", currency: "BGN", language: "bg" },
  { code: "RO", name: "Romania", currency: "RON", language: "ro" },
  { code: "GR", name: "Greece", currency: "EUR", language: "el" },
  { code: "IT", name: "Italy", currency: "EUR", language: "it" },
  { code: "AT", name: "Austria", currency: "EUR", language: "de" },
  { code: "HU", name: "Hungary", currency: "HUF", language: "hu" },
] as const;

interface EditRetailerDialogProps {
  retailer: Retailer | null;
  onOpenChange: (open: boolean) => void;
  onSuccess: (retailer: Retailer) => void;
}

export function EditRetailerDialog({
  retailer,
  onOpenChange,
  onSuccess,
}: EditRetailerDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [formData, setFormData] = useState<RetailerUpdate>({});

  // Sync form data when retailer prop changes (adjust state during render pattern)
  const [prevRetailerId, setPrevRetailerId] = useState<string | null>(retailer?.id ?? null);
  if (retailer && retailer.id !== prevRetailerId) {
    setPrevRetailerId(retailer.id);
    setFormData({
      name: retailer.name,
      country: retailer.country || "",
      currency: retailer.currency || "",
      language: retailer.language || "",
      logo_url: retailer.logo_url || "",
      external_id: retailer.external_id || "",
      is_active: retailer.is_active,
    });
  } else if (!retailer && prevRetailerId !== null) {
    setPrevRetailerId(null);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!retailer) return;

    if (!formData.name?.trim()) {
      toast.error("Retailer name is required");
      return;
    }

    startTransition(async () => {
      const result = await updateRetailer(retailer.id, {
        name: formData.name?.trim(),
        country: formData.country?.trim() || undefined,
        currency: formData.currency?.trim() || undefined,
        language: formData.language?.trim() || undefined,
        logo_url: formData.logo_url?.trim() || undefined,
        external_id: formData.external_id?.trim() || undefined,
        is_active: formData.is_active,
      });

      if (result.success && result.data) {
        toast.success("Retailer updated");
        onSuccess(result.data);
      } else {
        toast.error(result.error || "Failed to update retailer");
      }
    });
  };

  return (
    <Dialog open={!!retailer} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit Retailer</DialogTitle>
          <DialogDescription>
            Update retailer information and defaults.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="edit-name"
                value={formData.name || ""}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-country">Country</Label>
              <Select
                value={formData.country || ""}
                onValueChange={(value) => {
                  const country = BALKANS_COUNTRIES.find((c) => c.code === value);
                  if (country) {
                    setFormData({
                      ...formData,
                      country: country.code,
                      currency: country.currency,
                      language: country.language,
                    });
                  }
                }}
                disabled={isPending}
              >
                <SelectTrigger id="edit-country">
                  <SelectValue placeholder="Select a country">
                    {formData.country &&
                      (BALKANS_COUNTRIES.find(c => c.code === formData.country)?.name || formData.country)
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {BALKANS_COUNTRIES.map((country) => (
                    <SelectItem key={country.code} value={country.code}>
                      {country.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-currency">Currency</Label>
                <Input
                  id="edit-currency"
                  value={formData.currency || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value.toUpperCase() })
                  }
                  placeholder="Auto-populated"
                  maxLength={3}
                  disabled={isPending}
                  className="bg-gray-50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-language">Language</Label>
                <Input
                  id="edit-language"
                  value={formData.language || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, language: e.target.value.toLowerCase() })
                  }
                  placeholder="Auto-populated"
                  maxLength={5}
                  disabled={isPending}
                  className="bg-gray-50"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-logo_url">Logo URL</Label>
              <Input
                id="edit-logo_url"
                value={formData.logo_url || ""}
                onChange={(e) =>
                  setFormData({ ...formData, logo_url: e.target.value })
                }
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-external_id">External ID</Label>
              <Input
                id="edit-external_id"
                value={formData.external_id || ""}
                onChange={(e) =>
                  setFormData({ ...formData, external_id: e.target.value })
                }
                placeholder="e.g., ERP-12345"
                disabled={isPending}
              />
              <p className="text-xs text-slate-500">
                Identifier used for integration with external systems
              </p>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="edit-is_active">Active</Label>
              <Switch
                id="edit-is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, is_active: checked })
                }
                disabled={isPending}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isPending || !formData.name?.trim()}
              style={{ backgroundColor: colors.primaryBrandBlue }}
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
