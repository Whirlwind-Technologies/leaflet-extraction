import { Suspense } from "react";
import { notFound, redirect } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProductHistory } from "@/components/review/product-history";
import { getProduct, getProductReviews } from "@/lib/actions/products";
import { getLeafletPages } from "@/lib/actions/leaflets";
import { cookies } from "next/headers";
import {
  ArrowLeft,
  Edit2,
  ImageIcon,
  Folder,
} from "lucide-react";

interface ProductDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { id } = await params;

  return (
    <div className="container mx-auto pb-6 max-w-7xl space-y-6">
      <Suspense fallback={<ProductDetailSkeleton />}>
        <ProductDetailWrapper productId={id} />
      </Suspense>
    </div>
  );
}

async function ProductDetailWrapper({ productId }: { productId: string }) {
  // Check if user is authenticated
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  
  if (!token) {
    redirect("/login");
  }
  
  const [product, reviews] = await Promise.all([
    getProduct(productId),
    getProductReviews(productId),
  ]);
  
  if (!product) {
    // Could be auth error or not found - check token again
    const currentToken = cookieStore.get("access_token")?.value;
    if (!currentToken) {
      redirect("/login");
    }
    notFound();
  }
  
  await getLeafletPages(product.leaflet_id);
  
  const statusConfig: Record<string, { label: string; className: string }> = {
    pending: { label: "Pending Review", className: "bg-yellow-100 text-yellow-800" },
    auto_approved: { label: "Auto Approved", className: "bg-green-100 text-green-800" },
    approved: { label: "Approved", className: "bg-green-100 text-green-800" },
    rejected: { label: "Rejected", className: "bg-red-100 text-red-800" },
    needs_correction: { label: "Needs Correction", className: "bg-orange-100 text-orange-800" },
  };
  
  const statusCfg = statusConfig[product.review_status] || { label: product.review_status, className: "bg-gray-100" };
  
  // Get accessible URL for image - handle both new format and legacy
  const getProductImageSrc = () => {
    // Try new format first
    if (product.image?.data) {
      return product.image.data.startsWith("data:") 
        ? product.image.data 
        : `data:image/png;base64,${product.image.data}`;
    }
    if (product.image?.url) {
      return product.image.url
        .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
        .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
    }
    
    // Try legacy fields
    if (product.image_base64) {
      return product.image_base64.startsWith("data:") 
        ? product.image_base64 
        : `data:image/png;base64,${product.image_base64}`;
    }
    if (product.image_url) {
      return product.image_url
        .replace(/http:\/\/minio:9000/g, "http://localhost:9000")
        .replace(/https:\/\/minio:9000/g, "http://localhost:9000");
    }
    
    return null;
  };
  
  const imageSrc = getProductImageSrc();
  
  return (
    <>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/review">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-light text-[#2D3748] tracking-tight">{product.product_name}</h1>
            <p className="text-sm font-light text-[#6B7280]">
              {product.brand && `${product.brand} • `}
              Page {product.page_number}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={statusCfg.className}>
            {statusCfg.label}
          </Badge>
          <Button asChild>
            <Link href={`/products/${productId}/edit?leaflet_id=${product.leaflet_id}`}>
              <Edit2 className="h-4 w-4 mr-2" />
              Edit
            </Link>
          </Button>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Product info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Product Image */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Product Image</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="aspect-video bg-muted rounded-lg overflow-hidden relative flex items-center justify-center">
                {imageSrc ? (
                  <Image
                    src={imageSrc}
                    alt={product.product_name}
                    fill
                    className="object-contain p-2"
                    unoptimized
                  />
                ) : (
                  <div className="text-muted-foreground flex flex-col items-center gap-2">
                    <ImageIcon className="h-12 w-12" />
                    <span>No image available</span>
                  </div>
                )}
              </div>
              {product.image_quality_score !== null && (
                <p className="text-sm text-muted-foreground mt-2">
                  Image quality: {Math.round(product.image_quality_score * 100)}%
                </p>
              )}
            </CardContent>
          </Card>
          
          {/* Product Details */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Product Details</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">Brand</dt>
                  <dd className="font-medium">{product.brand || "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Product Code</dt>
                  <dd className="font-medium">{product.product_code || "—"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Quantity</dt>
                  <dd className="font-medium">
                    {product.quantity && product.units
                      ? `${product.quantity} ${product.units}`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Product ID/EAN</dt>
                  <dd className="font-medium">{product.product_id || "—"}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Category</dt>
                  <dd className="font-medium mt-1">
                    {product.category ? (
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="gap-1">
                          <Folder className="h-3 w-3" />
                          {product.category}
                        </Badge>
                        {product.category_confidence !== null && (
                          <span className="text-xs text-muted-foreground">
                            ({Math.round(product.category_confidence * 100)}% confidence)
                          </span>
                        )}
                      </div>
                    ) : (
                      "—"
                    )}
                    {product.suggested_category && product.suggested_category !== product.category && (
                      <p className="text-xs text-muted-foreground mt-1">
                        AI suggested: {product.suggested_category}
                      </p>
                    )}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
          
          {/* Pricing */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Pricing</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-4 mb-4">
                {product.discounted_price !== null && (
                  <span className="text-3xl font-bold text-primary">
                    {product.currency || "€"}{product.discounted_price.toFixed(2)}
                  </span>
                )}
                {product.discounted_price === null && product.regular_price !== null && (
                  <span className="text-3xl font-bold text-primary">
                    {product.currency || "€"}{product.regular_price.toFixed(2)}
                  </span>
                )}
                {product.regular_price !== null && product.discounted_price !== null && product.regular_price !== product.discounted_price && (
                  <span className="text-xl text-muted-foreground line-through">
                    {product.currency || "€"}{product.regular_price.toFixed(2)}
                  </span>
                )}
                {product.discount_percentage !== null && product.discount_percentage > 0 && (
                  <Badge variant="destructive">
                    -{parseFloat(product.discount_percentage.toFixed(2))}%
                  </Badge>
                )}
              </div>
              
              {product.promotional_info && (
                <p className="text-sm text-muted-foreground">
                  {product.promotional_info}
                </p>
              )}
            </CardContent>
          </Card>
          
          {/* Bounding Box */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Bounding Box</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">X</dt>
                  <dd className="font-mono">{product.bounding_box.x}px</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Y</dt>
                  <dd className="font-mono">{product.bounding_box.y}px</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Width</dt>
                  <dd className="font-mono">{product.bounding_box.width}px</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Height</dt>
                  <dd className="font-mono">{product.bounding_box.height}px</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
        
        {/* Right column - Confidence & History */}
        <div className="space-y-6">
          {/* Confidence Scores */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Confidence Scores</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Overall</span>
                    <span className="font-medium">
                      {product.confidence ? `${Math.round(product.confidence * 100)}%` : "—"}
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${(product.confidence || 0) * 100}%` }}
                    />
                  </div>
                </div>
                
                {product.field_confidence && Object.entries(product.field_confidence).map(([field, score]) => (
                  score !== null && (
                    <div key={field}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-muted-foreground capitalize">
                          {field.replace(/_/g, " ")}
                        </span>
                        <span className="font-medium">
                          {Math.round((score as number) * 100)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary/70 transition-all"
                          style={{ width: `${(score as number) * 100}%` }}
                        />
                      </div>
                    </div>
                  )
                ))}
              </div>
            </CardContent>
          </Card>
          
          {/* Validation Status */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Validation</CardTitle>
            </CardHeader>
            <CardContent>
              {product.validation_passed ? (
                <p className="text-sm text-green-600">✓ All validation rules passed</p>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-red-600 font-medium">Validation issues:</p>
                  <ul className="text-sm space-y-1">
                    {product.validation_errors?.map((error, idx) => (
                      <li key={idx} className="text-red-600">
                        • {error.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              
              {product.uncertainty_flags && product.uncertainty_flags.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm text-yellow-600 font-medium mb-2">Uncertainty flags:</p>
                  <div className="flex flex-wrap gap-1">
                    {product.uncertainty_flags.map((flag, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs bg-yellow-50">
                        {flag.replace(/_/g, " ")}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Review History */}
          <ProductHistory productId={productId} reviews={reviews} />
          
          {/* Metadata */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="text-sm space-y-2">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Review Priority</dt>
                  <dd className="font-medium">{product.review_priority}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Is Corrected</dt>
                  <dd className="font-medium">{product.is_corrected ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Split Product</dt>
                  <dd className="font-medium">{product.is_split_product ? "Yes" : "No"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Created</dt>
                  <dd className="font-medium">
                    {new Date(product.created_at).toLocaleDateString()}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function ProductDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-12 bg-muted rounded animate-pulse" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="h-64 bg-muted rounded animate-pulse" />
          <div className="h-48 bg-muted rounded animate-pulse" />
        </div>
        <div className="space-y-6">
          <div className="h-48 bg-muted rounded animate-pulse" />
          <div className="h-64 bg-muted rounded animate-pulse" />
        </div>
      </div>
    </div>
  );
}