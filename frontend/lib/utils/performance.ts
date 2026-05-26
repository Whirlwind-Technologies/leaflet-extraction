"use client";

import React, { useEffect, useRef, useState } from 'react';

// Performance monitoring utilities
export class PerformanceMonitor {
  private measurements = new Map<string, number>();
  private completedMeasurements = new Map<string, number>();

  // Start timing an operation
  startMeasure(name: string): void {
    this.measurements.set(name, performance.now());
  }

  // End timing and get duration
  endMeasure(name: string): number {
    const start = this.measurements.get(name);
    if (!start) {
      console.warn(`No measurement started for: ${name}`);
      return 0;
    }

    const duration = performance.now() - start;
    this.completedMeasurements.set(name, duration);
    this.measurements.delete(name);

    return duration;
  }

  // Get all completed measurements
  getMeasurements(): Record<string, number> {
    return Object.fromEntries(this.completedMeasurements);
  }

  // Clear all measurements
  clear(): void {
    this.measurements.clear();
    this.completedMeasurements.clear();
  }
}

// Global performance monitor
export const perfMonitor = new PerformanceMonitor();

// Decorator for measuring function performance
export function measured<T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  name?: string
): T {
  const measureName = name || fn.name;

  return ((...args: Parameters<T>) => {
    perfMonitor.startMeasure(measureName);
    try {
      const result = fn(...args);

      // Handle async functions
      if (result && typeof (result as unknown as Promise<unknown>).then === 'function') {
        return (result as unknown as Promise<unknown>).finally(() => {
          const duration = perfMonitor.endMeasure(measureName);
          console.log(`[Performance] ${measureName}: ${duration.toFixed(2)}ms`);
        });
      }

      const duration = perfMonitor.endMeasure(measureName);
      console.log(`[Performance] ${measureName}: ${duration.toFixed(2)}ms`);
      return result;
    } catch (error) {
      perfMonitor.endMeasure(measureName);
      throw error;
    }
  }) as T;
}

// React hook for measuring component render time

export function usePerformanceMonitor(componentName: string) {
  const renderStartRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    // Measure initial render
    if (renderStartRef.current) {
      const duration = performance.now() - renderStartRef.current;
      console.log(`[Render] ${componentName}: ${duration.toFixed(2)}ms`);
    }

    renderStartRef.current = performance.now();
  });

  // Start measuring on component mount
  useEffect(() => {
    renderStartRef.current = performance.now();
  }, []);
}

// Debounce utility for performance optimization
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  wait: number,
  immediate: boolean = false
): T & { cancel: () => void } {
  let timeout: NodeJS.Timeout | null = null;

  const debounced = function (this: unknown, ...args: Parameters<T>) {
    const callNow = immediate && !timeout;

    if (timeout) {
      clearTimeout(timeout);
    }

    timeout = setTimeout(() => {
      timeout = null;
      if (!immediate) func.apply(this, args);
    }, wait);

    if (callNow) {
      return func.apply(this, args);
    }
  } as T & { cancel: () => void };

  debounced.cancel = () => {
    if (timeout) {
      clearTimeout(timeout);
      timeout = null;
    }
  };

  return debounced;
}

// Throttle utility for performance optimization
export function throttle<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  limit: number
): T {
  let inThrottle: boolean;

  return function (this: unknown, ...args: Parameters<T>) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  } as T;
}

// Lazy loading utility
export function createLazyComponent<T extends React.ComponentType<React.ComponentProps<T>>>(
  importFn: () => Promise<{ default: T }>,
): React.LazyExoticComponent<T> {
  return React.lazy(importFn);
}

// Virtual scrolling utility
export interface VirtualScrollOptions {
  itemHeight: number;
  containerHeight: number;
  overscan?: number;
}

export function useVirtualScroll<T>(
  items: T[],
  options: VirtualScrollOptions
) {
  const { itemHeight, containerHeight, overscan = 5 } = options;
  const [scrollTop, setScrollTop] = useState(0);

  const visibleItemsCount = Math.ceil(containerHeight / itemHeight);
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const endIndex = Math.min(
    items.length - 1,
    startIndex + visibleItemsCount + overscan * 2
  );

  const visibleItems = items.slice(startIndex, endIndex + 1);
  const totalHeight = items.length * itemHeight;
  const offsetY = startIndex * itemHeight;

  const handleScroll = React.useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  return {
    visibleItems,
    totalHeight,
    offsetY,
    startIndex,
    endIndex,
    handleScroll,
  };
}

