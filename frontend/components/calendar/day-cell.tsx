'use client';

import { Shirt } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { DayRecord } from '@/lib/types';

interface DayCellProps {
  date: string;
  record?: DayRecord;
  isToday?: boolean;
  onSelect?: (date: string) => void;
}

function dayNumber(date: string): number {
  return Number(date.slice(8, 10));
}

export function DayCell({ date, record, isToday = false, onSelect }: DayCellProps) {
  const primary = record?.primary ?? null;
  const extrasCount = record?.extras?.length ?? 0;
  const hasWarning = !!record?.repeat_warnings?.length;

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect?.(date)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect?.(date);
        }
      }}
      className={cn(
        'flex aspect-square cursor-pointer flex-col overflow-hidden transition-all hover:shadow-md',
        isToday && 'ring-2 ring-primary'
      )}
    >
      <CardContent className="flex h-full flex-col gap-1 p-1.5">
        <div className="flex items-center justify-between">
          <span className={cn('text-xs font-semibold', isToday && 'text-primary')}>
            {dayNumber(date)}
          </span>
          {hasWarning && (
            <span
              className="h-2 w-2 rounded-full bg-amber-500"
              role="img"
              aria-label="Repeat warning"
              title="Repeat warning"
            />
          )}
        </div>

        {primary ? (
          <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded bg-muted">
            <Shirt className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center text-[10px] text-muted-foreground">
            —
          </div>
        )}

        <div className="flex min-h-[16px] items-center justify-between gap-1">
          {primary && (
            <Badge variant="outline" className="truncate px-1.5 py-0 text-[10px] capitalize leading-4">
              {primary.occasion}
            </Badge>
          )}
          {extrasCount > 0 && (
            <Badge variant="secondary" className="px-1.5 py-0 text-[10px] leading-4">
              +{extrasCount}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
