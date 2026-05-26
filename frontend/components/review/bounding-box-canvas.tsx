"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { BoundingBox } from "@/lib/types";

interface BoundingBoxCanvasProps {
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  boundingBox: BoundingBox;
  onBoundingBoxChange: (bbox: BoundingBox) => void;
  zoom: number;
  pan: { x: number; y: number };
  onPanChange: (pan: { x: number; y: number }) => void;
  onZoomChange: (zoom: number) => void;
  mode: "pan" | "edit-bbox";
  onCropPreview?: (dataUrl: string) => void;
}

type Handle =
  | "top-left" | "top" | "top-right"
  | "left" | "right"
  | "bottom-left" | "bottom" | "bottom-right"
  | "center";

type InteractionState =
  | { type: "idle" }
  | { type: "panning"; startX: number; startY: number }
  | { type: "resizing"; handle: Handle; startX: number; startY: number }
  | { type: "drawing"; anchorX: number; anchorY: number };

const HANDLE_SIZE = 10;
const MIN_BOX_SIZE = 20;

export function BoundingBoxCanvas({
  imageUrl,
  imageWidth,
  imageHeight,
  boundingBox,
  onBoundingBoxChange,
  zoom,
  pan,
  onPanChange,
  onZoomChange,
  mode,
  onCropPreview,
}: BoundingBoxCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [hoveredHandle, setHoveredHandle] = useState<Handle | null>(null);
  const [drawingRect, setDrawingRect] = useState<BoundingBox | null>(null);
  const interactionRef = useRef<InteractionState>({ type: "idle" });
  const spaceHeldRef = useRef(false);

  // Load image
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imageRef.current = img;
      setImageLoaded(true);
    };
    img.onerror = () => {
      console.error("Failed to load image:", imageUrl);
    };
    img.src = imageUrl;

    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [imageUrl]);

  // Resize canvas to container
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resizeObserver = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    });

    resizeObserver.observe(container);
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    return () => resizeObserver.disconnect();
  }, []);

  // Get handle position at point
  const getHandleAtPoint = useCallback((x: number, y: number): Handle | null => {
    const scaledBox = {
      x: boundingBox.x * zoom + pan.x,
      y: boundingBox.y * zoom + pan.y,
      width: boundingBox.width * zoom,
      height: boundingBox.height * zoom,
    };

    const handles: { pos: Handle; x: number; y: number }[] = [
      { pos: "top-left", x: scaledBox.x, y: scaledBox.y },
      { pos: "top", x: scaledBox.x + scaledBox.width / 2, y: scaledBox.y },
      { pos: "top-right", x: scaledBox.x + scaledBox.width, y: scaledBox.y },
      { pos: "left", x: scaledBox.x, y: scaledBox.y + scaledBox.height / 2 },
      { pos: "right", x: scaledBox.x + scaledBox.width, y: scaledBox.y + scaledBox.height / 2 },
      { pos: "bottom-left", x: scaledBox.x, y: scaledBox.y + scaledBox.height },
      { pos: "bottom", x: scaledBox.x + scaledBox.width / 2, y: scaledBox.y + scaledBox.height },
      { pos: "bottom-right", x: scaledBox.x + scaledBox.width, y: scaledBox.y + scaledBox.height },
    ];

    for (const handle of handles) {
      const distance = Math.sqrt(Math.pow(x - handle.x, 2) + Math.pow(y - handle.y, 2));
      if (distance <= HANDLE_SIZE) {
        return handle.pos;
      }
    }

    // Check if inside box (for moving)
    if (
      x >= scaledBox.x && x <= scaledBox.x + scaledBox.width &&
      y >= scaledBox.y && y <= scaledBox.y + scaledBox.height
    ) {
      return "center";
    }

    return null;
  }, [boundingBox, zoom, pan]);

  // Get cursor for handle
  const getCursor = (handle: Handle | null): string => {
    switch (handle) {
      case "top-left":
      case "bottom-right":
        return "nwse-resize";
      case "top-right":
      case "bottom-left":
        return "nesw-resize";
      case "top":
      case "bottom":
        return "ns-resize";
      case "left":
      case "right":
        return "ew-resize";
      case "center":
        return "move";
      default:
        return mode === "edit-bbox" ? "crosshair" : mode === "pan" ? "grab" : "default";
    }
  };

  // Draw canvas
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const img = imageRef.current;

    if (!canvas || !ctx || !img || !imageLoaded) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw image
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);
    ctx.drawImage(img, 0, 0, imageWidth, imageHeight);
    ctx.restore();

    // Draw bounding box
    const scaledBox = {
      x: boundingBox.x * zoom + pan.x,
      y: boundingBox.y * zoom + pan.y,
      width: boundingBox.width * zoom,
      height: boundingBox.height * zoom,
    };

    // Dim overlay - four rectangles around the bounding box
    ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
    // Top
    ctx.fillRect(0, 0, canvas.width, scaledBox.y);
    // Left
    ctx.fillRect(0, scaledBox.y, scaledBox.x, scaledBox.height);
    // Right
    ctx.fillRect(
      scaledBox.x + scaledBox.width,
      scaledBox.y,
      canvas.width - (scaledBox.x + scaledBox.width),
      scaledBox.height
    );
    // Bottom
    ctx.fillRect(
      0,
      scaledBox.y + scaledBox.height,
      canvas.width,
      canvas.height - (scaledBox.y + scaledBox.height)
    );

    // Outer glow
    ctx.strokeStyle = "rgba(59, 130, 246, 0.5)";
    ctx.lineWidth = 4;
    ctx.strokeRect(scaledBox.x, scaledBox.y, scaledBox.width, scaledBox.height);

    // Main border
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;
    ctx.strokeRect(scaledBox.x, scaledBox.y, scaledBox.width, scaledBox.height);

    // Semi-transparent fill
    ctx.fillStyle = "rgba(59, 130, 246, 0.1)";
    ctx.fillRect(scaledBox.x, scaledBox.y, scaledBox.width, scaledBox.height);

    // Draw handles in edit mode
    if (mode === "edit-bbox") {
      const handleCoords = [
        { x: scaledBox.x, y: scaledBox.y },
        { x: scaledBox.x + scaledBox.width / 2, y: scaledBox.y },
        { x: scaledBox.x + scaledBox.width, y: scaledBox.y },
        { x: scaledBox.x, y: scaledBox.y + scaledBox.height / 2 },
        { x: scaledBox.x + scaledBox.width, y: scaledBox.y + scaledBox.height / 2 },
        { x: scaledBox.x, y: scaledBox.y + scaledBox.height },
        { x: scaledBox.x + scaledBox.width / 2, y: scaledBox.y + scaledBox.height },
        { x: scaledBox.x + scaledBox.width, y: scaledBox.y + scaledBox.height },
      ];

      const handlePositions: Handle[] = [
        "top-left", "top", "top-right",
        "left", "right",
        "bottom-left", "bottom", "bottom-right"
      ];

      handleCoords.forEach((coord, idx) => {
        const isHovered = hoveredHandle === handlePositions[idx];

        ctx.fillStyle = isHovered ? "#2563eb" : "#3b82f6";
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;

        ctx.beginPath();
        ctx.arc(coord.x, coord.y, isHovered ? HANDLE_SIZE : HANDLE_SIZE - 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      });
    }

    // Draw dimensions
    ctx.font = "12px monospace";
    ctx.fillStyle = "#3b82f6";
    const dimText = `${boundingBox.width} \u00d7 ${boundingBox.height}`;
    const textWidth = ctx.measureText(dimText).width;
    ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
    ctx.fillRect(
      scaledBox.x + scaledBox.width / 2 - textWidth / 2 - 4,
      scaledBox.y - 20,
      textWidth + 8,
      16
    );
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.fillText(dimText, scaledBox.x + scaledBox.width / 2, scaledBox.y - 8);

    // Draw in-progress drawing rectangle
    if (drawingRect) {
      const scaled = {
        x: drawingRect.x * zoom + pan.x,
        y: drawingRect.y * zoom + pan.y,
        width: drawingRect.width * zoom,
        height: drawingRect.height * zoom,
      };
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 2;
      ctx.strokeRect(scaled.x, scaled.y, scaled.width, scaled.height);
      ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
      ctx.fillRect(scaled.x, scaled.y, scaled.width, scaled.height);
      ctx.setLineDash([]);
    }
  }, [imageLoaded, zoom, pan, boundingBox, mode, hoveredHandle, imageWidth, imageHeight, drawingRect]);

  // Redraw on changes
  useEffect(() => {
    draw();
  }, [draw]);

  // Generate crop preview when bounding box changes
  useEffect(() => {
    if (!onCropPreview || !imageRef.current || !imageLoaded) return;
    if (boundingBox.width < MIN_BOX_SIZE || boundingBox.height < MIN_BOX_SIZE) return;

    const timer = setTimeout(() => {
      const img = imageRef.current;
      if (!img) return;

      const maxPreviewWidth = 400;
      const scale = Math.min(1, maxPreviewWidth / boundingBox.width);

      const offscreen = document.createElement("canvas");
      offscreen.width = Math.round(boundingBox.width * scale);
      offscreen.height = Math.round(boundingBox.height * scale);
      const ctx = offscreen.getContext("2d");
      if (!ctx) return;

      ctx.drawImage(
        img,
        boundingBox.x, boundingBox.y, boundingBox.width, boundingBox.height,
        0, 0, offscreen.width, offscreen.height
      );

      onCropPreview(offscreen.toDataURL("image/jpeg", 0.85));
    }, 50);

    return () => clearTimeout(timer);
  }, [boundingBox, imageLoaded, onCropPreview]);

  // Handle mouse wheel for zoom
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Calculate zoom
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(5, zoom * delta));

    // Adjust pan to zoom towards cursor
    const scaleFactor = newZoom / zoom;
    const newPanX = x - (x - pan.x) * scaleFactor;
    const newPanY = y - (y - pan.y) * scaleFactor;

    onZoomChange(newZoom);
    onPanChange({ x: newPanX, y: newPanY });
  }, [zoom, pan, onZoomChange, onPanChange]);

  // Attach wheel listener
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  // Handle mouse down
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (mode === "edit-bbox" && !spaceHeldRef.current) {
      const handle = getHandleAtPoint(x, y);
      if (handle) {
        // Resize or move existing box
        interactionRef.current = { type: "resizing", handle, startX: x, startY: y };
      } else {
        // Empty space: start drawing a new bounding box
        const imageX = (x - pan.x) / zoom;
        const imageY = (y - pan.y) / zoom;
        interactionRef.current = { type: "drawing", anchorX: imageX, anchorY: imageY };
        setDrawingRect({ x: imageX, y: imageY, width: 0, height: 0 });
      }
      return;
    }

    // Pan mode (or Space held in edit-bbox mode)
    interactionRef.current = { type: "panning", startX: x - pan.x, startY: y - pan.y };
  };

  // Handle mouse move
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const state = interactionRef.current;

    // Idle: update hover state and cursor
    if (state.type === "idle") {
      if (mode === "edit-bbox" && spaceHeldRef.current) {
        canvas.style.cursor = "grab";
      } else if (mode === "edit-bbox") {
        const handle = getHandleAtPoint(x, y);
        setHoveredHandle(handle);
        canvas.style.cursor = getCursor(handle);
      } else if (mode === "pan") {
        canvas.style.cursor = "grab";
      }
      return;
    }

    // Drawing: update the preview rectangle
    if (state.type === "drawing") {
      canvas.style.cursor = "crosshair";
      const currentX = (x - pan.x) / zoom;
      const currentY = (y - pan.y) / zoom;
      setDrawingRect({
        x: Math.min(state.anchorX, currentX),
        y: Math.min(state.anchorY, currentY),
        width: Math.abs(currentX - state.anchorX),
        height: Math.abs(currentY - state.anchorY),
      });
      return;
    }

    // Resizing/moving the bounding box
    if (state.type === "resizing") {
      const dx = (x - state.startX) / zoom;
      const dy = (y - state.startY) / zoom;

      const newBox = { ...boundingBox };

      switch (state.handle) {
        case "top-left":
          newBox.x = Math.min(boundingBox.x + boundingBox.width - MIN_BOX_SIZE, boundingBox.x + dx);
          newBox.y = Math.min(boundingBox.y + boundingBox.height - MIN_BOX_SIZE, boundingBox.y + dy);
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width - dx);
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height - dy);
          break;
        case "top":
          newBox.y = Math.min(boundingBox.y + boundingBox.height - MIN_BOX_SIZE, boundingBox.y + dy);
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height - dy);
          break;
        case "top-right":
          newBox.y = Math.min(boundingBox.y + boundingBox.height - MIN_BOX_SIZE, boundingBox.y + dy);
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width + dx);
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height - dy);
          break;
        case "left":
          newBox.x = Math.min(boundingBox.x + boundingBox.width - MIN_BOX_SIZE, boundingBox.x + dx);
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width - dx);
          break;
        case "right":
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width + dx);
          break;
        case "bottom-left":
          newBox.x = Math.min(boundingBox.x + boundingBox.width - MIN_BOX_SIZE, boundingBox.x + dx);
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width - dx);
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height + dy);
          break;
        case "bottom":
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height + dy);
          break;
        case "bottom-right":
          newBox.width = Math.max(MIN_BOX_SIZE, boundingBox.width + dx);
          newBox.height = Math.max(MIN_BOX_SIZE, boundingBox.height + dy);
          break;
        case "center":
          newBox.x = boundingBox.x + dx;
          newBox.y = boundingBox.y + dy;
          break;
      }

      // Clamp to image bounds
      newBox.x = Math.max(0, Math.min(imageWidth - newBox.width, newBox.x));
      newBox.y = Math.max(0, Math.min(imageHeight - newBox.height, newBox.y));
      newBox.width = Math.min(imageWidth - newBox.x, newBox.width);
      newBox.height = Math.min(imageHeight - newBox.y, newBox.height);

      // Round to integers
      newBox.x = Math.round(newBox.x);
      newBox.y = Math.round(newBox.y);
      newBox.width = Math.round(newBox.width);
      newBox.height = Math.round(newBox.height);

      onBoundingBoxChange(newBox);
      interactionRef.current = { ...state, startX: x, startY: y };
      return;
    }

    // Panning
    if (state.type === "panning") {
      canvas.style.cursor = "grabbing";
      onPanChange({ x: x - state.startX, y: y - state.startY });
    }
  };

  // Handle mouse up
  const handleMouseUp = () => {
    const state = interactionRef.current;

    if (state.type === "drawing" && drawingRect) {
      if (drawingRect.width >= MIN_BOX_SIZE && drawingRect.height >= MIN_BOX_SIZE) {
        const newBox = {
          x: Math.max(0, Math.round(drawingRect.x)),
          y: Math.max(0, Math.round(drawingRect.y)),
          width: Math.round(drawingRect.width),
          height: Math.round(drawingRect.height),
        };
        // Clamp to image bounds
        newBox.width = Math.min(imageWidth - newBox.x, newBox.width);
        newBox.height = Math.min(imageHeight - newBox.y, newBox.height);
        onBoundingBoxChange(newBox);
      }
      setDrawingRect(null);
    }

    interactionRef.current = { type: "idle" };
    setHoveredHandle(null);
  };

  // Handle mouse leave
  const handleMouseLeave = () => {
    if (interactionRef.current.type === "drawing") {
      setDrawingRect(null);
    }
    interactionRef.current = { type: "idle" };
    setHoveredHandle(null);
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      const step = e.shiftKey ? 10 : 1;
      const newBox = { ...boundingBox };
      let changed = false;

      switch (e.key) {
        case "ArrowLeft":
          newBox.x = Math.max(0, boundingBox.x - step);
          changed = true;
          break;
        case "ArrowRight":
          newBox.x = Math.min(imageWidth - boundingBox.width, boundingBox.x + step);
          changed = true;
          break;
        case "ArrowUp":
          newBox.y = Math.max(0, boundingBox.y - step);
          changed = true;
          break;
        case "ArrowDown":
          newBox.y = Math.min(imageHeight - boundingBox.height, boundingBox.y + step);
          changed = true;
          break;
      }

      if (changed) {
        e.preventDefault();
        onBoundingBoxChange(newBox);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [boundingBox, imageWidth, imageHeight, onBoundingBoxChange]);

  // Space key: hold to pan in edit-bbox mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat) {
        if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
        e.preventDefault();
        spaceHeldRef.current = true;
        const canvas = canvasRef.current;
        if (canvas && mode === "edit-bbox" && interactionRef.current.type === "idle") {
          canvas.style.cursor = "grab";
        }
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        spaceHeldRef.current = false;
        const canvas = canvasRef.current;
        if (canvas && mode === "edit-bbox" && interactionRef.current.type === "idle") {
          canvas.style.cursor = "crosshair";
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [mode]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        className="w-full h-full"
      />
    </div>
  );
}
