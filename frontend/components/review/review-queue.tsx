"use client";

import { useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProductCard } from "./product-card";
import {
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Search,
  LayoutGrid,
  List,
  CheckSquare,
  Square,
  Download,
} from "lucide-react";
import { reviewProduct, batchReviewProducts } from "@/lib/actions/products";
import { toast } from "sonner";
import type { Product } from "@/lib/types";
import { ExportDialog } from "@/components/export/export-dialog";

interface ReviewQueueProps {
  products: Product[];
  leafletId?: string;
  pageImageUrl?: string | null;
  totalCount: number;
  currentPage: number;
  pageSize: number;
}

type ViewMode = "grid" | "list";

export function ReviewQueue({
  products,
  leafletId,
  pageImageUrl,
  totalCount,
  currentPage,
  pageSize,
}: ReviewQueueProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [localProducts, setLocalProducts] = useState<Product[]>(products);
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [exportDialogOpen, setExportDialogOpen] = useState(false);

  const totalPages = Math.ceil(totalCount / pageSize);

  // Filter products
  const filteredProducts = localProducts.filter(p => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        p.product_name.toLowerCase().includes(query) ||
        p.brand?.toLowerCase().includes(query) ||
        p.product_code?.toLowerCase().includes(query)
      );
    }
    return true;
  });
  
  const handleApprove = async (productId: string) => {
    setProcessingId(productId);
    try {
      const result = await reviewProduct(productId, { action: "approved" });
      if (result.success) {
        toast.success("Product approved");
        // Remove from local state immediately
        setLocalProducts(prev => prev.filter(p => p.id !== productId));
        // Also remove from selection if selected
        setSelectedProducts(prev => {
          const next = new Set(prev);
          next.delete(productId);
          return next;
        });
        startTransition(() => router.refresh());
      } else {
        toast.error(result.error || "Failed to approve product");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (productId: string) => {
    setProcessingId(productId);
    try {
      const result = await reviewProduct(productId, { action: "rejected" });
      if (result.success) {
        toast.success("Product rejected");
        // Remove from local state immediately
        setLocalProducts(prev => prev.filter(p => p.id !== productId));
        // Also remove from selection if selected
        setSelectedProducts(prev => {
          const next = new Set(prev);
          next.delete(productId);
          return next;
        });
        startTransition(() => router.refresh());
      } else {
        toast.error(result.error || "Failed to reject product");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setProcessingId(null);
    }
  };
  
  const handleEdit = (productId: string) => {
    const product = localProducts.find(p => p.id === productId);
    const params = new URLSearchParams();
    if (product?.leaflet_id) params.set("leaflet_id", product.leaflet_id);
    if (leafletId) params.set("leaflet_id", leafletId);
    params.set("status", "pending");
    router.push(`/products/${productId}/edit?${params.toString()}`);
  };
  
  const handleSelectProduct = (productId: string, selected: boolean) => {
    setSelectedProducts(prev => {
      const next = new Set(prev);
      if (selected) {
        next.add(productId);
      } else {
        next.delete(productId);
      }
      return next;
    });
  };
  
  const handleSelectAll = () => {
    if (selectedProducts.size === filteredProducts.length) {
      setSelectedProducts(new Set());
    } else {
      setSelectedProducts(new Set(filteredProducts.map(p => p.id)));
    }
  };
  
  const handleBatchApprove = async () => {
    if (selectedProducts.size === 0) return;

    setIsBatchProcessing(true);
    const productIds = Array.from(selectedProducts);
    try {
      const result = await batchReviewProducts(productIds, "approved");
      if (result.success && result.data) {
        toast.success(
          `Approved ${result.data.succeeded} of ${result.data.processed} products`
        );
        // Remove approved products from local state immediately
        setLocalProducts(prev => prev.filter(p => !productIds.includes(p.id)));
        setSelectedProducts(new Set());
        startTransition(() => router.refresh());
      } else {
        toast.error(result.error || "Batch approve failed");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setIsBatchProcessing(false);
    }
  };

  const handleBatchReject = async () => {
    if (selectedProducts.size === 0) return;

    setIsBatchProcessing(true);
    const productIds = Array.from(selectedProducts);
    try {
      const result = await batchReviewProducts(productIds, "rejected");
      if (result.success && result.data) {
        toast.success(
          `Rejected ${result.data.succeeded} of ${result.data.processed} products`
        );
        // Remove rejected products from local state immediately
        setLocalProducts(prev => prev.filter(p => !productIds.includes(p.id)));
        setSelectedProducts(new Set());
        startTransition(() => router.refresh());
      } else {
        toast.error(result.error || "Batch reject failed");
      }
    } catch {
      toast.error("An error occurred");
    } finally {
      setIsBatchProcessing(false);
    }
  };
  
  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", page.toString());
    router.push(`/review?${params.toString()}`);
  };
  
  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* View mode */}
            <div className="flex gap-1 rounded-md p-0.5 border border-border">
              <Button
                variant={viewMode === "grid" ? "secondary" : "ghost"}
                size="sm"
                className="h-9 w-9 p-0"
                onClick={() => setViewMode("grid")}
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === "list" ? "secondary" : "ghost"}
                size="sm"
                className="h-9 w-9 p-0"
                onClick={() => setViewMode("list")}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>

            {/* Export queue button */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setExportDialogOpen(true)}
              disabled={totalCount === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Export Queue ({totalCount})
            </Button>
          </div>
        </CardContent>
      </Card>
      
      {/* Batch actions bar */}
      {selectedProducts.size > 0 && (
        <Card className="bg-primary/10 border-primary">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-foreground">
                  {selectedProducts.size} selected
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedProducts(new Set())}
                >
                  Clear selection
                </Button>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBatchReject}
                  disabled={isBatchProcessing}
                  className="border-destructive/50 text-destructive hover:bg-destructive/10"
                >
                  {isBatchProcessing ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <XCircle className="h-4 w-4 mr-2" />
                  )}
                  Reject All
                </Button>
                <Button
                  size="sm"
                  onClick={handleBatchApprove}
                  disabled={isBatchProcessing}
                >
                  {isBatchProcessing ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle className="h-4 w-4 mr-2" />
                  )}
                  Approve All
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Products grid/list */}
      {filteredProducts.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <div>
              {searchQuery ? (
                <>
                  <p className="text-lg font-medium text-foreground">No products match your search</p>
                  <p className="text-sm mt-1 text-muted-foreground">Try adjusting your search criteria</p>
                </>
              ) : (
                <>
                  <CheckCircle className="h-12 w-12 mx-auto mb-4 text-emerald-600 dark:text-emerald-400" />
                  <p className="text-lg font-medium text-foreground">All caught up!</p>
                  <p className="text-sm mt-1 text-muted-foreground">No products pending review</p>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Select all */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleSelectAll}
              className="text-muted-foreground"
            >
              {selectedProducts.size === filteredProducts.length ? (
                <CheckSquare className="h-4 w-4 mr-2 text-primary" />
              ) : (
                <Square className="h-4 w-4 mr-2" />
              )}
              Select all ({filteredProducts.length})
            </Button>
          </div>
          
          <div className={
            viewMode === "grid"
              ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3 sm:gap-4"
              : "space-y-2"
          }>
            {filteredProducts.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                pageImageUrl={pageImageUrl}
                onApprove={handleApprove}
                onReject={handleReject}
                onEdit={handleEdit}
                isSelected={selectedProducts.has(product.id)}
                onSelect={handleSelectProduct}
                isProcessing={processingId === product.id}
                viewMode={viewMode}
              />
            ))}
          </div>
        </>
      )}
      
      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {(currentPage - 1) * pageSize + 1} to{" "}
            {Math.min(currentPage * pageSize, totalCount)} of {totalCount} products
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1 || isPending}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }

                return (
                  <Button
                    key={pageNum}
                    variant={currentPage === pageNum ? "default" : "outline"}
                    size="sm"
                    onClick={() => handlePageChange(pageNum)}
                    disabled={isPending}
                    className="w-8"
                  >
                    {pageNum}
                  </Button>
                );
              })}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages || isPending}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Export Dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onOpenChange={setExportDialogOpen}
        mode="review_queue"
        reviewQueueFilters={leafletId ? { leaflet_id: leafletId } : undefined}
      />
    </div>
  );
}