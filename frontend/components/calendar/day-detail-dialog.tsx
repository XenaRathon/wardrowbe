'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { CalendarCheck, Loader2, Shirt, Trash2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { getErrorMessage } from '@/lib/api';
import {
  useCalendar,
  useConfirmDay,
  useLogWear,
  usePlanDay,
  useRemoveWear,
} from '@/lib/hooks/use-calendar';
import { useOutfits } from '@/lib/hooks/use-outfits';
import { useItems } from '@/lib/hooks/use-items';
import { useFamily } from '@/lib/hooks/use-family';
import { OCCASIONS, type OutfitBrief } from '@/lib/types';

interface DayDetailDialogProps {
  date: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const ME_VALUE = '__me__';
const NO_OCCASION_VALUE = '__none__';

function formatHeading(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });
}

function OutfitLabel({ occasion, name }: { occasion: string; name: string | null }) {
  return (
    <span className="capitalize">
      {name || occasion}
      {name ? <span className="text-muted-foreground"> · {occasion}</span> : null}
    </span>
  );
}

function RepeatWarningBadges({ ids }: { ids: string[] }) {
  const { data: warnedItems } = useItems({ ids: ids.join(',') }, 1, ids.length || 1);
  const warnedItemNames = useMemo(() => {
    const byId = new Map((warnedItems?.items ?? []).map((item) => [item.id, item.name || item.type]));
    return ids.map((id) => byId.get(id) || 'an item');
  }, [warnedItems, ids]);

  return (
    <div className="flex flex-wrap gap-1.5">
      {warnedItemNames.map((name, i) => (
        <Badge
          key={ids[i]}
          variant="outline"
          className="border-amber-500 bg-amber-50 text-amber-700 text-xs"
        >
          Recently worn: {name}
        </Badge>
      ))}
    </div>
  );
}

