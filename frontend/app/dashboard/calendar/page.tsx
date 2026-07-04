'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { DayCell } from '@/components/calendar/day-cell';
import { useCalendar, weekRange, monthRange } from '@/lib/hooks/use-calendar';
import { cn } from '@/lib/utils';
import type { DayRecord } from '@/lib/types';

type ViewMode = 'week' | 'month';

const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function parseYmd(dateKey: string): Date {
  const [y, m, d] = dateKey.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function todayKey(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function formatHeading(anchor: Date, view: ViewMode): string {
  if (view === 'month') {
    return anchor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }
  return `Week of ${anchor.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })}`;
}

export default function CalendarPage() {
  const [view, setView] = useState<ViewMode>('week');
  const [anchor, setAnchor] = useState<Date>(() => new Date());

  const range = useMemo(
    () => (view === 'week' ? weekRange(anchor) : monthRange(anchor)),
    [anchor, view]
  );

  const { data, isLoading, isError } = useCalendar(range.start, range.end);

  const recordsByDate = useMemo(() => {
    const map = new Map<string, DayRecord>();
    (data ?? []).forEach((record) => map.set(record.date, record));
    return map;
  }, [data]);

  // Leading blanks so the month grid aligns to weekday columns (weeks always
  // start Sunday; the month itself may not start on one).
  const leadingBlanks = view === 'month' ? parseYmd(range.start).getDay() : 0;
  const today = todayKey();

  const shiftAnchor = (delta: number) => {
    setAnchor((prev) =>
      view === 'week'
        ? new Date(prev.getFullYear(), prev.getMonth(), prev.getDate() + delta * 7)
        : new Date(prev.getFullYear(), prev.getMonth() + delta, 1)
    );
  };

  const handleSelect = (date: string) => {
    // Task 3 wires up the day-detail dialog here.
    void date;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Calendar</h1>
          <p className="text-muted-foreground">Your scheduled and worn looks</p>
        </div>
        <div
          className="inline-flex overflow-hidden rounded-full border-2 border-muted"
          role="group"
          aria-label="View toggle"
        >
          <button
            type="button"
            onClick={() => setView('week')}
            aria-pressed={view === 'week'}
            className={cn(
              'px-4 py-1.5 text-sm font-medium transition-colors',
              view === 'week'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-muted-foreground hover:text-foreground'
            )}
          >
            Week
          </button>
          <button
            type="button"
            onClick={() => setView('month')}
            aria-pressed={view === 'month'}
            className={cn(
              'border-l-2 border-muted px-4 py-1.5 text-sm font-medium transition-colors',
              view === 'month'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background text-muted-foreground hover:text-foreground'
            )}
          >
            Month
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => shiftAnchor(-1)} aria-label="Previous">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={() => setAnchor(new Date())}>
            Today
          </Button>
          <Button variant="outline" size="icon" onClick={() => shiftAnchor(1)} aria-label="Next">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <h2 className="text-lg font-semibold">{formatHeading(anchor, view)}</h2>
        <div className="w-[132px]" />
      </div>

      {isError ? (
        <div className="py-8 text-center text-destructive">Failed to load calendar</div>
      ) : isLoading ? (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: view === 'week' ? 7 : 35 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {WEEKDAY_LABELS.map((label) => (
            <div key={label} className="pb-1 text-center text-xs font-medium text-muted-foreground">
              {label}
            </div>
          ))}
          {Array.from({ length: leadingBlanks }).map((_, i) => (
            <div key={`blank-${i}`} />
          ))}
          {range.days.map((date) => (
            <DayCell
              key={date}
              date={date}
              record={recordsByDate.get(date)}
              isToday={date === today}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
