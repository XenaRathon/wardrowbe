'use client';

import { useEffect, useState } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import {
  useTaxonomy,
  categoryOfType,
  subtypesOfType,
  resolveCategoryState,
} from '@/lib/hooks/use-taxonomy';

// Radix Select doesn't allow an empty-string item value, so unset selections
// are represented with this sentinel and translated back to undefined.
const NONE_VALUE = '__none__';

export interface TypeSelectorValue {
  type?: string;
  subtype?: string;
}

interface TypeSelectorProps {
  value: TypeSelectorValue;
  onChange: (value: TypeSelectorValue) => void;
}

export function TypeSelector({ value, onChange }: TypeSelectorProps) {
  const { data: taxonomy, isLoading } = useTaxonomy();

  // The category isn't part of the controlled value (only type/subtype are),
  // so once a type is picked the category is derived from it. But a category
  // can be picked on its own (to filter the Type dropdown) before any type is
  // chosen, so we need somewhere to hold that pending pick — hence this local
  // state, which is only consulted when value.type is unset.
  const [pendingCategory, setPendingCategory] = useState<string | undefined>(undefined);

  // Keep pendingCategory in sync with the type's derived category whenever a
  // type is set. This is what lets clearing the type back to "Let AI
  // detect..." retain the category context (instead of snapping to "Any
  // category", which would also disable the Type select below and lock the
  // user out of re-narrowing type without re-picking category), and what
  // prevents a stale category from leaking in if this component instance is
  // reused for a different item with a different type.
  useEffect(() => {
    if (taxonomy && value.type) {
      setPendingCategory(categoryOfType(taxonomy, value.type));
    }
  }, [taxonomy, value.type]);

  const { currentCategory } = resolveCategoryState(taxonomy, value.type, pendingCategory);
  const typesForCategory = taxonomy?.categories.find((c) => c.category === currentCategory)?.types ?? [];
  const subtypes = taxonomy && value.type ? subtypesOfType(taxonomy, value.type) : [];

  const handleCategoryChange = (category: string) => {
    setPendingCategory(category === NONE_VALUE ? undefined : category);
    // Changing category invalidates the current type/subtype selection.
    onChange({ type: undefined, subtype: undefined });
  };

  const handleTypeChange = (type: string) => {
    if (type === NONE_VALUE) {
      onChange({ type: undefined, subtype: undefined });
      return;
    }
    // Picking a new type clears any subtype from the previous type.
    onChange({ type, subtype: undefined });
  };

  const handleSubtypeChange = (subtype: string) => {
    onChange({ ...value, subtype: subtype === NONE_VALUE ? undefined : subtype });
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor="type-selector-category">Category</Label>
        <Select
          value={currentCategory ?? NONE_VALUE}
          onValueChange={handleCategoryChange}
          disabled={isLoading || !taxonomy}
        >
          <SelectTrigger id="type-selector-category">
            <SelectValue placeholder="Select category..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_VALUE}>Any category</SelectItem>
            {taxonomy?.categories.map((c) => (
              <SelectItem key={c.category} value={c.category}>
                {c.category}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="type-selector-type">
          Type <span className="text-muted-foreground font-normal">(AI will detect if empty)</span>
        </Label>
        <Select
          value={value.type ?? NONE_VALUE}
          onValueChange={handleTypeChange}
          disabled={isLoading || !taxonomy || !currentCategory}
        >
          <SelectTrigger id="type-selector-type">
            <SelectValue placeholder="Let AI detect..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE_VALUE}>Let AI detect...</SelectItem>
            {typesForCategory.map((t) => (
              <SelectItem key={t.type} value={t.type}>
                {t.type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {value.type && subtypes.length > 0 && (
        <div className="space-y-2">
          <Label htmlFor="type-selector-subtype">Subtype</Label>
          <Select value={value.subtype ?? NONE_VALUE} onValueChange={handleSubtypeChange}>
            <SelectTrigger id="type-selector-subtype">
              <SelectValue placeholder="Select subtype..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>None</SelectItem>
              {subtypes.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}
