export default function EditProductLoading() {
  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <div className="flex-1 bg-gray-900 animate-pulse" />
      <div className="w-[420px] border-l p-4 space-y-4">
        <div className="h-8 bg-muted rounded animate-pulse" />
        <div className="h-10 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
        <div className="h-32 bg-muted rounded animate-pulse" />
      </div>
    </div>
  );
}
