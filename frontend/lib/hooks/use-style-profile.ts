'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, setAccessToken } from '@/lib/api';
import { StyleProfileData, StyleProfileUpdate, StyleDraft, StyleDraftRequest, Guidance } from '@/lib/types';

// Helper to set token if available (for NextAuth mode)
function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

export function useStyleProfile() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['style-profile'],
    queryFn: () => api.get<StyleProfileData>('/style-profile'),
    enabled: status !== 'loading',
  });
}

export function useUpdateStyleProfile() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: (data: StyleProfileUpdate) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.put<StyleProfileData>('/style-profile', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['style-profile'] });
    },
  });
}

export function useStyleDraft() {
  const { data: session } = useSession();

  return useMutation({
    mutationFn: (data: StyleDraftRequest) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.post<StyleDraft>('/style-profile/draft', data);
    },
  });
}

export function useGuidance() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['style-profile', 'guidance'],
    queryFn: () => api.get<Guidance>('/style-profile/guidance'),
    enabled: status !== 'loading',
  });
}
