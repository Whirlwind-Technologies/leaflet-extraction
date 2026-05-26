"use client";

// Memory-based cache with TTL support
class MemoryCache {
  private cache = new Map<string, { data: unknown; expires: number }>();
  private timers = new Map<string, NodeJS.Timeout>();

  set(key: string, data: unknown, ttlMs: number = 300000) { // 5 minutes default
    // Clear existing timer if any
    this.clearTimer(key);

    const expires = Date.now() + ttlMs;
    this.cache.set(key, { data, expires });

    // Set expiration timer
    const timer = setTimeout(() => {
      this.delete(key);
    }, ttlMs);
    this.timers.set(key, timer);
  }

  get<T = unknown>(key: string): T | null {
    const item = this.cache.get(key);
    if (!item) return null;

    if (Date.now() > item.expires) {
      this.delete(key);
      return null;
    }

    return item.data as T;
  }

  has(key: string): boolean {
    const item = this.cache.get(key);
    if (!item) return false;

    if (Date.now() > item.expires) {
      this.delete(key);
      return false;
    }

    return true;
  }

  delete(key: string): boolean {
    this.clearTimer(key);
    return this.cache.delete(key);
  }

  clear(): void {
    this.timers.forEach((timer) => clearTimeout(timer));
    this.timers.clear();
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }

  private clearTimer(key: string): void {
    const timer = this.timers.get(key);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(key);
    }
  }
}

// Global cache instance
const globalCache = new MemoryCache();

// Cache decorator for functions
export function cached<T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  options: {
    keyGenerator?: (...args: Parameters<T>) => string;
    ttl?: number;
    cacheInstance?: MemoryCache;
  } = {}
): T {
  const {
    keyGenerator = (...args: Parameters<T>) => JSON.stringify(args),
    ttl = 300000, // 5 minutes
    cacheInstance = globalCache,
  } = options;

  return ((...args: Parameters<T>) => {
    const cacheKey = `${fn.name}_${keyGenerator(...args)}`;

    // Try to get from cache first
    const cachedValue = cacheInstance.get(cacheKey);
    if (cachedValue !== null) {
      return cachedValue;
    }

    // Execute function and cache result
    const result = fn(...args);
    cacheInstance.set(cacheKey, result, ttl);
    return result;
  }) as T;
}

// Async cache decorator
export function cachedAsync<T extends (...args: Parameters<T>) => Promise<unknown>>(
  fn: T,
  options: {
    keyGenerator?: (...args: Parameters<T>) => string;
    ttl?: number;
    cacheInstance?: MemoryCache;
  } = {}
): T {
  const {
    keyGenerator = (...args: Parameters<T>) => JSON.stringify(args),
    ttl = 300000, // 5 minutes
    cacheInstance = globalCache,
  } = options;

  const pendingPromises = new Map<string, Promise<unknown>>();

  return (async (...args: Parameters<T>) => {
    const cacheKey = `${fn.name}_${keyGenerator(...args)}`;

    // Try to get from cache first
    const cachedValue = cacheInstance.get(cacheKey);
    if (cachedValue !== null) {
      return cachedValue;
    }

    // Check if there's already a pending promise for this key
    const pendingPromise = pendingPromises.get(cacheKey);
    if (pendingPromise) {
      return pendingPromise;
    }

    // Execute function and cache result
    const promise = fn(...args).then((result) => {
      cacheInstance.set(cacheKey, result, ttl);
      pendingPromises.delete(cacheKey);
      return result;
    }).catch((error) => {
      pendingPromises.delete(cacheKey);
      throw error;
    });

    pendingPromises.set(cacheKey, promise);
    return promise;
  }) as T;
}

// Local Storage cache with expiration
export class LocalStorageCache {
  private prefix: string;

  constructor(prefix: string = 'app_cache_') {
    this.prefix = prefix;
  }

  set(key: string, data: unknown, ttlMs: number = 300000): void {
    try {
      const item = {
        data,
        expires: Date.now() + ttlMs,
      };
      localStorage.setItem(this.prefix + key, JSON.stringify(item));
    } catch (error) {
      console.warn('Failed to set localStorage cache:', error);
    }
  }

  get<T = unknown>(key: string): T | null {
    try {
      const itemStr = localStorage.getItem(this.prefix + key);
      if (!itemStr) return null;

      const item = JSON.parse(itemStr);
      if (Date.now() > item.expires) {
        this.delete(key);
        return null;
      }

      return item.data;
    } catch (error) {
      console.warn('Failed to get localStorage cache:', error);
      return null;
    }
  }

  has(key: string): boolean {
    return this.get(key) !== null;
  }

  delete(key: string): void {
    try {
      localStorage.removeItem(this.prefix + key);
    } catch (error) {
      console.warn('Failed to delete localStorage cache:', error);
    }
  }

