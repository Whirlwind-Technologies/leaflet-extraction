"use client";

import { useState, useEffect } from "react";
import { Check, ChevronsUpDown, Building, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Organization {
  id: string;
  name: string;
  role: string;
  status: string;
  member_count?: number;
}

interface OrganizationSwitcherProps {
  currentOrganization?: Organization;
  organizations?: Organization[];
  onSwitch?: (orgId: string) => void;
}

export function OrganizationSwitcher({
  currentOrganization,
  organizations = [],
  onSwitch,
}: OrganizationSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<Organization | undefined>(
    currentOrganization
  );

  useEffect(() => {
    setSelectedOrg(currentOrganization);
  }, [currentOrganization]);

  const handleSwitch = async (orgId: string) => {
    const org = organizations.find((o) => o.id === orgId);
    if (org) {
      setSelectedOrg(org);
      setIsOpen(false);
      if (onSwitch) {
        onSwitch(orgId);
      }
    }
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role.toLowerCase()) {
      case "owner":
        return "bg-[#2D3748] text-white border-[#2D3748]";
      case "admin":
        return "bg-[#5B8DBE] text-white border-[#5B8DBE]";
      case "member":
        return "bg-gray-100 text-gray-700 border-gray-300";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          className="w-full justify-between"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Building className="h-4 w-4 flex-shrink-0" />
            <span className="truncate">
              {selectedOrg?.name || "Select organization"}
            </span>
          </div>
          <ChevronsUpDown className="ml-2 h-4 w-4 flex-shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-[300px]" align="start">
        <DropdownMenuLabel>Organizations</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {organizations.length === 0 ? (
          <div className="px-2 py-6 text-center text-sm text-muted-foreground">
            No organizations found
          </div>
        ) : (
          organizations.map((org) => (
            <DropdownMenuItem
              key={org.id}
              onSelect={() => handleSwitch(org.id)}
              className="cursor-pointer"
            >
              <div className="flex items-center justify-between w-full gap-2">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <Check
                    className={cn(
                      "h-4 w-4 flex-shrink-0",
                      selectedOrg?.id === org.id ? "opacity-100" : "opacity-0"
                    )}
                  />
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-sm font-medium truncate">
                      {org.name}
                    </span>
                    {org.member_count !== undefined && (
                      <span className="text-xs text-muted-foreground">
                        {org.member_count} {org.member_count === 1 ? "member" : "members"}
                      </span>
                    )}
                  </div>
                </div>
                <Badge
                  variant="outline"
                  className={cn("text-xs flex-shrink-0", getRoleBadgeColor(org.role))}
                >
                  {org.role}
                </Badge>
              </div>
            </DropdownMenuItem>
          ))
        )}

        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer"
          onSelect={() => {
            window.location.href = "/settings/organization";
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Manage Organizations
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
