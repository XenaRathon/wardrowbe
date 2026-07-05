import { describe, it, expect } from 'vitest';
import { categoryOfType, subtypesOfType } from '@/lib/hooks/use-taxonomy';

const tax = { categories: [
  { category: 'Intimates', types: [{ type: 'bra', subtypes: ['push-up','balconette'] }] },
  { category: 'Tops', types: [{ type: 't-shirt', subtypes: ['crop'] }, { type: 'top', subtypes: [] }] },
]};

describe('taxonomy helpers', () => {
  it('categoryOfType finds the parent category', () => {
    expect(categoryOfType(tax, 'bra')).toBe('Intimates');
    expect(categoryOfType(tax, 't-shirt')).toBe('Tops');
    expect(categoryOfType(tax, 'nope')).toBeUndefined();
  });
  it('subtypesOfType returns the type\'s subtypes', () => {
    expect(subtypesOfType(tax, 'bra')).toEqual(['push-up','balconette']);
    expect(subtypesOfType(tax, 'top')).toEqual([]);
    expect(subtypesOfType(tax, 'nope')).toEqual([]);
  });
});