export function DayDetailDialog({ date, open, onOpenChange }: DayDetailDialogProps) {
  const [planOutfitId, setPlanOutfitId] = useState('');
  const [logOutfitId, setLogOutfitId] = useState('');
  const [logWornBy, setLogWornBy] = useState(ME_VALUE);
  const [logOccasion, setLogOccasion] = useState(NO_OCCASION_VALUE);

  useEffect(() => {
    if (open) {
      setPlanOutfitId('');
      setLogOutfitId('');
      setLogWornBy(ME_VALUE);
      setLogOccasion(NO_OCCASION_VALUE);
    }
  }, [open, date]);

  const { data: days, isLoading } = useCalendar(date ?? '', date ?? '');
  const record = days?.[0];
  const primary = record?.primary ?? null;
  const extras = record?.extras ?? [];
  const repeatWarnings = record?.repeat_warnings ?? [];

  const { data: outfitsData } = useOutfits({}, 1, 50);
  const outfits = useMemo(() => outfitsData?.outfits ?? [], [outfitsData]);

  const { data: family } = useFamily();
  const members = family?.members ?? [];

  const planDay = usePlanDay();
  const confirmDay = useConfirmDay();
  const logWear = useLogWear();
  const removeWear = useRemoveWear();

  if (!date) return null;

  const confirmedToday = !!primary?.worn_at && primary.worn_at === date;
  const hasUnconfirmedPlan = !!primary && !confirmedToday;
  const canPlan = !primary || !confirmedToday;

  const handlePlan = async () => {
    if (!planOutfitId) return;
    try {
      await planDay.mutateAsync({ date, outfitId: planOutfitId });
      toast.success('Outfit planned');
      setPlanOutfitId('');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to plan outfit'));
    }
  };

  const handleConfirm = async () => {
    try {
      await confirmDay.mutateAsync(date);
      toast.success('Marked as worn');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to confirm'));
    }
  };

  const handleLogWear = async () => {
    if (!logOutfitId) return;
    try {
      await logWear.mutateAsync({
        date,
        outfitId: logOutfitId,
        wornByUserId: logWornBy === ME_VALUE ? undefined : logWornBy,
        occasion: logOccasion === NO_OCCASION_VALUE ? undefined : logOccasion,
      });
      toast.success('Wear logged');
      setLogOutfitId('');
      setLogWornBy(ME_VALUE);
      setLogOccasion(NO_OCCASION_VALUE);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to log wear'));
    }
  };

  const handleRemove = async (outfitId: string) => {
    try {
      await removeWear.mutateAsync({ date, outfitId });
      toast.success('Wear removed');
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to remove wear'));
    }
  };

  const renderOutfitOptions = () =>
    outfits.map((outfit) => (
      <SelectItem key={outfit.id} value={outfit.id}>
        <OutfitLabel occasion={outfit.occasion} name={outfit.name} />
      </SelectItem>
    ));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{formatHeading(date)}</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-5 pr-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {repeatWarnings.length > 0 && <RepeatWarningBadges ids={repeatWarnings} />}

              {/* Current plan / wear status */}
              <div className="space-y-2">
                <p className="text-sm font-medium">Today&apos;s outfit</p>
                {primary ? (
                  <div className="flex items-center justify-between gap-2 rounded-md border p-3">
                    <div className="flex items-center gap-2 text-sm">
                      <Shirt className="h-4 w-4 text-muted-foreground" />
                      <OutfitLabel occasion={primary.occasion} name={primary.name} />
                    </div>
                    <Badge variant={confirmedToday ? 'default' : 'secondary'}>
                      {confirmedToday ? 'Worn' : 'Planned'}
                    </Badge>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Nothing planned yet.</p>
                )}

                {hasUnconfirmedPlan && (
                  <Button
                    size="sm"
                    onClick={handleConfirm}
                    disabled={confirmDay.isPending}
                    className="w-full"
                  >
                    {confirmDay.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <CalendarCheck className="h-4 w-4 mr-2" />
                    )}
                    Confirm worn
                  </Button>
                )}
              </div>

              {/* Plan / replan */}
              {canPlan && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-sm font-medium">
                    {primary ? 'Change plan' : 'Plan an outfit'}
                  </p>
                  <div className="flex gap-2">
                    <Select value={planOutfitId} onValueChange={setPlanOutfitId}>
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder="Choose an outfit" />
                      </SelectTrigger>
                      <SelectContent>{renderOutfitOptions()}</SelectContent>
                    </Select>
                    <Button
                      size="sm"
                      onClick={handlePlan}
                      disabled={!planOutfitId || planDay.isPending}
                    >
                      {planDay.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        'Plan'
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* Log actual / extra wear */}
              <div className="space-y-2 pt-2 border-t">
                <p className="text-sm font-medium">Log what I actually wore</p>
                <Select value={logOutfitId} onValueChange={setLogOutfitId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose an outfit" />
                  </SelectTrigger>
                  <SelectContent>{renderOutfitOptions()}</SelectContent>
                </Select>
                {members.length > 0 && (
                  <Select value={logWornBy} onValueChange={setLogWornBy}>
                    <SelectTrigger>
                      <SelectValue placeholder="Who wore it?" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={ME_VALUE}>Me</SelectItem>
                      {members.map((member) => (
                        <SelectItem key={member.id} value={member.id}>
                          {member.display_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <Select value={logOccasion} onValueChange={setLogOccasion}>
                  <SelectTrigger>
                    <SelectValue placeholder="Occasion (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_OCCASION_VALUE}>No occasion</SelectItem>
                    {OCCASIONS.map((occasion) => (
                      <SelectItem key={occasion.value} value={occasion.value}>
                        {occasion.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full"
                  onClick={handleLogWear}
                  disabled={!logOutfitId || logWear.isPending}
                >
                  {logWear.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : null}
                  Log wear
                </Button>
              </div>

              {/* Extras */}
              {extras.length > 0 && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-sm font-medium">Also worn</p>
                  {extras.map((extra: OutfitBrief) => (
                    <div
                      key={extra.id}
                      className="flex items-center justify-between gap-2 rounded-md border p-2.5"
                    >
                      <div className="flex items-center gap-2 text-sm">
                        <Shirt className="h-4 w-4 text-muted-foreground" />
                        <OutfitLabel occasion={extra.occasion} name={extra.name} />
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => handleRemove(extra.id)}
                        disabled={removeWear.isPending}
                        title="Remove"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
