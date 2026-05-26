"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
  Clock,
  CheckCircle,
  AlertTriangle,
  BarChart3,
} from "lucide-react";

interface ReviewStatsProps {
  total: number;
  pending: number;
  needsCorrection: number;
  approved: number;
  highPriority: number;
}

export function ReviewStats({
  total,
  pending,
  needsCorrection,
  approved,
  highPriority,
}: ReviewStatsProps) {
  const stats = [
    {
      label: "Total Products",
      value: total,
      icon: BarChart3,
      iconClass: "text-foreground",
      bgClass: "bg-muted",
    },
    {
      label: "Pending Review",
      value: pending,
      icon: Clock,
      iconClass: "text-amber-600 dark:text-amber-400",
      bgClass: "bg-amber-50 dark:bg-amber-950",
    },
    {
      label: "Needs Correction",
      value: needsCorrection,
      icon: AlertTriangle,
      iconClass: "text-amber-600 dark:text-amber-400",
      bgClass: "bg-amber-50 dark:bg-amber-950",
    },
    {
      label: "Approved",
      value: approved,
      icon: CheckCircle,
      iconClass: "text-emerald-600 dark:text-emerald-400",
      bgClass: "bg-emerald-50 dark:bg-emerald-950",
    },
    {
      label: "High Priority",
      value: highPriority,
      icon: AlertTriangle,
      iconClass: "text-destructive",
      bgClass: "bg-destructive/10",
    },
  ];

  // Calculate review progress
  const totalReviewed = approved + needsCorrection;
  const reviewRate = total > 0
    ? Math.round((totalReviewed / total) * 100)
    : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${stat.bgClass}`}>
                  <stat.icon className={`h-4 w-4 ${stat.iconClass}`} />
                </div>
                <div>
                  <p className="text-2xl font-light text-foreground">{stat.value}</p>
                  <p className="text-xs font-light text-muted-foreground">{stat.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-light text-foreground">Review Progress</span>
              <span className="text-sm font-light text-muted-foreground">
                {totalReviewed} of {total} reviewed ({reviewRate}%)
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden bg-muted">
              <div className="h-full flex">
                <div
                  className="transition-all bg-emerald-500 dark:bg-emerald-600"
                  style={{ width: `${(approved / total) * 100}%` }}
                  title={`Approved: ${approved}`}
                />
                <div
                  className="transition-all bg-amber-500 dark:bg-amber-600"
                  style={{ width: `${(needsCorrection / total) * 100}%` }}
                  title={`Needs correction: ${needsCorrection}`}
                />
              </div>
            </div>
            <div className="flex gap-4 mt-2 text-xs font-light text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 dark:bg-emerald-600" />
                Approved
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500 dark:bg-amber-600" />
                Needs correction
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-border" />
                Pending
              </span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}