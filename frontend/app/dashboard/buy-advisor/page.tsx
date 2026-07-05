'use client';

import { useState } from 'react';
import { ShoppingBag, ExternalLink, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useBuyAdvisor, useSizeForUrl } from '@/lib/hooks/use-buy-advisor';
import { getErrorMessage } from '@/lib/api';
import { CLOTHING_TYPES } from '@/lib/types';

function formatLabel(value: string): string {
  return value
    .split(/[-_]/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function confidenceBadgeVariant(confidence: string): 'default' | 'secondary' | 'outline' {
  switch (confidence.toLowerCase()) {
    case 'high':
      return 'default';
    case 'medium':
      return 'secondary';
    default:
      return 'outline';
  }
}

function RecCard({
  rec,
}: {
  rec: {
    role: string;
    type: string;
    silhouette: string | null;
    color: string | null;
    rationale: string;
    search_links: { retailer: string; url: string }[];
  };
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">{formatLabel(rec.type)}</CardTitle>
        <CardDescription>Gap: {formatLabel(rec.role)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {rec.silhouette && <Badge variant="secondary">{formatLabel(rec.silhouette)} silhouette</Badge>}
          {rec.color && <Badge variant="outline">{formatLabel(rec.color)}</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">{rec.rationale}</p>
        <div className="flex flex-wrap gap-2">
          {rec.search_links.map((link) => (
            <Button key={link.retailer} asChild variant="outline" size="sm">
              <a href={link.url} target="_blank" rel="noopener noreferrer">
                {link.retailer}
                <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
              </a>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RecsLoadingSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-24" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-8 w-40" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function SizeFinderPanel() {
  const [productUrl, setProductUrl] = useState('');
  const [productType, setProductType] = useState<string>('');
  const sizeMutation = useSizeForUrl();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!productUrl.trim()) return;
    sizeMutation.mutate({
      product_url: productUrl.trim(),
      product_type: productType || undefined,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Find My Size</CardTitle>
        <CardDescription>
          Paste a product page URL and we&apos;ll estimate your size from its chart (or your
          measurements if no chart is found).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="product-url">Product URL</Label>
            <Input
              id="product-url"
              type="url"
              placeholder="https://example.com/product/..."
              value={productUrl}
              onChange={(e) => setProductUrl(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="product-type">Item type (optional)</Label>
            <Select value={productType || 'unspecified'} onValueChange={(value) => setProductType(value === 'unspecified' ? '' : value)}>
              <SelectTrigger id="product-type" className="w-full sm:w-[240px]">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="unspecified">Not specified</SelectItem>
                {CLOTHING_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={!productUrl.trim() || sizeMutation.isPending}>
            {sizeMutation.isPending ? 'Checking…' : 'Find my size'}
          </Button>
        </form>

        {sizeMutation.isError && (
          <p className="text-sm text-destructive">
            {getErrorMessage(sizeMutation.error, 'Could not determine a size for that URL.')}
          </p>
        )}

        {sizeMutation.isSuccess && sizeMutation.data && (
          <div className="rounded-lg border bg-muted/30 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm text-muted-foreground">Estimated size</div>
                <div className="text-2xl font-semibold">{sizeMutation.data.size}</div>
              </div>
              <Badge variant={confidenceBadgeVariant(sizeMutation.data.confidence)}>
                {formatLabel(sizeMutation.data.confidence)} confidence
              </Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Source: {formatLabel(sizeMutation.data.source)}. This is a starting point, not a
              guarantee — always check the retailer&apos;s own size chart, especially for bras and
              other fitted intimates.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function BuyAdvisorPage() {
  const { data, isLoading, isError } = useBuyAdvisor();
  const recommendations = data?.recommendations ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <ShoppingBag className="h-6 w-6" />
          Buy Advisor
        </h1>
        <p className="text-muted-foreground">
          Closet-gap recommendations with prefilled search links, plus a paste-a-URL size finder.
        </p>
      </div>

      {isLoading && <RecsLoadingSkeleton />}

      {!isLoading && isError && (
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load recommendations</CardTitle>
            <CardDescription>Please refresh the page or try again shortly.</CardDescription>
          </CardHeader>
        </Card>
      )}

      {!isLoading && !isError && recommendations.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              No gaps found
            </CardTitle>
            <CardDescription>
              Your wardrobe looks well-covered right now — check back after your closet changes.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {!isLoading && !isError && recommendations.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {recommendations.map((rec, i) => (
            <RecCard key={`${rec.role}-${rec.type}-${i}`} rec={rec} />
          ))}
        </div>
      )}

      <SizeFinderPanel />
    </div>
  );
}
