"use client";

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Search,
  Filter,
  X,
  Plus,
  SortAsc,
  SortDesc,
  Download,
  RotateCcw,
} from 'lucide-react';

import { useAdvancedSearch, type SearchFilter } from '@/lib/hooks/use-advanced-search';

export interface SearchableField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'date' | 'select' | 'boolean';
  options?: { value: string; label: string }[];
}

export interface AdvancedSearchProps<T> {
  data: T[];
  searchableFields: SearchableField[];
  defaultSearchFields?: string[];
  onResults?: (results: T[]) => void;
  onPaginationChange?: (pagination: { page: number; limit: number; total: number }) => void;
  showExport?: boolean;
  showPagination?: boolean;
  className?: string;
}

export function AdvancedSearch<T>({
  data,
  searchableFields,
  defaultSearchFields,
  onResults,
  onPaginationChange,
  showExport = true,
  showPagination = true,
  className = '',
}: AdvancedSearchProps<T>) {
  const [searchTerm, setSearchTerm] = useState('');
  const [addFilterOpen, setAddFilterOpen] = useState(false);
  const [newFilter, setNewFilter] = useState<Partial<SearchFilter>>({
    field: searchableFields[0]?.key || '',
    operator: 'contains',
    value: '',
  });

  const {
    setSearchQuery,
    filters,
    addFilter,
    removeFilter,
    clearFilters,
    sort,
    setSort,
    pagination,
    setPagination,
    filteredData,
    paginatedData,
    totalResults,
    exportResults,
    reset,
  } = useAdvancedSearch({
    data,
    searchFields: defaultSearchFields,
    defaultPagination: { page: 1, limit: 20 },
  });

  // Update external components when results change
  React.useEffect(() => {
    onResults?.(showPagination ? paginatedData : filteredData);
  }, [filteredData, paginatedData, onResults, showPagination]);

  React.useEffect(() => {
    onPaginationChange?.({
      ...pagination,
      total: totalResults
    });
  }, [pagination, onPaginationChange, totalResults]);

  const handleSearch = (value: string) => {
    setSearchTerm(value);
    setSearchQuery(value);
  };

  const handleAddFilter = () => {
    if (newFilter.field && newFilter.operator && newFilter.value !== '') {
      const field = searchableFields.find(f => f.key === newFilter.field);
      addFilter({
        field: newFilter.field,
        operator: newFilter.operator as SearchFilter['operator'],
        value: newFilter.value ?? '',
        label: field?.label,
      });
      setNewFilter({
        field: searchableFields[0]?.key || '',
        operator: 'contains',
        value: '',
      });
      setAddFilterOpen(false);
    }
  };

  const getOperatorLabel = (operator: string) => {
    const labels: Record<string, string> = {
      equals: 'equals',
      contains: 'contains',
      starts_with: 'starts with',
      ends_with: 'ends with',
      greater_than: 'greater than',
      less_than: 'less than',
      between: 'between',
      in: 'in',
      not_in: 'not in',
    };
    return labels[operator] || operator;
  };

  const getOperatorsForField = (fieldType: string) => {
    switch (fieldType) {
      case 'text':
        return ['equals', 'contains', 'starts_with', 'ends_with'];
      case 'number':
        return ['equals', 'greater_than', 'less_than', 'between'];
      case 'date':
        return ['equals', 'greater_than', 'less_than', 'between'];
      case 'select':
        return ['equals', 'in', 'not_in'];
      case 'boolean':
        return ['equals'];
      default:
        return ['equals', 'contains'];
    }
  };

  const renderFilterValue = (field: SearchableField) => {
    switch (field.type) {
      case 'select':
        return (
          <Select
            value={String(newFilter.value ?? '')}
            onValueChange={(value) => setNewFilter(prev => ({ ...prev, value }))}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select value" />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );

      case 'boolean':
        return (
          <Select
            value={String(newFilter.value ?? '')}
            onValueChange={(value) => setNewFilter(prev => ({ ...prev, value: value === 'true' }))}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select value" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">True</SelectItem>
              <SelectItem value="false">False</SelectItem>
            </SelectContent>
          </Select>
        );

      case 'number':
        return (
          <Input
            type="number"
            placeholder="Enter number"
            value={String(newFilter.value ?? '')}
            onChange={(e) => setNewFilter(prev => ({ ...prev, value: e.target.value }))}
          />
        );

      case 'date':
        return (
          <Input
            type="date"
            value={String(newFilter.value ?? '')}
            onChange={(e) => setNewFilter(prev => ({ ...prev, value: e.target.value }))}
          />
        );

      default:
        return (
          <Input
            placeholder="Enter value"
            value={String(newFilter.value ?? '')}
            onChange={(e) => setNewFilter(prev => ({ ...prev, value: e.target.value }))}
          />
        );
    }
  };

  const selectedField = searchableFields.find(f => f.key === newFilter.field);

  return (
    <Card className={className}>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Advanced Search
          {totalResults > 0 && (
            <Badge variant="secondary" className="ml-2">
              {totalResults.toLocaleString()} results
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Main Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Active Filters */}
        {filters.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">Active Filters</Label>
              <Button size="sm" variant="ghost" onClick={clearFilters}>
                <X className="h-3 w-3 mr-1" />
                Clear All
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {filters.map((filter, index) => (
                <Badge key={index} variant="secondary" className="flex items-center gap-1">
                  <span className="text-xs">
                    {filter.label || filter.field} {getOperatorLabel(filter.operator)} {String(filter.value)}
                  </span>
                  <button
                    onClick={() => removeFilter(index)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Add Filter */}
          <Dialog open={addFilterOpen} onOpenChange={setAddFilterOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Filter className="h-4 w-4 mr-1" />
                Add Filter
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Add Filter</DialogTitle>
                <DialogDescription>
                  Add a new filter to refine your search results
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Field</Label>
                  <Select
                    value={newFilter.field}
                    onValueChange={(value) => setNewFilter(prev => ({ ...prev, field: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {searchableFields.map((field) => (
                        <SelectItem key={field.key} value={field.key}>
                          {field.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Operator</Label>
                  <Select
                    value={newFilter.operator}
                    onValueChange={(value) => setNewFilter(prev => ({ ...prev, operator: value as SearchFilter['operator'] }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {getOperatorsForField(selectedField?.type || 'text').map((operator) => (
                        <SelectItem key={operator} value={operator}>
                          {getOperatorLabel(operator)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Value</Label>
                  {selectedField && renderFilterValue(selectedField)}
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setAddFilterOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddFilter}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Filter
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Sort */}
          <Popover>
            <PopoverTrigger asChild>
              <Button size="sm" variant="outline">
                {sort ? <SortDesc className="h-4 w-4 mr-1" /> : <SortAsc className="h-4 w-4 mr-1" />}
                Sort
                {sort && (
                  <Badge variant="secondary" className="ml-1">
                    {searchableFields.find(f => f.key === sort.field)?.label} {sort.direction}
                  </Badge>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-80">
              <div className="space-y-4">
                <h4 className="font-medium">Sort Results</h4>

                <div className="space-y-2">
                  <Label>Field</Label>
                  <Select
                    value={sort?.field || ''}
                    onValueChange={(field) => {
                      if (field) {
                        setSort({ field, direction: sort?.direction || 'asc' });
                      } else {
                        setSort(null);
                      }
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select field to sort by" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">No sorting</SelectItem>
                      {searchableFields.map((field) => (
                        <SelectItem key={field.key} value={field.key}>
                          {field.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {sort && (
                  <div className="space-y-2">
                    <Label>Direction</Label>
                    <Select
                      value={sort.direction}
                      onValueChange={(direction: 'asc' | 'desc') => {
                        setSort({ ...sort, direction });
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="asc">Ascending</SelectItem>
                        <SelectItem value="desc">Descending</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>

          {/* Export */}
          {showExport && totalResults > 0 && (
            <Popover>
              <PopoverTrigger asChild>
                <Button size="sm" variant="outline">
                  <Download className="h-4 w-4 mr-1" />
                  Export
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-48">
                <div className="space-y-2">
                  <h4 className="font-medium">Export Results</h4>
                  <div className="space-y-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="w-full justify-start"
                      onClick={() => exportResults('csv')}
                    >
                      Export as CSV
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="w-full justify-start"
                      onClick={() => exportResults('json')}
                    >
                      Export as JSON
                    </Button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          )}

          {/* Reset */}
          <Button size="sm" variant="outline" onClick={reset}>
            <RotateCcw className="h-4 w-4 mr-1" />
            Reset
          </Button>
        </div>

        {/* Pagination Info */}
        {showPagination && totalResults > 0 && (
          <div className="flex items-center justify-between text-sm text-muted-foreground border-t pt-4">
            <div>
              Showing {((pagination.page - 1) * pagination.limit) + 1} to{' '}
              {Math.min(pagination.page * pagination.limit, totalResults)} of{' '}
              {totalResults.toLocaleString()} results
            </div>
            <div className="flex items-center gap-2">
              <Label>Per page:</Label>
              <Select
                value={pagination.limit.toString()}
                onValueChange={(value) => setPagination({ limit: Number(value), page: 1 })}
              >
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}