// Intersection Observer utility for lazy loading
export function useIntersectionObserver(
  callback: IntersectionObserverCallback,
  options?: IntersectionObserverInit
) {
  const targetRef = useRef<HTMLElement>(null);
  const observerRef = useRef<IntersectionObserver | undefined>(undefined);

  useEffect(() => {
    if (targetRef.current && 'IntersectionObserver' in window) {
      observerRef.current = new IntersectionObserver(callback, options);
      observerRef.current.observe(targetRef.current);
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [callback, options]);

  return targetRef;
}

// Image lazy loading hook
export function useLazyImage(src: string, placeholder?: string) {
  const [imageSrc, setImageSrc] = useState(placeholder || '');
  const [isLoaded, setIsLoaded] = useState(false);
  const [isError, setIsError] = useState(false);

  const imgRef = useIntersectionObserver(
    ([entry]) => {
      if (entry.isIntersecting && !isLoaded && !isError) {
        const img = new Image();
        img.onload = () => {
          setImageSrc(src);
          setIsLoaded(true);
        };
        img.onerror = () => {
          setIsError(true);
        };
        img.src = src;
      }
    },
    { threshold: 0.1, rootMargin: '50px' }
  );

  return {
    ref: imgRef,
    src: imageSrc,
    isLoaded,
    isError,
  };
}

// Bundle size utilities
interface NetworkConnection {
  downlink?: number;
}

export function getBundleSize(): number {
  if (typeof navigator !== 'undefined' && 'connection' in navigator) {
    const connection = (navigator as unknown as { connection: NetworkConnection }).connection;
    return connection?.downlink || 0;
  }
  return 0;
}

// Memory usage utilities
interface PerformanceMemory {
  usedJSHeapSize: number;
  totalJSHeapSize: number;
  jsHeapSizeLimit: number;
}

export function getMemoryUsage() {
  if ('memory' in performance) {
    const memory = (performance as unknown as { memory: PerformanceMemory }).memory;
    return {
      usedJSHeapSize: memory.usedJSHeapSize,
      totalJSHeapSize: memory.totalJSHeapSize,
      jsHeapSizeLimit: memory.jsHeapSizeLimit,
      usage: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100,
    };
  }
  return null;
}

// FPS monitoring
export class FPSMonitor {
  private lastTime = 0;
  private frames = 0;
  private fps = 0;
  private isRunning = false;
  private callbacks: ((fps: number) => void)[] = [];

  start(): void {
    if (this.isRunning) return;

    this.isRunning = true;
    this.lastTime = performance.now();
    this.frames = 0;
    this.tick();
  }

  stop(): void {
    this.isRunning = false;
  }

  onFPSUpdate(callback: (fps: number) => void): () => void {
    this.callbacks.push(callback);

    return () => {
      const index = this.callbacks.indexOf(callback);
      if (index > -1) {
        this.callbacks.splice(index, 1);
      }
    };
  }

  getFPS(): number {
    return this.fps;
  }

  private tick = (): void => {
    if (!this.isRunning) return;

    const now = performance.now();
    this.frames++;

    if (now - this.lastTime >= 1000) {
      this.fps = Math.round((this.frames * 1000) / (now - this.lastTime));
      this.callbacks.forEach(callback => callback(this.fps));
      this.frames = 0;
      this.lastTime = now;
    }

    requestAnimationFrame(this.tick);
  };
}

// Global FPS monitor
export const fpsMonitor = new FPSMonitor();

// React hook for FPS monitoring
export function useFPS() {
  const [fps, setFPS] = useState(60);

  useEffect(() => {
    const unsubscribe = fpsMonitor.onFPSUpdate(setFPS);
    fpsMonitor.start();

    return () => {
      unsubscribe();
      fpsMonitor.stop();
    };
  }, []);

  return fps;
}

// Web Vitals utilities
export interface WebVitals {
  FCP?: number; // First Contentful Paint
  LCP?: number; // Largest Contentful Paint
  FID?: number; // First Input Delay
  CLS?: number; // Cumulative Layout Shift
  TTFB?: number; // Time to First Byte
}

export function measureWebVitals(): Promise<WebVitals> {
  return new Promise((resolve) => {
    const vitals: WebVitals = {};

    // Measure TTFB
    if ('navigation' in performance) {
      const navTiming = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      vitals.TTFB = navTiming.responseStart - navTiming.requestStart;
    }

    // Basic implementation using available performance APIs
    if (typeof window !== 'undefined') {
      // Use basic performance metrics
      setTimeout(() => {
        // Get paint timing if available
        const paintEntries = performance.getEntriesByType('paint');
        const fcpEntry = paintEntries.find(entry => entry.name === 'first-contentful-paint');
        const lcpEntries = performance.getEntriesByType('largest-contentful-paint');

        vitals.FCP = fcpEntry?.startTime || performance.now();
        vitals.LCP = lcpEntries[lcpEntries.length - 1]?.startTime || performance.now();
        vitals.CLS = 0; // Basic implementation
        vitals.FID = 0; // Basic implementation

        resolve(vitals);
      }, 0);
    } else {
      resolve(vitals);
    }
  });
}

// Performance optimization recommendations
export function getPerformanceRecommendations(): string[] {
  const recommendations: string[] = [];

  // Check bundle size
  const connectionSpeed = getBundleSize();
  if (connectionSpeed > 0 && connectionSpeed < 1) {
    recommendations.push('Consider code splitting to reduce initial bundle size for slow connections');
  }

  // Check memory usage
  const memory = getMemoryUsage();
  if (memory && memory.usage > 80) {
    recommendations.push('High memory usage detected - consider optimizing component re-renders');
  }

  // Check FPS
  const fps = fpsMonitor.getFPS();
  if (fps < 30) {
    recommendations.push('Low FPS detected - consider optimizing animations and heavy computations');
  }

  return recommendations;
}
