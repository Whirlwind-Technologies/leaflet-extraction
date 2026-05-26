"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Loader2, Store } from "lucide-react";
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

interface QuickAddRetailerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (retailer: Retailer) => void;
  initialName?: string;
}

export function QuickAddRetailerModal({
  open,
  onOpenChange,
  onSuccess,
  initialName = "",
}: QuickAddRetailerModalProps) {
  const [isPending, startTransition] = useTransition();
  const [formData, setFormData] = useState<RetailerCreate>({
    name: initialName,
    country: "",
    currency: "",
    language: "",
  });

  // Reset form name when dialog opens (adjust state during render pattern)
  const [prevOpen, setPrevOpen] = useState(open);
  const [prevInitialName, setPrevInitialName] = useState(initialName);
  if ((open && !prevOpen) || (open && initialName !== prevInitialName)) {
    setPrevOpen(open);
    setPrevInitialName(initialName);
    setFormData((prev) => ({
      ...prev,
      name: initialName,
    }));
  } else if (open !== prevOpen) {
    setPrevOpen(open);
  }

  const resetForm = () => {
    setFormData({
      name: "",
      country: "",
      currency: "",
      language: "",
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
      });

      if (result.success && result.data) {
        toast.success(`Retailer "${result.data.name}" added`);
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
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Store className="h-5 w-5" />
            Quick Add Retailer
          </DialogTitle>
          <DialogDescription>
            Add a new retailer to use for this upload.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="quick-name">
                Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="quick-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g., SuperMart"
                disabled={isPending}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quick-country">Country</Label>
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
                <SelectTrigger id="quick-country">
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
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="quick-currency">Currency</Label>
                <Input
                  id="quick-currency"
                  value={formData.currency}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value.toUpperCase() })
                  }
                  placeholder="Auto"
                  maxLength={3}
                  disabled={isPending}
                  className="bg-gray-50"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="quick-language">Language</Label>
                <Input
                  id="quick-language"
                  value={formData.language}
                  onChange={(e) =>
                    setFormData({ ...formData, language: e.target.value.toLowerCase() })
                  }
                  placeholder="Auto"
                  maxLength={5}
                  disabled={isPending}
                  className="bg-gray-50"
                />
              </div>
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
                  Adding...
                </>
              ) : (
                "Add & Select"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
