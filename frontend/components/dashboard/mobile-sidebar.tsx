"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  BarChart3, BookOpen, Building, ClipboardList, FileText, LayoutDashboard,
  Menu, Package, Settings, Upload, X, Shield, Brain, DollarSign,
  Archive, Cpu, Trash2, Users, ChevronDown, Store
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/types";
import { transitions } from "@/lib/design-system";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/products", label: "All Products", icon: Package },
  { href: "/review", label: "Review Queue", icon: ClipboardList },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/retailers", label: "Retailers", icon: Store },
  { href: "/api-docs", label: "API Docs", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Admin menu structure matching the main sidebar
const adminMenuItems = [
  {
    id: "dashboard",
    href: "/admin",
    label: "Admin Dashboard",
    icon: LayoutDashboard
  },
  {
    id: "users",
    label: "User & Access",
    icon: Users,
    children: [
      { href: "/admin/users", label: "User Management", icon: Users },
      { href: "/admin/registrations", label: "Registrations", icon: Shield },
      { href: "/admin/organizations", label: "Org Limits", icon: Building },
      { href: "/admin/deletion-requests", label: "Deletion Requests", icon: Trash2 },
    ]
  },
  {
    id: "vlm",
    label: "VLM System",
    icon: Brain,
    children: [
      { href: "/admin/vlm-models", label: "VLM Models", icon: Cpu },
      { href: "/admin/platform-providers", label: "VLM Providers", icon: Brain },
      { href: "/admin/provider-backups", label: "Provider Backups", icon: Archive },
    ]
  },
  {
    id: "monitoring",
    label: "Monitoring",
    icon: BarChart3,
    children: [
      { href: "/admin/usage-reports", label: "Usage Reports", icon: BarChart3 },
      { href: "/admin/budget-alerts", label: "Budget Alerts", icon: DollarSign },
      { href: "/admin/audit-logs", label: "Audit Logs", icon: FileText },
    ]
  },
];

interface MobileSidebarProps {
  user?: User;
}

export function MobileSidebar({ user }: MobileSidebarProps) {
  const [open, setOpen] = useState(false);
  const [expandedMenus, setExpandedMenus] = useState<string[]>([]);
  const pathname = usePathname();

  const toggleMenu = (id: string) => {
    setExpandedMenus(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    );
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={() => setOpen(true)}
      >
        <Menu className="h-6 w-6" />
      </Button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-50 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-full w-72 bg-gradient-to-b from-[#2D3748] to-[#374151] transform transition-transform duration-200 lg:hidden overflow-y-auto",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-700/50">
          <Link
            href="/dashboard"
            className="flex items-center gap-2"
            onClick={() => setOpen(false)}
          >
            <FileText className="h-6 w-6 text-white" strokeWidth={1.5} />
            <span className="font-light text-white text-lg tracking-wide">LeafXtract</span>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setOpen(false)}
            className="text-gray-300 hover:text-white hover:bg-gray-700/30"
          >
            <X className="h-5 w-5" strokeWidth={1.5} />
          </Button>
        </div>

        <nav className="sidebar-scroll p-3 pb-20 space-y-1 overflow-y-auto h-[calc(100vh-4rem)]">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  `flex items-center gap-3 px-3 py-2.5 rounded-md ${transitions.DEFAULT} font-light text-sm`,
                  isActive
                    ? "bg-[#5B8DBE]/90 text-white"
                    : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={1.5} />
                <span>{item.label}</span>
              </Link>
            );
          })}

          {/* Admin section - only for superusers */}
          {user?.is_superuser && (
            <>
              <div className="px-3 pt-6 pb-2 text-[10px] font-light text-gray-500 uppercase tracking-wider">
                Admin
              </div>
              {adminMenuItems.map((item) => {
                const Icon = item.icon;
                const hasChildren = item.children && item.children.length > 0;
                const isExpanded = expandedMenus.includes(item.id);
                const isChildActive = hasChildren && item.children?.some(child => pathname === child.href);
                const isDirectActive = item.href && pathname === item.href;
                const isActive = isDirectActive || isChildActive;

                // Direct link (no children)
                if (!hasChildren && item.href) {
                  return (
                    <Link
                      key={item.id}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className={cn(
                        `flex items-center gap-3 px-3 py-2.5 rounded-md ${transitions.DEFAULT} font-light text-sm`,
                        isActive
                          ? "bg-[#5B8DBE]/90 text-white"
                          : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
                      )}
                    >
                      <Icon className="h-5 w-5" strokeWidth={1.5} />
                      <span>{item.label}</span>
                    </Link>
                  );
                }

                // Menu with children (expandable)
                return (
                  <div key={item.id}>
                    <button
                      onClick={() => toggleMenu(item.id)}
                      className={cn(
                        `w-full flex items-center gap-3 px-3 py-2.5 rounded-md ${transitions.DEFAULT} font-light text-sm`,
                        isActive
                          ? "bg-[#5B8DBE]/90 text-white"
                          : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
                      )}
                    >
                      <Icon className="h-5 w-5" strokeWidth={1.5} />
                      <span className="flex-1 text-left">{item.label}</span>
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 transition-transform duration-200",
                          isExpanded ? "rotate-180" : ""
                        )}
                        strokeWidth={1.5}
                      />
                    </button>

                    {/* Expandable children */}
                    {isExpanded && item.children && (
                      <div className="ml-4 mt-1 space-y-1 border-l border-gray-700/50 pl-3">
                        {item.children.map((child) => {
                          const ChildIcon = child.icon;
                          const isChildItemActive = pathname === child.href;

                          return (
                            <Link
                              key={child.href}
                              href={child.href}
                              onClick={() => setOpen(false)}
                              className={cn(
                                `flex items-center gap-3 px-3 py-2 rounded-md ${transitions.DEFAULT} font-light text-sm`,
                                isChildItemActive
                                  ? "bg-[#5B8DBE]/90 text-white"
                                  : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
                              )}
                            >
                              <ChildIcon className="h-4 w-4" strokeWidth={1.5} />
                              <span>{child.label}</span>
                            </Link>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}
        </nav>
      </aside>
    </>
  );
}