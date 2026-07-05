'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, setAccessToken } from '@/lib/api';
import { BuyAdvisorResponse, SizeForUrlRequest, SizeResult } from '@/lib/types';

// Helper to set token if available (for NextAuth mode)
function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

export function useBuyAdvisor() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['buy-advisor'],
    queryFn: () => api.get<BuyAdvisorResponse>('/buy-advisor'),
    enabled: status !== 'loading',
  });
}

export function useSizeForUrl() {
  const { data: session } = useSession();

  return useMutation({
    mutationFn: (data: SizeForUrlRequest) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.post<SizeResult>('/buy-advisor/size', data);
    },
  });
}
