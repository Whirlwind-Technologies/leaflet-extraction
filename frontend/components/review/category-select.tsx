"use client";

import { useState, useEffect, useMemo } from "react";
import { Check, ChevronsUpDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
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
import { getAllSystemCategories, type SystemCategory } from "@/lib/actions/categories";

interface CategorySelectProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

export function CategorySelect({
  value,
  onValueChange,
  placeholder = "Select category...",
  disabled = false,
  className,
}: CategorySelectProps) {
  const [open, setOpen] = useState(false);
  const [categories, setCategories] = useState<SystemCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [customValue, setCustomValue] = useState("");

  // Fetch categories on mount
  useEffect(() => {
    async function loadCategories() {
      setIsLoading(true);
      try {
        const cats = await getAllSystemCategories();
        setCategories(cats);
      } catch (error) {
        console.error("Failed to load categories:", error);
      } finally {
        setIsLoading(false);
      }
    }
    loadCategories();
  }, []);

  // Filter categories based on search
  const filteredCategories = useMemo(() => {
    if (!searchQuery) return categories;

    const query = searchQuery.toLowerCase();
    return categories.filter(
      (cat) =>
        cat.name.toLowerCase().includes(query) ||
        (cat.description && cat.description.toLowerCase().includes(query))
    );
  }, [categories, searchQuery]);

  // Split into specific and fallback categories
  const { specificCategories, fallbackCategories } = useMemo(() => {
    const specific = filteredCategories.filter((c) => !c.is_fallback);
    const fallback = filteredCategories.filter((c) => c.is_fallback);
    return { specificCategories: specific, fallbackCategories: fallback };
  }, [filteredCategories]);

  const displayValue = value || placeholder;

  const handleSelect = (categoryName: string) => {
    if (categoryName === "__custom__") {
      setShowCustomInput(true);
      setCustomValue(value);
    } else {
      onValueChange(categoryName);
      setOpen(false);
      setSearchQuery("");
    }
  };

  const handleCustomSubmit = () => {
    if (customValue.trim()) {
      onValueChange(customValue.trim());
    }
    setShowCustomInput(false);
    setOpen(false);
    setSearchQuery("");
  };

  const handleCustomCancel = () => {
    setShowCustomInput(false);
    setCustomValue("");
  };

  // Custom input mode
  if (showCustomInput) {
    return (
      <div className={cn("flex gap-2", className)}>
        <input
          type="text"
          value={customValue}
          onChange={(e) => setCustomValue(e.target.value)}
          placeholder="Enter custom category"
          className="flex h-8 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCustomSubmit();
            if (e.key === "Escape") handleCustomCancel();
          }}
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCustomCancel}
          className="h-8"
        >
          Cancel
        </Button>
        <Button
          size="sm"
          onClick={handleCustomSubmit}
          className="h-8"
        >
          OK
        </Button>
      </div>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled || isLoading}
          className={cn("h-8 w-full justify-between font-normal", className)}
        >
          {isLoading ? (
            <span className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Loading...
            </span>
          ) : (
            <span className={cn(!value && "text-muted-foreground")}>
              {displayValue}
            </span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[350px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search categories..."
            value={searchQuery}
            onValueChange={setSearchQuery}
          />
          <CommandList>
            <CommandEmpty>
              {searchQuery ? (
                <div className="py-4 text-center text-sm">
                  <p>No categories match &ldquo;{searchQuery}&rdquo;</p>
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => handleSelect("__custom__")}
                    className="mt-2"
                  >
                    Use custom category
                  </Button>
                </div>
              ) : (
                <p className="py-4 text-center text-sm">No categories found</p>
              )}
            </CommandEmpty>

            {/* Specific categories (most specific) */}
            {specificCategories.length > 0 && (
              <CommandGroup heading="Categories">
                {specificCategories.slice(0, 50).map((category) => (
                  <CommandItem
                    key={category.name}
                    value={category.name}
                    onSelect={() => handleSelect(category.name)}
                    className="flex flex-col items-start py-2"
                  >
                    <div className="flex w-full items-center">
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4",
                          value === category.name ? "opacity-100" : "opacity-0"
                        )}
                      />
                      <span className="flex-1 font-medium">{category.name}</span>
                    </div>
                    {category.description && (
                      <p className="ml-6 text-xs text-muted-foreground line-clamp-2">
                        {category.description}
                      </p>
                    )}
                  </CommandItem>
                ))}
                {specificCategories.length > 50 && (
                  <p className="px-2 py-1 text-xs text-muted-foreground text-center">
                    Type to search {specificCategories.length - 50} more...
                  </p>
                )}
              </CommandGroup>
            )}

            {/* Fallback categories */}
            {fallbackCategories.length > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup heading="Fallback Categories">
                  {fallbackCategories.slice(0, 20).map((category) => (
                    <CommandItem
                      key={category.name}
                      value={category.name}
                      onSelect={() => handleSelect(category.name)}
                      className="flex flex-col items-start py-2"
                    >
                      <div className="flex w-full items-center">
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            value === category.name ? "opacity-100" : "opacity-0"
                          )}
                        />
                        <span className="flex-1 font-medium">{category.name}</span>
                        <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                          Fallback
                        </span>
                      </div>
                      {category.description && (
                        <p className="ml-6 text-xs text-muted-foreground line-clamp-2">
                          {category.description}
                        </p>
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </>
            )}

            {/* Custom category option */}
            <CommandSeparator />
            <CommandGroup>
              <CommandItem
                value="__custom__"
                onSelect={() => handleSelect("__custom__")}
                className="py-2"
              >
                <Check className="mr-2 h-4 w-4 opacity-0" />
                <span className="text-primary">Enter custom category...</span>
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
