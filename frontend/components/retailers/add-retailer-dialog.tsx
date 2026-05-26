"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import type { Retailer, RetailerCreate } from "@/lib/types";
import { createRetailer } from "@/lib/actions/retailers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

interface AddRetailerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (retailer: Retailer) => void;
}

export function AddRetailerDialog({
  open,
  onOpenChange,
  onSuccess,
}: AddRetailerDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [formData, setFormData] = useState<RetailerCreate>({
    name: "",
    country: "",
    currency: "",
    language: "",
    logo_url: "",
    external_id: "",
  });

  const resetForm = () => {
    setFormData({
      name: "",
      country: "",
      currency: "",
      language: "",
      logo_url: "",
      external_id: "",
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error("Retailer name is required");
      return;
    }

    startTransition(async () => {
      const result = await createRetailer({
        name: formData.name.trim(),
        country: formData.country?.trim() || undefined,
        currency: formData.currency?.trim() || undefined,
        language: formData.language?.trim() || undefined,
        logo_url: formData.logo_url?.trim() || undefined,
        external_id: formData.external_id?.trim() || undefined,
      });

      if (result.success && result.data) {
        toast.success(`Retailer "${result.data.name}" created`);
        onSuccess(result.data);
        resetForm();
      } else {
        toast.error(result.error || "Failed to create retailer");
      }
    });
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      resetForm();
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Add New Retailer</DialogTitle>
          <DialogDescription>
            Add a new retailer with default metadata settings.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g., SuperMart"
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="country">Country</Label>
              <Select
                value={formData.country}
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
                <SelectTrigger id="country">
                  <SelectValue placeholder="Select a country" />
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
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={formData.currency}
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
                <Label htmlFor="language">Language</Label>
                <Input
                  id="language"
                  value={formData.language}
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
              <Label htmlFor="logo_url">Logo URL (optional)</Label>
              <Input
                id="logo_url"
                value={formData.logo_url}
                onChange={(e) =>
                  setFormData({ ...formData, logo_url: e.target.value })
                }
                placeholder="https://example.com/logo.png"
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="external_id">External ID (optional)</Label>
              <Input
                id="external_id"
                value={formData.external_id}
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
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isPending || !formData.name.trim()}
              style={{ backgroundColor: colors.primaryBrandBlue }}
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Retailer"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
