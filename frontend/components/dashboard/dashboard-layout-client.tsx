"use client";

import { useState, createContext, useContext } from "react";
import { Header } from "@/components/dashboard/header";
import { Sidebar } from "@/components/dashboard/sidebar";
import type { User } from "@/lib/types";
import type { OrganizationSwitcherData } from "@/lib/actions/organizations";
import { cn } from "@/lib/utils";

interface SidebarContextType {
  isCollapsed: boolean;
  setIsCollapsed: (collapsed: boolean) => void;
}

const SidebarContext = createContext<SidebarContextType>({
  isCollapsed: false,
  setIsCollapsed: () => {},
});

export function useSidebar() {
  return useContext(SidebarContext);
}

interface DashboardLayoutClientProps {
  user: User;
  children: React.ReactNode;
  currentOrganization?: OrganizationSwitcherData;
  organizations?: OrganizationSwitcherData[];
}

export function DashboardLayoutClient({
  user,
  children,
  currentOrganization,
  organizations
}: DashboardLayoutClientProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed }}>
      <div className="min-h-screen bg-gray-50">
        <Sidebar user={user} />
        <div className={cn(
          "transition-[margin] duration-300 min-h-screen",
          isCollapsed ? "lg:ml-[68px]" : "lg:ml-64"
        )}>
          <Header
            user={user}
            currentOrganization={currentOrganization}
            organizations={organizations}
          />
          <main className="px-6 lg:px-8 pt-7 lg:pt-7 pb-6 lg:pb-8">{children}</main>
        </div>
      </div>
    </SidebarContext.Provider>
  );
}
