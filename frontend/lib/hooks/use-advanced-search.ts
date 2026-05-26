"use client";

import { useState, useCallback, useMemo } from 'react';

// Simple debounce utility
const debounce = <T extends (...args: Parameters<T>) => ReturnType<T>>(func: T, wait: number) => {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

export interface SearchFilter {
  field: string;
  operator: 'equals' | 'contains' | 'starts_with' | 'ends_with' | 'greater_than' | 'less_than' | 'between' | 'in' | 'not_in';
  value: string | number | boolean;
  label?: string;
}

export interface SortOption {
  field: string;
  direction: 'asc' | 'desc';
  label?: string;
}

export interface PaginationOptions {
  page: number;
  limit: number;
  total?: number;
}

export interface AdvancedSearchOptions<T = Record<string, unknown>> {
  data: T[];
  searchFields?: string[];
  defaultFilters?: SearchFilter[];
  defaultSort?: SortOption | null;
  defaultPagination?: Partial<PaginationOptions>;
  debounceMs?: number;
}

export interface AdvancedSearchReturn<T = Record<string, unknown>> {
  // Search state
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // Filters
  filters: SearchFilter[];
  addFilter: (filter: SearchFilter) => void;
  removeFilter: (index: number) => void;
  updateFilter: (index: number, filter: SearchFilter) => void;
  clearFilters: () => void;

  // Sorting
  sort: SortOption | null;
  setSort: (sort: SortOption | null) => void;

  // Pagination
  pagination: PaginationOptions;
  setPagination: (pagination: Partial<PaginationOptions>) => void;

  // Results
  filteredData: T[];
  paginatedData: T[];
  totalResults: number;

  // Utilities
  exportResults: (format: 'csv' | 'json') => void;
  reset: () => void;
}

export function useAdvancedSearch<T = Record<string, unknown>>({
  data,
  searchFields = [],
  defaultFilters = [],
  defaultSort = null,
  defaultPagination = { page: 1, limit: 50 },
  debounceMs = 300,
}: AdvancedSearchOptions<T>): AdvancedSearchReturn<T> {

  const [searchQuery, setSearchQueryState] = useState('');
  const [filters, setFilters] = useState<SearchFilter[]>(defaultFilters);
  const [sort, setSort] = useState<SortOption | null>(defaultSort);
  const [pagination, setPaginationState] = useState<PaginationOptions>({
    page: defaultPagination.page || 1,
    limit: defaultPagination.limit || 50,
    total: 0,
  });

  // Debounced search query setter
  const debouncedSetSearch = useMemo(
    () =>
      debounce((query: string) => {
        setSearchQueryState(query);
        setPaginationState(prev => ({ ...prev, page: 1 })); // Reset to first page on search
      }, debounceMs),
    [debounceMs]
  );

  const setSearchQuery = useCallback((query: string) => {
    debouncedSetSearch(query);
  }, [debouncedSetSearch]);

  // Filter operations
  const addFilter = useCallback((filter: SearchFilter) => {
    setFilters(prev => [...prev, filter]);
    setPaginationState(prev => ({ ...prev, page: 1 }));
  }, []);

  const removeFilter = useCallback((index: number) => {
    setFilters(prev => prev.filter((_, i) => i !== index));
    setPaginationState(prev => ({ ...prev, page: 1 }));
  }, []);

  const updateFilter = useCallback((index: number, filter: SearchFilter) => {
    setFilters(prev => prev.map((f, i) => i === index ? filter : f));
    setPaginationState(prev => ({ ...prev, page: 1 }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters([]);
    setPaginationState(prev => ({ ...prev, page: 1 }));
  }, []);

  // Pagination operations
  const setPagination = useCallback((newPagination: Partial<PaginationOptions>) => {
    setPaginationState(prev => ({ ...prev, ...newPagination }));
  }, []);

  // Apply search query to data
  const searchedData = useMemo(() => {
    if (!searchQuery.trim()) return data;

    const query = searchQuery.toLowerCase();
    return data.filter((item) => {
      if (searchFields.length === 0) {
        // Search all string fields if no specific fields provided
        return Object.values(item as Record<string, unknown>).some((value) =>
          typeof value === 'string' && value.toLowerCase().includes(query)
        );
      }

      // Search specific fields
      return searchFields.some(field => {
        const value = getNestedValue(item, field);
        return typeof value === 'string' && value.toLowerCase().includes(query);
      });
    });
  }, [data, searchQuery, searchFields]);

  // Apply filters to data
  const filteredData = useMemo(() => {
    if (filters.length === 0) return searchedData;

    return searchedData.filter((item) => {
      return filters.every(filter => {
        const value = getNestedValue(item, filter.field);
        return applyFilter(value, filter);
      });
    });
  }, [searchedData, filters]);

  // Apply sorting to data
  const sortedData = useMemo(() => {
    if (!sort) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aValue = getNestedValue(a, sort.field);
      const bValue = getNestedValue(b, sort.field);

      // Coerce to string for comparison of unknown values
      const aStr = String(aValue ?? '');
      const bStr = String(bValue ?? '');

      // Try numeric comparison first
      const aNum = Number(aValue);
      const bNum = Number(bValue);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        const comparison = aNum - bNum;
        return sort.direction === 'desc' ? -comparison : comparison;
      }

      let comparison = 0;
      if (aStr < bStr) comparison = -1;
      if (aStr > bStr) comparison = 1;

      return sort.direction === 'desc' ? comparison * -1 : comparison;
    });
  }, [filteredData, sort]);

  // Apply pagination to data
  const paginatedData = useMemo(() => {
    const startIndex = (pagination.page - 1) * pagination.limit;
    const endIndex = startIndex + pagination.limit;
    return sortedData.slice(startIndex, endIndex);
  }, [sortedData, pagination.page, pagination.limit]);

  // Derive total results from sorted data length
  const totalResults = sortedData.length;

  // Export functionality
  const exportResults = useCallback((format: 'csv' | 'json') => {
    const dataToExport = filteredData;

    if (format === 'csv') {
      const csv = convertToCSV(dataToExport as Record<string, unknown>[]);
      downloadFile(csv, 'search-results.csv', 'text/csv');
    } else if (format === 'json') {
      const json = JSON.stringify(dataToExport, null, 2);
      downloadFile(json, 'search-results.json', 'application/json');
    }
  }, [filteredData]);

  // Reset all filters and search
  const reset = useCallback(() => {
    setSearchQueryState('');
    setFilters(defaultFilters);
    setSort(defaultSort);
    setPaginationState({
      page: defaultPagination.page || 1,
      limit: defaultPagination.limit || 50,
      total: 0,
    });
  }, [defaultFilters, defaultSort, defaultPagination]);

  return {
    searchQuery,
    setSearchQuery,
    filters,
    addFilter,
    removeFilter,
    updateFilter,
    clearFilters,
    sort,
    setSort,
    pagination,
    setPagination,
    filteredData: sortedData,
    paginatedData,
    totalResults,
    exportResults,
    reset,
  };
}

