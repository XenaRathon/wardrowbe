import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, setAccessToken } from '@/lib/api';
import { DayRecord } from '@/lib/types';

// Helper to set token if available (for NextAuth mode)
function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

// Format a Date as YYYY-MM-DD using LOCAL time components.
// Do NOT use toISOString() here — it converts to UTC and can shift the day.
function fmt(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export interface DateRange {
  start: string;
  end: string;
  days: string[];
}

// Returns the 7 consecutive days (Sunday-Saturday) covering the anchor date.
export function weekRange(anchor: Date): DateRange {
  const dayOfWeek = anchor.getDay(); // 0 = Sunday
  const weekStart = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() - dayOfWeek);

  const days: string[] = [];
  for (let i = 0; i < 7; i++) {
    days.push(fmt(new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + i)));
  }

  return { start: days[0], end: days[6], days };
}

// Returns every day in the calendar month containing the anchor date.
export function monthRange(anchor: Date): DateRange {
  const firstDay = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const lastDay = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);

  const days: string[] = [];
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push(fmt(new Date(anchor.getFullYear(), anchor.getMonth(), d)));
  }

  return { start: fmt(firstDay), end: fmt(lastDay), days };
}

export function useCalendar(start: string, end: string) {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['calendar', start, end],
    queryFn: () => api.get<DayRecord[]>('/calendar', { params: { start, end } }),
    enabled: !!start && !!end && status !== 'loading',
  });
}

// Shared invalidation for mutations that change a day's plan/wear state:
// the calendar grid, item wear counters (needs_wash etc.), and analytics
// all derive from wear events.
function invalidateCalendarAndWearDerived(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['calendar'] });
  queryClient.invalidateQueries({ queryKey: ['items'] });
  queryClient.invalidateQueries({ queryKey: ['analytics'] });
}

export function usePlanDay() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: async ({ date, outfitId }: { date: string; outfitId: string }) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.post<DayRecord>(`/calendar/${date}/plan`, { outfit_id: outfitId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
    },
  });
}

export function useConfirmDay() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: async (date: string) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.post<DayRecord>(`/calendar/${date}/confirm`);
    },
    onSuccess: () => {
      invalidateCalendarAndWearDerived(queryClient);
    },
  });
}

export function useLogWear() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: async ({
      date,
      outfitId,
      wornByUserId,
      occasion,
    }: {
      date: string;
      outfitId: string;
      wornByUserId?: string;
      occasion?: string;
    }) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.post<DayRecord>(`/calendar/${date}/wear`, {
        outfit_id: outfitId,
        worn_by_user_id: wornByUserId,
        occasion,
      });
    },
    onSuccess: () => {
      invalidateCalendarAndWearDerived(queryClient);
    },
  });
}

export function useRemoveWear() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  return useMutation({
    mutationFn: async ({ date, outfitId }: { date: string; outfitId: string }) => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string);
      }
      return api.delete<DayRecord>(`/calendar/${date}/wear/${outfitId}`);
    },
    onSuccess: () => {
      invalidateCalendarAndWearDerived(queryClient);
    },
  });
}
