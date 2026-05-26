"use client";

import { useState, useEffect } from "react";
import { Check, ChevronsUpDown, Plus, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Retailer } from "@/lib/types";
import { getRetailers } from "@/lib/actions/retailers";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface RetailerSelectProps {
  value: string;
  onSelect: (retailer: Retailer | null) => void;
  onAddNew: () => void;
  disabled?: boolean;
}

export function RetailerSelect({
  value,
  onSelect,
  onAddNew,
  disabled,
}: RetailerSelectProps) {
  const [open, setOpen] = useState(false);
  const [retailers, setRetailers] = useState<Retailer[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadRetailers = async () => {
    setIsLoading(true);
    try {
      const data = await getRetailers({ is_active: true });
      setRetailers(data);
    } catch (error) {
      console.error("Failed to load retailers:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRetailers();
  }, []);

  // Refresh retailers when popover opens
  useEffect(() => {
    if (open) {
      loadRetailers();
    }
  }, [open]);

  const handleSelect = (retailerName: string) => {
    if (retailerName === value) {
      // Deselect if clicking same item
      onSelect(null);
    } else {
      const retailer = retailers.find((r) => r.name === retailerName);
      if (retailer) {
        onSelect(retailer);
      }
    }
    setOpen(false);
  };

  const handleAddNew = () => {
    setOpen(false);
    onAddNew();
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between font-normal"
          disabled={disabled}
        >
          {isLoading ? (
            <span className="text-slate-400">Loading...</span>
          ) : value ? (
            <span className="truncate">{value}</span>
          ) : (
            <span className="text-slate-400">Select retailer...</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[300px] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search retailers..." />
          <CommandList>
            {isLoading ? (
              <div className="py-6 text-center">
                <Loader2 className="h-6 w-6 animate-spin mx-auto text-slate-400" />
              </div>
            ) : (
              <>
                <CommandEmpty>No retailer found.</CommandEmpty>
                <CommandGroup>
                  {retailers.map((retailer) => (
                    <CommandItem
                      key={retailer.id}
                      value={retailer.name}
                      onSelect={handleSelect}
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4",
                          value === retailer.name ? "opacity-100" : "opacity-0"
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="truncate">{retailer.name}</div>
                        {(retailer.country || retailer.currency) && (
                          <div className="text-xs text-slate-500">
                            {[retailer.country, retailer.currency]
                              .filter(Boolean)
                              .join(" / ")}
                          </div>
                        )}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
                <CommandSeparator />
                <CommandGroup>
                  <CommandItem onSelect={handleAddNew} className="text-blue-600">
                    <Plus className="mr-2 h-4 w-4" />
                    Add new retailer...
                  </CommandItem>
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