// Helper functions

function getNestedValue(obj: unknown, path: string): unknown {
  return path.split('.').reduce((current: unknown, key) => {
    if (current && typeof current === 'object' && key in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

function applyFilter(value: unknown, filter: SearchFilter): boolean {
  const { operator, value: filterValue } = filter;

  switch (operator) {
    case 'equals':
      return value === filterValue;

    case 'contains':
      return typeof value === 'string' && typeof filterValue === 'string' &&
             value.toLowerCase().includes(filterValue.toLowerCase());

    case 'starts_with':
      return typeof value === 'string' && typeof filterValue === 'string' &&
             value.toLowerCase().startsWith(filterValue.toLowerCase());

    case 'ends_with':
      return typeof value === 'string' && typeof filterValue === 'string' &&
             value.toLowerCase().endsWith(filterValue.toLowerCase());

    case 'greater_than':
      return Number(value) > Number(filterValue);

    case 'less_than':
      return Number(value) < Number(filterValue);

    case 'between': {
      const [min, max] = Array.isArray(filterValue) ? filterValue : [0, 0];
      return Number(value) >= Number(min) && Number(value) <= Number(max);
    }

    case 'in':
      return Array.isArray(filterValue) && filterValue.includes(value);

    case 'not_in':
      return Array.isArray(filterValue) && !filterValue.includes(value);

    default:
      return true;
  }
}

function convertToCSV(data: Record<string, unknown>[]): string {
  if (data.length === 0) return '';

  const headers = Object.keys(data[0]);
  const csvHeaders = headers.join(',');

  const csvRows = data.map(row =>
    headers.map(header => {
      const value = row[header];
      // Escape and quote values that contain commas, quotes, or newlines
      if (typeof value === 'string' && (value.includes(',') || value.includes('"') || value.includes('\n'))) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value ?? '';
    }).join(',')
  );

  return [csvHeaders, ...csvRows].join('\n');
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}
