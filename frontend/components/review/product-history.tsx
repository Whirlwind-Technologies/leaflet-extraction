"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  History,
  CheckCircle,
  XCircle,
  Edit2,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { formatDistanceToNow } from "@/lib/utils";

interface ProductReview {
  id: string;
  product_id: string;
  reviewer_id: string | null;
  action: string;
  previous_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  changed_fields: string[];
  notes: string | null;
  time_spent_seconds: number | null;
  created_at: string;
}

interface ProductHistoryProps {
  productId: string;
  reviews?: ProductReview[];
}

function ActionIcon({ action }: { action: string }) {
  switch (action) {
    case "approved":
      return <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />;
    case "rejected":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "corrected":
      return <Edit2 className="h-4 w-4 text-primary" />;
    case "needs_correction":
      return <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
}

function ActionBadge({ action }: { action: string }) {
  const config: Record<string, { label: string; className: string }> = {
    approved: { label: "Approved", className: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-400 dark:border-emerald-800" },
    rejected: { label: "Rejected", className: "bg-destructive/10 text-destructive border-destructive/30" },
    corrected: { label: "Corrected", className: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800" },
    needs_correction: { label: "Needs Correction", className: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-400 dark:border-amber-800" },
  };

  const cfg = config[action] || { label: action, className: "bg-muted text-muted-foreground border-border" };

  return (
    <Badge variant="outline" className={`text-xs ${cfg.className}`}>
      {cfg.label}
    </Badge>
  );
}

export function ProductHistory({ reviews = [] }: ProductHistoryProps) {
  const [expandedReview, setExpandedReview] = useState<string | null>(null);

  if (reviews.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2 text-foreground">
            <History className="h-4 w-4" />
            Review History
          </CardTitle>
        </CardHeader>
        <CardContent className="py-3">
          <p className="text-sm text-center py-4 text-muted-foreground">
            No review history yet
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="text-sm flex items-center gap-2 text-foreground">
          <History className="h-4 w-4" />
          Review History ({reviews.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="py-0">
        <div>
          {reviews.map((review) => (
            <div key={review.id} className="py-3 border-b border-border last:border-0">
              <div className="flex items-start gap-3">
                <div className="mt-0.5">
                  <ActionIcon action={review.action} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <ActionBadge action={review.action} />
                    <span className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(review.created_at))}
                    </span>
                    {review.time_spent_seconds && (
                      <span className="text-xs text-muted-foreground">
                        • {review.time_spent_seconds}s
                      </span>
                    )}
                  </div>

                  {review.notes && (
                    <p className="text-sm mb-2 text-muted-foreground">
                      &quot;{review.notes}&quot;
                    </p>
                  )}

                  {review.changed_fields && review.changed_fields.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {review.changed_fields.map((field) => (
                        <Badge key={field} variant="outline" className="text-xs">
                          {field.replace(/_/g, " ")}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Expandable details */}
                  {(review.previous_data || review.new_data) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-primary"
                      onClick={() => setExpandedReview(
                        expandedReview === review.id ? null : review.id
                      )}
                    >
                      {expandedReview === review.id ? (
                        <ChevronUp className="h-3 w-3 mr-1" />
                      ) : (
                        <ChevronDown className="h-3 w-3 mr-1" />
                      )}
                      {expandedReview === review.id ? "Hide" : "Show"} changes
                    </Button>
                  )}

                  {expandedReview === review.id && (
                    <div className="mt-2 p-2 rounded text-xs space-y-2 bg-muted">
                      {review.previous_data && Object.keys(review.previous_data).length > 0 && (
                        <div>
                          <p className="font-medium mb-1 text-muted-foreground">Before:</p>
                          <div className="grid grid-cols-2 gap-1">
                            {Object.entries(review.previous_data)
                              .filter(([key]) => review.changed_fields?.includes(key))
                              .map(([key, value]) => (
                                <div key={key}>
                                  <span className="text-muted-foreground">{key}:</span>{" "}
                                  <span className="line-through text-destructive">
                                    {String(value ?? "null")}
                                  </span>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                      {review.new_data && Object.keys(review.new_data).length > 0 && (
                        <div>
                          <p className="font-medium mb-1 text-muted-foreground">After:</p>
                          <div className="grid grid-cols-2 gap-1">
                            {Object.entries(review.new_data).map(([key, value]) => (
                              <div key={key}>
                                <span className="text-muted-foreground">{key}:</span>{" "}
                                <span className="text-emerald-600 dark:text-emerald-400">
                                  {String(value ?? "null")}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}