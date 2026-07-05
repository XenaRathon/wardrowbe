import { describe, it, expect } from 'vitest';
import { categoryOfType, subtypesOfType, resolveCategoryState } from '@/lib/hooks/use-taxonomy';

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

describe('resolveCategoryState (TypeSelector category-sync regression)', () => {
  it('(a) clearing type after it was set retains the derived category', () => {
    // Item loads with type=bra -> category derives + syncs into pendingCategory.
    const step1 = resolveCategoryState(tax, 'bra', undefined);
    expect(step1.currentCategory).toBe('Intimates');
    expect(step1.pendingCategory).toBe('Intimates');

    // User clears type back to "Let AI detect...".
    const step2 = resolveCategoryState(tax, undefined, step1.pendingCategory);
    expect(step2.currentCategory).toBe('Intimates'); // NOT "Any category"
    expect(step2.pendingCategory).toBe('Intimates'); // still defined -> Type select stays enabled
  });

  it('(b) an explicit category pick (no type yet) is preserved untouched', () => {
    // handleCategoryChange sets pendingCategory directly and clears type/subtype;
    // resolveCategoryState must not disturb that pick while type stays unset.
    const afterPick = resolveCategoryState(tax, undefined, 'Tops');
    expect(afterPick.currentCategory).toBe('Tops');
    expect(afterPick.pendingCategory).toBe('Tops');
  });

  it('(c) a different bound type (component reused for another item) overwrites stale pendingCategory', () => {
    // Previous item left a stale pendingCategory of Intimates; the bound
    // value.type now belongs to a different item, in a different category.
    const stalePending = 'Intimates';
    const reused = resolveCategoryState(tax, 't-shirt', stalePending);
    expect(reused.currentCategory).toBe('Tops');
    expect(reused.pendingCategory).toBe('Tops'); // no leak from the previous item
  });
});
