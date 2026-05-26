"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  BarChart3, BookOpen, Building, ClipboardList, FileText, LayoutDashboard,
  Package, ArrowUpFromLine, Settings, Shield, Brain, DollarSign, Archive,
  Cpu, Trash2, Users, MoreHorizontal, LucideIcon, Store
} from "lucide-react";
import type { User } from "@/lib/types";
import { transitions } from "@/lib/design-system";
import { useSidebar } from "./dashboard-layout-client";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload", icon: ArrowUpFromLine },
  { href: "/products", label: "All Products", icon: Package },
  { href: "/review", label: "Review Queue", icon: ClipboardList },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/retailers", label: "Retailers", icon: Store },
  { href: "/api-docs", label: "API Docs", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
];

// Grouped admin menu structure with submenus
interface AdminSubItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface AdminMenuItem {
  id: string;
  label: string;
  icon: LucideIcon;
  href?: string;
  children?: AdminSubItem[];
}

const adminMenuItems: AdminMenuItem[] = [
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

interface SidebarProps {
  user?: User;
}

// Submenu item component with flyout
function AdminMenuItemWithSubmenu({
  item,
  pathname,
  isCollapsed,
  openSubmenu,
  setOpenSubmenu,
}: {
  item: AdminMenuItem;
  pathname: string;
  isCollapsed: boolean;
  openSubmenu: string | null;
  setOpenSubmenu: (id: string | null) => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuTop, setMenuTop] = useState(0);
  const Icon = item.icon;
  const hasChildren = item.children && item.children.length > 0;
  const isOpen = openSubmenu === item.id;

  // Check if any child route is active
  const isChildActive = hasChildren && item.children?.some(child => pathname === child.href);
  const isDirectActive = item.href && pathname === item.href;
  const isActive = isDirectActive || isChildActive;

  // Toggle submenu on click
  const handleClick = () => {
    if (hasChildren) {
      // Compute position before opening the flyout
      if (!isOpen && menuRef.current) {
        setMenuTop(menuRef.current.getBoundingClientRect().top);
      }
      setOpenSubmenu(isOpen ? null : item.id);
    }
  };

  // Close submenu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        if (isOpen) {
          setOpenSubmenu(null);
        }
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, setOpenSubmenu]);

  // Direct link (no children)
  if (!hasChildren && item.href) {
    return (
      <Link
        href={item.href}
        title={isCollapsed ? item.label : undefined}
        className={cn(
          `flex items-center rounded-md ${transitions.DEFAULT} font-normal text-sm group relative py-2.5`,
          isCollapsed ? "justify-center" : "gap-3 px-3",
          isActive
            ? "bg-[#5B8DBE]/90 text-white"
            : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
        )}
      >
        <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.5} />
        {!isCollapsed && (
          <span className="whitespace-nowrap">
            {item.label}
          </span>
        )}
        {!isActive && (
          <div className="absolute inset-0 rounded-md opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-transparent via-white/5 to-transparent" />
        )}
      </Link>
    );
  }

  // Menu item with submenu
  return (
    <div
      ref={menuRef}
      className="relative"
    >
      <button
        onClick={handleClick}
        title={isCollapsed ? item.label : undefined}
        className={cn(
          `w-full flex items-center rounded-md ${transitions.DEFAULT} font-normal text-sm group relative py-2.5`,
          isCollapsed ? "justify-center" : "gap-3 px-3",
          isActive
            ? "bg-[#5B8DBE]/90 text-white"
            : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
        )}
      >
        <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.5} />
        {!isCollapsed && (
          <span className="whitespace-nowrap flex-1 text-left">
            {item.label}
          </span>
        )}
        {!isCollapsed && (
          <MoreHorizontal
            className="h-4 w-4 flex-shrink-0 opacity-60"
            strokeWidth={1.5}
          />
        )}
        {!isActive && (
          <div className="absolute inset-0 rounded-md opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-transparent via-white/5 to-transparent" />
        )}
      </button>

      {/* Flyout submenu - positioned at sidebar edge */}
      {isOpen && item.children && (
        <div
          className={cn(
            "fixed z-50 min-w-[220px] py-2 rounded-md shadow-xl border border-gray-700/50",
            "bg-gradient-to-b from-[#2D3748] to-[#374151]",
            "animate-in fade-in-0 zoom-in-95 duration-150"
          )}
          style={{
            left: isCollapsed ? '74px' : '262px',
            top: menuTop,
          }}
        >
          {/* Arrow pointer */}
          <div className="absolute -left-2 top-3 w-0 h-0 border-t-[6px] border-t-transparent border-b-[6px] border-b-transparent border-r-[8px] border-r-[#2D3748]" />

          {item.children.map((child) => {
            const ChildIcon = child.icon;
            const isChildItemActive = pathname === child.href;

            return (
              <Link
                key={child.href}
                href={child.href}
                onClick={() => setOpenSubmenu(null)}
                className={cn(
                  `flex items-center gap-3 px-4 py-2.5 ${transitions.DEFAULT} font-light text-sm`,
                  isChildItemActive
                    ? "bg-[#5B8DBE]/90 text-white"
                    : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
                )}
              >
                <ChildIcon className="h-4 w-4 flex-shrink-0" strokeWidth={1.5} />
                <span className="whitespace-nowrap">{child.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname();
  const { isCollapsed } = useSidebar();
  const [openSubmenu, setOpenSubmenu] = useState<string | null>(null);
  const [showSubmark, setShowSubmark] = useState(false);

  // Track collapsed state changes and derive showSubmark
  const [prevIsCollapsed, setPrevIsCollapsed] = useState(isCollapsed);
  if (isCollapsed !== prevIsCollapsed) {
    setPrevIsCollapsed(isCollapsed);
    if (!isCollapsed) {
      setShowSubmark(false);
    }
  }

  // Delayed show submark when collapsing (needs effect for timer)
  useEffect(() => {
    if (!isCollapsed) return;
    const timer = setTimeout(() => setShowSubmark(true), 300);
    return () => clearTimeout(timer);
  }, [isCollapsed]);

  return (
    <aside className={cn(
      "fixed top-0 left-0 z-40 h-full bg-gradient-to-b from-[#2D3748] to-[#374151] border-r border-gray-700/50 hidden lg:block transition-all duration-300",
      isCollapsed ? "w-[68px]" : "w-64"
    )}>
      {/* Header */}
      <div className={cn(
        "h-20 border-b border-gray-700/50 flex items-center",
        isCollapsed ? "justify-center p-1.5" : "p-3"
      )}>
        <Link href="/dashboard" className={cn(
          "flex items-center py-2.5",
          isCollapsed ? "justify-center" : "gap-3 px-3"
        )}>
          <Image
            src={showSubmark ? "/LX-Sidebar-SubmarkLogo.svg" : "/LX-Sidebar-Logo.svg"}
            alt="LeafXtract"
            width={showSubmark ? 40 : 160}
            height={40}
            className="h-10 w-auto transition-all duration-300"
          />
        </Link>
      </div>

      {/* Navigation - scrollable area */}
      <nav className={cn(
        "sidebar-scroll pb-20 space-y-1 h-[calc(100vh-5rem)] pt-3",
        isCollapsed ? "pl-3 pr-[11px]" : "px-3"
      )}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                `flex items-center rounded-md ${transitions.DEFAULT} font-normal text-sm group relative py-2.5`,
                isCollapsed ? "justify-center" : "gap-3 px-3",
                isActive
                  ? "bg-[#5B8DBE]/90 text-white"
                  : "text-gray-300 hover:bg-gray-700/30 hover:text-white"
              )}
            >
              <Icon className="h-5 w-5 flex-shrink-0" strokeWidth={1.5} />
              {!isCollapsed && (
                <span className="whitespace-nowrap">
                  {item.label}
                </span>
              )}
              {!isActive && (
                <div className="absolute inset-0 rounded-md opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-r from-transparent via-white/5 to-transparent" />
              )}
            </Link>
          );
        })}

        {/* Admin section - only for superusers */}
        {user?.is_superuser && (
          <>
            {!isCollapsed && (
              <div className="px-3 pt-6 pb-2 text-[10px] font-light text-gray-500 uppercase tracking-wider">
                Admin
              </div>
            )}
            {isCollapsed && <div className="pt-4" />}
            {adminMenuItems.map((item) => (
              <AdminMenuItemWithSubmenu
                key={item.id}
                item={item}
                pathname={pathname}
                isCollapsed={isCollapsed}
                openSubmenu={openSubmenu}
                setOpenSubmenu={setOpenSubmenu}
              />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}