import { describe, it, expect } from 'vitest';
import { weekRange, monthRange } from '@/lib/hooks/use-calendar';

describe('calendar ranges', () => {
  it('weekRange returns 7 consecutive days covering the anchor', () => {
    const { start, end, days } = weekRange(new Date('2026-07-08T12:00:00'));
    expect(days).toHaveLength(7);
    expect(days[0]).toBe(start);
    expect(days[6]).toBe(end);
    expect(days).toContain('2026-07-08');
  });
  it('monthRange spans the whole month', () => {
    const { start, end } = monthRange(new Date('2026-07-15T12:00:00'));
    expect(start).toBe('2026-07-01');
    expect(end).toBe('2026-07-31');
  });
});
