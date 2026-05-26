"use client";

import { useState, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Calculator, ArrowRight, RotateCcw } from "lucide-react";

interface DiscountCalculatorProps {
  regularPrice?: string;
  discountedPrice?: string;
  discountPercentage?: string;
  onApply: (values: {
    regularPrice: string;
    discountedPrice: string;
    discountPercentage: string;
  }) => void;
}

type CalculationMode = "from-prices" | "from-regular-and-percent" | "from-discounted-and-percent";

export function DiscountCalculator({
  regularPrice = "",
  discountedPrice = "",
  discountPercentage = "",
  onApply,
}: DiscountCalculatorProps) {
  const [mode, setMode] = useState<CalculationMode>("from-prices");
  const [values, setValues] = useState({
    regular: regularPrice,
    discounted: discountedPrice,
    percentage: discountPercentage,
  });
  
  // Calculate result based on mode - using useMemo instead of useEffect
  const calculated = useMemo(() => {
    const regular = parseFloat(values.regular);
    const discounted = parseFloat(values.discounted);
    const percentage = parseFloat(values.percentage);
    
    switch (mode) {
      case "from-prices":
        if (regular > 0 && discounted > 0 && regular > discounted) {
          const calc = ((regular - discounted) / regular) * 100;
          return {
            result: `Discount: ${parseFloat(calc.toFixed(2))}%`,
            calculatedPercentage: calc.toString(),
          };
        }
        break;
        
      case "from-regular-and-percent":
        if (regular > 0 && percentage > 0 && percentage < 100) {
          const calc = regular * (1 - percentage / 100);
          return {
            result: `Discounted Price: ${calc}`,
            calculatedDiscounted: calc.toString(),
          };
        }
        break;
        
      case "from-discounted-and-percent":
        if (discounted > 0 && percentage > 0 && percentage < 100) {
          const calc = discounted / (1 - percentage / 100);
          return {
            result: `Regular Price: ${calc}`,
            calculatedRegular: calc.toString(),
          };
        }
        break;
    }
    
    return null;
  }, [mode, values.regular, values.discounted, values.percentage]);
  
  const handleReset = () => {
    setValues({
      regular: regularPrice,
      discounted: discountedPrice,
      percentage: discountPercentage,
    });
  };
  
  const handleApply = () => {
    // Apply calculated values along with entered values
    const finalValues = {
      regularPrice: calculated?.calculatedRegular || values.regular,
      discountedPrice: calculated?.calculatedDiscounted || values.discounted,
      discountPercentage: calculated?.calculatedPercentage || values.percentage,
    };
    onApply(finalValues);
  };
  
  return (
    <Card className="bg-primary/10 border-primary">
      <CardContent className="p-3 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <Calculator className="h-4 w-4" />
          Discount Calculator
        </div>

        {/* Mode selection */}
        <div className="flex gap-1">
          <Button
            variant={mode === "from-prices" ? "default" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setMode("from-prices")}
          >
            Prices → %
          </Button>
          <Button
            variant={mode === "from-regular-and-percent" ? "default" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setMode("from-regular-and-percent")}
          >
            Regular + % → Sale
          </Button>
          <Button
            variant={mode === "from-discounted-and-percent" ? "default" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setMode("from-discounted-and-percent")}
          >
            Sale + % → Regular
          </Button>
        </div>

        {/* Input fields */}
        <div className="grid grid-cols-3 gap-2">
          <div>
            <Label className="text-xs text-primary">Regular</Label>
            <Input
              type="number"
              step="0.01"
              value={values.regular}
              onChange={(e) => setValues(prev => ({ ...prev, regular: e.target.value }))}
              className="h-8 bg-background"
              disabled={mode === "from-discounted-and-percent"}
            />
          </div>
          <div>
            <Label className="text-xs text-primary">Discounted</Label>
            <Input
              type="number"
              step="0.01"
              value={values.discounted}
              onChange={(e) => setValues(prev => ({ ...prev, discounted: e.target.value }))}
              className="h-8 bg-background"
              disabled={mode === "from-regular-and-percent"}
            />
          </div>
          <div>
            <Label className="text-xs text-primary">Discount %</Label>
            <Input
              type="number"
              step="0.1"
              value={values.percentage}
              onChange={(e) => setValues(prev => ({ ...prev, percentage: e.target.value }))}
              className="h-8 bg-background"
              disabled={mode === "from-prices"}
            />
          </div>
        </div>

        {/* Result */}
        {calculated?.result && (
          <div className="text-sm font-medium flex items-center gap-2 text-primary">
            <ArrowRight className="h-4 w-4" />
            {calculated.result}
          </div>
        )}

        {/* Quick calculations */}
        <div className="flex flex-wrap gap-1">
          <span className="text-xs text-muted-foreground">Quick:</span>
          {[10, 20, 25, 30, 33, 50].map((pct) => (
            <Button
              key={pct}
              variant="outline"
              size="sm"
              className="h-6 text-xs px-2"
              onClick={() => {
                setMode("from-regular-and-percent");
                setValues(prev => ({ ...prev, percentage: pct.toString() }));
              }}
            >
              -{pct}%
            </Button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="h-7 text-xs text-muted-foreground"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            Reset
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleApply}
            className="h-7 text-xs flex-1"
          >
            Apply Values
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}