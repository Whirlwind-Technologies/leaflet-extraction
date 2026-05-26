"use client";

import { useState, useTransition } from "react";
import Image from "next/image";
import { toast } from "sonner";
import { Plus, Search, Edit2, Trash2, Store, RefreshCw } from "lucide-react";
import type { Retailer } from "@/lib/types";
import { deleteRetailer, getRetailers } from "@/lib/actions/retailers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AddRetailerDialog } from "./add-retailer-dialog";
import { EditRetailerDialog } from "./edit-retailer-dialog";
import { brandColors as colors } from "@/lib/brand-colors";

// Country code to name mapping for display
const COUNTRY_NAMES: Record<string, string> = {
  SI: "Slovenia",
  HR: "Croatia",
  RS: "Serbia",
  BA: "Bosnia and Herzegovina",
  ME: "Montenegro",
  MK: "North Macedonia",
  AL: "Albania",
  XK: "Kosovo",
  BG: "Bulgaria",
  RO: "Romania",
  GR: "Greece",
  IT: "Italy",
  AT: "Austria",
  HU: "Hungary",
};

function formatCountry(code: string | undefined | null): string {
  if (!code) return "-";
  const name = COUNTRY_NAMES[code];
  return name ? `${name} (${code})` : code;
}

interface RetailerRegistryProps {
  initialRetailers: Retailer[];
}

export function RetailerRegistry({ initialRetailers }: RetailerRegistryProps) {
  const [retailers, setRetailers] = useState<Retailer[]>(initialRetailers);
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [editingRetailer, setEditingRetailer] = useState<Retailer | null>(null);
  const [deletingRetailer, setDeletingRetailer] = useState<Retailer | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const filteredRetailers = retailers.filter((r) =>
    r.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleRetailerAdded = (retailer: Retailer) => {
    setRetailers((prev) =>
      [...prev, retailer].sort((a, b) => a.name.localeCompare(b.name))
    );
    setShowAddDialog(false);
  };

  const handleRetailerUpdated = (retailer: Retailer) => {
    setRetailers((prev) =>
      prev
        .map((r) => (r.id === retailer.id ? retailer : r))
        .sort((a, b) => a.name.localeCompare(b.name))
    );
    setEditingRetailer(null);
  };

  const handleDelete = async () => {
    if (!deletingRetailer) return;

    startTransition(async () => {
      const result = await deleteRetailer(deletingRetailer.id);
      if (result.success) {
        setRetailers((prev) => prev.filter((r) => r.id !== deletingRetailer.id));
        toast.success(`Retailer "${deletingRetailer.name}" deleted`);
      } else {
        toast.error(result.error || "Failed to delete retailer");
      }
      setDeletingRetailer(null);
    });
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const freshRetailers = await getRetailers();
      setRetailers(freshRetailers);
      toast.success("Retailers refreshed");
    } catch {
      toast.error("Failed to refresh retailers");
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <>
      <Card className="border-slate-200">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-base text-slate-800">
            <div className="flex items-center gap-2">
              <Store className="h-5 w-5" />
              Retailers ({retailers.length})
            </div>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
            <Button
              onClick={() => setShowAddDialog(true)}
              style={{ backgroundColor: colors.primaryBrandBlue }}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Retailer
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search retailers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Table */}
          {filteredRetailers.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              {searchQuery
                ? "No retailers found matching your search"
                : "No retailers added yet. Click 'Add Retailer' to get started."}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>External ID</TableHead>
                    <TableHead>Country</TableHead>
                    <TableHead>Currency</TableHead>
                    <TableHead>Language</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRetailers.map((retailer) => (
                    <TableRow key={retailer.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {retailer.logo_url ? (
                            <Image
                              src={retailer.logo_url}
                              alt=""
                              width={24}
                              height={24}
                              className="w-6 h-6 rounded object-cover"
                              unoptimized
                            />
                          ) : (
                            <Store className="w-5 h-5 text-slate-400" />
                          )}
                          {retailer.name}
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-600 font-mono text-sm">
                        {retailer.external_id || "-"}
                      </TableCell>
                      <TableCell>{formatCountry(retailer.country)}</TableCell>
                      <TableCell>{retailer.currency || "-"}</TableCell>
                      <TableCell>{retailer.language || "-"}</TableCell>
                      <TableCell>
                        <Badge
                          variant={retailer.is_active ? "default" : "secondary"}
                        >
                          {retailer.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setEditingRetailer(retailer)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeletingRetailer(retailer)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Dialog */}
      <AddRetailerDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
        onSuccess={handleRetailerAdded}
      />

      {/* Edit Dialog */}
      <EditRetailerDialog
        retailer={editingRetailer}
        onOpenChange={(open) => !open && setEditingRetailer(null)}
        onSuccess={handleRetailerUpdated}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deletingRetailer}
        onOpenChange={(open) => !open && setDeletingRetailer(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Retailer</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{deletingRetailer?.name}&quot;?
              This will deactivate the retailer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