  clear(): void {
    try {
      const keys = Object.keys(localStorage).filter(key =>
        key.startsWith(this.prefix)
      );
      keys.forEach(key => localStorage.removeItem(key));
    } catch (error) {
      console.warn('Failed to clear localStorage cache:', error);
    }
  }

  // Clean expired items
  cleanup(): void {
    try {
      const keys = Object.keys(localStorage).filter(key =>
        key.startsWith(this.prefix)
      );

      keys.forEach(key => {
        try {
          const itemStr = localStorage.getItem(key);
          if (itemStr) {
            const item = JSON.parse(itemStr);
            if (Date.now() > item.expires) {
              localStorage.removeItem(key);
            }
          }
        } catch {
          // Invalid item, remove it
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.warn('Failed to cleanup localStorage cache:', error);
    }
  }
}

// Query cache for API calls
export class QueryCache {
  private cache: MemoryCache;
  private localStorage: LocalStorageCache;

  constructor() {
    this.cache = new MemoryCache();
    this.localStorage = new LocalStorageCache('query_cache_');
  }

  async query<T>(
    key: string,
    queryFn: () => Promise<T>,
    options: {
      memoryTtl?: number;
      storageTtl?: number;
      staleWhileRevalidate?: boolean;
    } = {}
  ): Promise<T> {
    const {
      memoryTtl = 60000, // 1 minute
      storageTtl = 600000, // 10 minutes
      staleWhileRevalidate = true,
    } = options;

    // Try memory cache first
    let cachedValue = this.cache.get<T>(key);
    if (cachedValue !== null) {
      return cachedValue;
    }

    // Try localStorage cache
    cachedValue = this.localStorage.get<T>(key);
    if (cachedValue !== null) {
      // Store in memory cache for faster access
      this.cache.set(key, cachedValue, memoryTtl);

      if (staleWhileRevalidate) {
        // Fetch fresh data in background
        this.fetchAndCache(key, queryFn, memoryTtl, storageTtl);
      }

      return cachedValue;
    }

    // No cache, fetch fresh data
    return this.fetchAndCache(key, queryFn, memoryTtl, storageTtl);
  }

  private async fetchAndCache<T>(
    key: string,
    queryFn: () => Promise<T>,
    memoryTtl: number,
    storageTtl: number
  ): Promise<T> {
    const data = await queryFn();

    // Cache in both memory and storage
    this.cache.set(key, data, memoryTtl);
    this.localStorage.set(key, data, storageTtl);

    return data;
  }

  invalidate(key: string): void {
    this.cache.delete(key);
    this.localStorage.delete(key);
  }

  invalidatePattern(_pattern: RegExp): void {
    // Clear memory cache
    this.cache.clear();

    // Clear matching localStorage items
    try {
      const keys = Object.keys(localStorage).filter(key =>
        key.startsWith('query_cache_') && _pattern.test(key)
      );
      keys.forEach(key => localStorage.removeItem(key));
    } catch (error) {
      console.warn('Failed to invalidate cache pattern:', error);
    }
  }

  clear(): void {
    this.cache.clear();
    this.localStorage.clear();
  }
}

// Global instances
export const memoryCache = globalCache;
export const localStorageCache = new LocalStorageCache();
export const queryCache = new QueryCache();

// React hooks for caching
import { useCallback, useMemo, useRef } from 'react';

export function useMemoryCache() {
  return {
    set: useCallback((key: string, data: unknown, ttl?: number) =>
      memoryCache.set(key, data, ttl), []),
    get: useCallback(<T = unknown>(key: string) =>
      memoryCache.get<T>(key), []),
    has: useCallback((key: string) =>
      memoryCache.has(key), []),
    delete: useCallback((key: string) =>
      memoryCache.delete(key), []),
    clear: useCallback(() =>
      memoryCache.clear(), []),
  };
}

export function useCachedCallback<T extends (...args: Parameters<T>) => ReturnType<T>>(
  callback: T,
  deps: React.DependencyList,
  options: {
    ttl?: number;
    keyGenerator?: (...args: Parameters<T>) => string;
  } = {}
): T {
  const cachedFnRef = useRef<T | undefined>(undefined);

  // Recreate the cached function when dependencies change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const memoizedCallback = useMemo(() => cached(callback, options), deps);

  cachedFnRef.current = memoizedCallback;

  return cachedFnRef.current;
}

// Cleanup function to run periodically
export function startCacheCleanup(intervalMs: number = 600000) { // 10 minutes
  const cleanup = () => {
    localStorageCache.cleanup();
  };

  // Initial cleanup
  cleanup();

  // Periodic cleanup
  const interval = setInterval(cleanup, intervalMs);

  return () => clearInterval(interval);
}
