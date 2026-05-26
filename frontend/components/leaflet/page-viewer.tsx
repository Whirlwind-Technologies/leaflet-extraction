"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ArrowLeft,
  Edit,
  ImageIcon,
  Loader2,
  PanelRightClose,
  PanelRight,
  X,
} from "lucide-react";
import type { Leaflet, LeafletPage, Product, ReviewStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface PageViewerProps {
  leaflet: Leaflet;
  page: LeafletPage;
  pages: LeafletPage[];
  products: Product[];
}

function getAccessibleUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return url
    .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
    .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
}

function getStatusColor(status: ReviewStatus): string {
  switch (status) {
    case "approved":
    case "auto_approved":
      return "#22c55e";
    case "pending":
      return "#eab308";
    case "rejected":
      return "#ef4444";
    case "corrected":
      return "#3b82f6";
    case "needs_correction":
      return "#f97316";
    default:
      return "#6b7280";
  }
}

const ZOOM_PRESETS = [
  { label: "Fit", value: "fit" },
  { label: "50%", value: 0.5 },
  { label: "75%", value: 0.75 },
  { label: "100%", value: 1 },
  { label: "150%", value: 1.5 },
  { label: "200%", value: 2 },
];

export function PageViewer({ leaflet, page, pages, products }: PageViewerProps) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [hoveredProductId, setHoveredProductId] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const pageProducts = useMemo(() => products.filter((p) => p.page_number === page.page_number), [products, page.page_number]);
  const selectedProduct = pageProducts.find((p) => p.id === selectedProductId);
  const currentPageIndex = pages.findIndex((p) => p.page_number === page.page_number);
  const prevPage = currentPageIndex > 0 ? pages[currentPageIndex - 1] : null;
  const nextPage = currentPageIndex < pages.length - 1 ? pages[currentPageIndex + 1] : null;

  // Reset image state when page URL changes (adjust state during render pattern)
  const accessibleImageUrl = getAccessibleUrl(page.image_url);
  const [prevImageUrl, setPrevImageUrl] = useState(page.image_url);
  if (page.image_url !== prevImageUrl) {
    setPrevImageUrl(page.image_url);
    setImageLoaded(false);
    setImageError(!accessibleImageUrl);
  }

  // Load image
  useEffect(() => {
    if (!accessibleImageUrl) return;

    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imageRef.current = img;
      setImageLoaded(true);
    };
    img.onerror = () => setImageError(true);
    img.src = accessibleImageUrl;

    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [accessibleImageUrl]);

  const fitToContainer = useCallback(() => {
    const container = containerRef.current;
    const img = imageRef.current;
    if (!container || !img) return;

    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const imgWidth = img.naturalWidth || page.width;
    const imgHeight = img.naturalHeight || page.height;

    if (containerWidth <= 0 || containerHeight <= 0 || imgWidth <= 0 || imgHeight <= 0) return;

    const scale = Math.min(containerWidth / imgWidth, containerHeight / imgHeight) * 0.92;
    setZoom(scale);
    setPan({
      x: (containerWidth - imgWidth * scale) / 2,
      y: (containerHeight - imgHeight * scale) / 2,
    });
  }, [page.width, page.height]);

  const setZoomLevel = useCallback((level: number | "fit") => {
    if (level === "fit") {
      fitToContainer();
      return;
    }
    const container = containerRef.current;
    const img = imageRef.current;
    if (!container || !img) return;

    const imgWidth = img.naturalWidth || page.width;
    const imgHeight = img.naturalHeight || page.height;

    setZoom(level);
    setPan({
      x: (container.clientWidth - imgWidth * level) / 2,
      y: (container.clientHeight - imgHeight * level) / 2,
    });
  }, [fitToContainer, page.width, page.height]);

  useEffect(() => {
    if (!imageLoaded) return;
    const timer = setTimeout(fitToContainer, 50);
    return () => clearTimeout(timer);
  }, [imageLoaded, fitToContainer]);

  // Resize canvas
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const updateSize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = container.clientWidth * dpr;
      canvas.height = container.clientHeight * dpr;
      canvas.style.width = `${container.clientWidth}px`;
      canvas.style.height = `${container.clientHeight}px`;
    };

    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(container);
    updateSize();
    return () => resizeObserver.disconnect();
  }, []);

  // Draw
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const img = imageRef.current;
    if (!canvas || !ctx || !img || !imageLoaded) return;

    const dpr = window.devicePixelRatio || 1;
    const imgWidth = img.naturalWidth || page.width;
    const imgHeight = img.naturalHeight || page.height;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.scale(dpr, dpr);

    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);
    ctx.drawImage(img, 0, 0, imgWidth, imgHeight);

    pageProducts.forEach((product) => {
      const bbox = product.bounding_box;
      if (!bbox) return;

      const isSelected = product.id === selectedProductId;
      const isHovered = product.id === hoveredProductId;
      const color = getStatusColor(product.review_status);

      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 3 / zoom : isHovered ? 2.5 / zoom : 2 / zoom;
      ctx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);

      ctx.fillStyle = isSelected ? `${color}40` : isHovered ? `${color}30` : `${color}15`;
      ctx.fillRect(bbox.x, bbox.y, bbox.width, bbox.height);

      // Label - always visible, positioned inside the bounding box at the top
      // Font size compensates for zoom so labels remain readable at any zoom level
      const label = product.product_name?.slice(0, 25) || "Product";
      const baseFontSize = 14; // Target size on screen
      const fontSize = baseFontSize / zoom; // Compensate for canvas scale
      ctx.font = `600 ${fontSize}px system-ui, -apple-system, sans-serif`;
      const textWidth = ctx.measureText(label).width;
      const labelHeight = fontSize * 1.4;
      const labelPadding = 6 / zoom;
      const labelMargin = 8 / zoom;
      // Place label inside the box at the top
      const labelY = bbox.y + labelMargin;
      const labelX = bbox.x + labelMargin;

      // Label background with shadow effect
      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.beginPath();
      ctx.roundRect(labelX + 2/zoom, labelY + 2/zoom, textWidth + labelPadding * 2, labelHeight, 4/zoom);
      ctx.fill();

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(labelX, labelY, textWidth + labelPadding * 2, labelHeight, 4/zoom);
      ctx.fill();

      // Label text
      ctx.fillStyle = "#ffffff";
      ctx.textBaseline = "middle";
      ctx.fillText(label, labelX + labelPadding, labelY + labelHeight / 2);
    });

    ctx.restore();
  }, [imageLoaded, page.width, page.height, pageProducts, zoom, pan, selectedProductId, hoveredProductId]);

  useEffect(() => {
    requestAnimationFrame(draw);
  }, [draw]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isPanning) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;

    const clicked = pageProducts.find((p) => {
      const b = p.bounding_box;
      return b && x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height;
    });
    setSelectedProductId(clicked?.id || null);
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isPanning) {
      setPan((prev) => ({
        x: prev.x + e.clientX - panStart.x,
        y: prev.y + e.clientY - panStart.y,
      }));
      setPanStart({ x: e.clientX, y: e.clientY });
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;

    const hovered = pageProducts.find((p) => {
      const b = p.bounding_box;
      return b && x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height;
    });
    setHoveredProductId(hovered?.id || null);
    canvas.style.cursor = hovered ? "pointer" : "grab";
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
      e.currentTarget.style.cursor = "grabbing";
    }
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsPanning(false);
    e.currentTarget.style.cursor = "grab";
  };

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(5, zoom * delta));
    const scaleFactor = newZoom / zoom;

    setZoom(newZoom);
    setPan({ x: x - (x - pan.x) * scaleFactor, y: y - (y - pan.y) * scaleFactor });
  }, [zoom, pan]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  // Keyboard
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key) {
        case "ArrowLeft":
          if (prevPage) router.push(`/leaflets/${leaflet.id}/pages/${prevPage.page_number}`);
          break;
        case "ArrowRight":
          if (nextPage) router.push(`/leaflets/${leaflet.id}/pages/${nextPage.page_number}`);
          break;
        case "Escape":
          if (selectedProductId) setSelectedProductId(null);
          else router.push(`/leaflets/${leaflet.id}?tab=pages`);
          break;
        case "f":
        case "F":
          fitToContainer();
          break;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router, leaflet.id, prevPage, nextPage, fitToContainer, selectedProductId]);

  // Scroll selected into view
  useEffect(() => {
    if (!selectedProductId || !sidebarRef.current) return;
    const el = sidebarRef.current.querySelector(`[data-product-id="${selectedProductId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedProductId]);

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col overflow-hidden">
      {/* Header */}
      <div className="h-12 px-3 border-b flex items-center justify-between shrink-0 bg-background">
        <div className="flex items-center gap-2">
          <Link href={`/leaflets/${leaflet.id}?tab=pages`}>
            <Button variant="ghost" size="sm" className="h-8 px-2">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <span className="text-sm font-medium">Page {page.page_number}</span>
          <span className="text-sm text-muted-foreground">/ {pages.length}</span>
          <Badge variant="secondary" className="ml-1 h-5 text-xs">
            {pageProducts.length} products
          </Badge>
        </div>

        <div className="flex items-center gap-1">
          <div className="flex items-center border rounded-md h-8">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-r-none"
              onClick={() => setZoom((z) => Math.max(0.1, z * 0.8))}
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 px-2 min-w-[52px] rounded-none border-x text-xs">
                  {Math.round(zoom * 100)}%
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="center">
                {ZOOM_PRESETS.map((p) => (
                  <DropdownMenuItem key={p.label} onClick={() => setZoomLevel(p.value as number | "fit")}>
                    {p.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-l-none"
              onClick={() => setZoom((z) => Math.min(5, z * 1.25))}
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={fitToContainer}>
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
          <div className="w-px h-5 bg-border mx-1" />
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setSidebarOpen((p) => !p)}
          >
            {sidebarOpen ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRight className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* Canvas */}
        <div className="flex-1 relative bg-neutral-100 dark:bg-neutral-900">
          {prevPage && (
            <Link href={`/leaflets/${leaflet.id}/pages/${prevPage.page_number}`}>
              <Button size="icon" variant="secondary" className="absolute left-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 rounded-full shadow">
                <ChevronLeft className="h-5 w-5" />
              </Button>
            </Link>
          )}
          {nextPage && (
            <Link href={`/leaflets/${leaflet.id}/pages/${nextPage.page_number}`}>
              <Button size="icon" variant="secondary" className="absolute right-2 top-1/2 -translate-y-1/2 z-10 h-9 w-9 rounded-full shadow">
                <ChevronRight className="h-5 w-5" />
              </Button>
            </Link>
          )}

          <div ref={containerRef} className="absolute inset-0">
            {!imageLoaded && !imageError && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {imageError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
                <ImageIcon className="h-10 w-10 mb-2" />
                <p className="text-sm">Failed to load image</p>
              </div>
            )}
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              onMouseMove={handleCanvasMouseMove}
              onMouseDown={handleMouseDown}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              className={cn("absolute inset-0", !imageLoaded && "hidden")}
            />
          </div>
        </div>

        {/* Sidebar */}
        {sidebarOpen && (
          <div className="w-64 border-l flex flex-col bg-background shrink-0 overflow-hidden">
            <div className="h-9 px-3 border-b flex items-center justify-between shrink-0">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Products
              </span>
              <span className="text-xs text-muted-foreground">{pageProducts.length}</span>
            </div>

            {/* Product list */}
            <div ref={sidebarRef} className="flex-1 overflow-y-auto">
              {pageProducts.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-8">No products</p>
              ) : (
                <div className="py-1">
                  {pageProducts.map((product) => (
                    <div
                      key={product.id}
                      data-product-id={product.id}
                      className={cn(
                        "px-3 py-1.5 cursor-pointer border-l-2 transition-colors",
                        selectedProductId === product.id
                          ? "bg-primary/10 border-l-primary"
                          : "border-l-transparent hover:bg-muted/50"
                      )}
                      onClick={() => setSelectedProductId(product.id)}
                      onMouseEnter={() => setHoveredProductId(product.id)}
                      onMouseLeave={() => setHoveredProductId(null)}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="w-1.5 h-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: getStatusColor(product.review_status) }}
                        />
                        <span className="text-xs truncate flex-1">{product.product_name}</span>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {product.discounted_price?.toFixed(2) || product.regular_price?.toFixed(2) || "-"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Selected product detail */}
            {selectedProduct && (
              <div className="border-t bg-muted/30 p-3 shrink-0">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-sm font-medium leading-tight line-clamp-2">
                    {selectedProduct.product_name}
                  </p>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0 -mr-1 -mt-1"
                    onClick={() => setSelectedProductId(null)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
                {selectedProduct.brand && (
                  <p className="text-xs text-muted-foreground mb-2">{selectedProduct.brand}</p>
                )}
                <div className="flex items-center gap-3 text-xs mb-3">
                  <div>
                    <span className="text-muted-foreground">Price: </span>
                    <span className="font-medium">
                      {selectedProduct.discounted_price ? (
                        <>
                          <span className="text-red-600">{selectedProduct.discounted_price.toFixed(2)}</span>
                          <span className="text-muted-foreground line-through ml-1">
                            {selectedProduct.regular_price?.toFixed(2)}
                          </span>
                        </>
                      ) : (
                        selectedProduct.regular_price?.toFixed(2) || "-"
                      )}
                      {selectedProduct.currency && ` ${selectedProduct.currency}`}
                    </span>
                  </div>
                  {selectedProduct.discount_percentage && (
                    <Badge variant="destructive" className="h-4 text-[10px] px-1">
                      -{parseFloat(selectedProduct.discount_percentage.toFixed(2))}%
                    </Badge>
                  )}
                </div>
                <Button
                  size="sm"
                  className="w-full h-7 text-xs"
                  onClick={() => router.push(`/products/${selectedProduct.id}/edit`)}
                >
                  <Edit className="h-3 w-3 mr-1" />
                  Edit Product
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
