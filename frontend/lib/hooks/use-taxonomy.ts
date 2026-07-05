'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, setAccessToken } from '@/lib/api';
import { Taxonomy } from '@/lib/types';

// Helper to set token if available (for NextAuth mode)
function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

// Taxonomy is static reference data (category > type > subtype), so it's
// fetched once and cached indefinitely.
export function useTaxonomy() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['taxonomy'],
    queryFn: () => api.get<Taxonomy>('/taxonomy'),
    enabled: status !== 'loading',
    staleTime: Infinity,
  });
}

// Pure lookup: which category does this type belong to?
export function categoryOfType(taxonomy: Taxonomy, type: string): string | undefined {
  return taxonomy.categories.find((c) => c.types.some((t) => t.type === type))?.category;
}

// Pure lookup: what subtypes does this type have?
export function subtypesOfType(taxonomy: Taxonomy, type: string): string[] {
  for (const category of taxonomy.categories) {
    const found = category.types.find((t) => t.type === type);
    if (found) return found.subtypes;
  }
  return [];
}
