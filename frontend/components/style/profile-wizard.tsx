'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Loader2, Sparkles, Upload, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUserProfile } from '@/lib/hooks/use-user';
import { useStyleDraft, useStyleProfile, useUpdateStyleProfile } from '@/lib/hooks/use-style-profile';

const UNDERTONE_OPTIONS = [
  { value: 'cool', label: 'Cool' },
  { value: 'warm', label: 'Warm' },
  { value: 'neutral', label: 'Neutral' },
];

const CONTRAST_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];

// Mirrors backend `SEASON_PALETTE` keys (app/style_rules.py) — the draft endpoint only ever
// returns one of these, and the PUT endpoint doesn't validate, so keep this list in sync.
const COLOR_SEASON_OPTIONS = [
  'cool-winter',
  'warm-winter',
  'warm-spring',
  'cool-spring',
  'soft-autumn',
  'warm-autumn',
  'cool-summer',
  'soft-summer',
];

// Mirrors backend `KNOWN_KIBBE_LEANS` (app/services/style_service.py).
const KIBBE_LEAN_OPTIONS = ['dramatic', 'natural', 'romantic', 'classic', 'gamine'];

const KIBBE_HINT_TOGGLES = [
  { key: 'sharp-angular-features', label: 'Sharp / angular features' },
  { key: 'soft-rounded-features', label: 'Soft / rounded features' },
  { key: 'petite-frame', label: 'Petite frame' },
] as const;

function formatLabel(value: string | null | undefined, fallback = 'Not set'): string {
  if (!value) return fallback;
  return value
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function isPositive(value: unknown): boolean {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? parseFloat(value) : NaN;
  return Number.isFinite(n) && n > 0;
}

// Shape-relevant measurement keys the backend's `analyze_measurements` needs to compute
// `body_shape` (bust OR chest, plus waist and hips — see backend/app/services/body_analysis.py).
export function hasShapeMeasurements(
  measurements: Record<string, number | string> | null | undefined
): boolean {
  if (!measurements) return false;
  const hasBustOrChest = isPositive(measurements.bust) || isPositive(measurements.chest);
  return hasBustOrChest && isPositive(measurements.waist) && isPositive(measurements.hips);
}

export const STEP_MEASUREMENTS = 0;
export const STEP_HINTS = 1;
export const STEP_PHOTO = 2;
export const STEP_CONFIRM = 3;
export const LAST_STEP = STEP_CONFIRM;

export interface WizardState {
  hasMeasurements: boolean;
  undertone: string;
  contrast: string;
  colorSeason: string;
  kibbeLean: string;
}

/** Pure step-gating logic, kept separate from component state so it's unit-testable. */
export function canAdvance(step: number, state: WizardState): boolean {
  switch (step) {
    case STEP_MEASUREMENTS:
      return state.hasMeasurements;
    case STEP_HINTS:
      return state.undertone !== '' && state.contrast !== '';
    case STEP_PHOTO:
      return true;
    case STEP_CONFIRM:
      return state.colorSeason !== '' && state.kibbeLean !== '';
    default:
      return false;
  }
}

interface ProfileWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProfileWizard({ open, onOpenChange }: ProfileWizardProps) {
  const { data: userProfile } = useUserProfile();
  const { data: styleProfile } = useStyleProfile();
  const styleDraft = useStyleDraft();
  const updateStyleProfile = useUpdateStyleProfile();

  const [step, setStep] = useState<number>(STEP_MEASUREMENTS);
  const [undertone, setUndertone] = useState('');
  const [contrast, setContrast] = useState('');
  const [kibbeHints, setKibbeHints] = useState<Record<string, boolean>>({});
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [colorSeason, setColorSeason] = useState('');
  const [kibbeLean, setKibbeLean] = useState('');
  const [draftFetched, setDraftFetched] = useState(false);

  const hasMeasurements = hasShapeMeasurements(userProfile?.body_measurements);

  // Reset the whole flow every time the dialog is (re)opened.
  useEffect(() => {
    if (!open) return;
    setStep(hasMeasurements ? STEP_HINTS : STEP_MEASUREMENTS);
    setUndertone('');
    setContrast('');
    setKibbeHints({});
    setImageB64(null);
    setImagePreview(null);
    setColorSeason('');
    setKibbeLean('');
    setDraftFetched(false);
    // Only re-run when the dialog opens/closes — intentionally not reacting to
    // `hasMeasurements` changing while already open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const state: WizardState = { hasMeasurements, undertone, contrast, colorSeason, kibbeLean };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      setImagePreview(result);
      // Backend expects raw base64 (it re-adds the `data:image/...;base64,` prefix itself).
      setImageB64(result.split(',')[1] ?? '');
    };
    reader.readAsDataURL(file);
  };

  const clearImage = () => {
    setImageB64(null);
    setImagePreview(null);
  };

  const toggleKibbeHint = (key: string) => {
    setKibbeHints((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleGetSuggestion = async () => {
    const hints = {
      undertone,
      contrast,
      self_perception: Object.entries(kibbeHints)
        .filter(([, checked]) => checked)
        .map(([key]) => key),
    };
    try {
      const draft = await styleDraft.mutateAsync({ hints, image_b64: imageB64 ?? undefined });
      setColorSeason(draft.color_season ?? '');
      setKibbeLean(draft.kibbe_lean ?? '');
      if (!draft.color_season && !draft.kibbe_lean) {
        toast.warning('AI could not confirm a suggestion — please choose manually below.');
      }
    } catch {
      toast.error('Could not get an AI suggestion. Please choose manually below.');
    } finally {
      setDraftFetched(true);
    }
  };

  const handleSave = async () => {
    try {
      await updateStyleProfile.mutateAsync({
        color_season: colorSeason,
        kibbe_lean: kibbeLean,
        season_confirmed: true,
        kibbe_confirmed: true,
      });
      toast.success('Style profile saved!');
      onOpenChange(false);
    } catch {
      toast.error('Failed to save style profile. Please try again.');
    }
  };

  const goNext = () => setStep((s) => Math.min(s + 1, LAST_STEP));
  const goBack = () => setStep((s) => Math.max(s - 1, STEP_MEASUREMENTS));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Set Up Style Profile</DialogTitle>
          <DialogDescription>
            {step === STEP_MEASUREMENTS && 'First, make sure your measurements are on file.'}
            {step === STEP_HINTS && 'Tell us a bit about your colouring and shape perception.'}
            {step === STEP_PHOTO && 'Optionally add a photo to sharpen the AI suggestion.'}
            {step === STEP_CONFIRM &&
              'Review your body analysis and confirm a colour season + Kibbe lean.'}
          </DialogDescription>
        </DialogHeader>

        {step === STEP_MEASUREMENTS && (
          <div className="space-y-4">
            {hasMeasurements ? (
              <p className="text-sm text-muted-foreground">
                Measurements found — you&apos;re ready to continue.
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  We need at least your bust/chest, waist, and hip measurements to compute your
                  body shape. Add them in Settings, then reopen this wizard to continue.
                </p>
                <Button asChild variant="outline">
                  <Link href="/dashboard/settings" onClick={() => onOpenChange(false)}>
                    Go to Settings
                  </Link>
                </Button>
              </>
            )}
          </div>
        )}

        {step === STEP_HINTS && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Skin undertone</Label>
              <Select value={undertone} onValueChange={setUndertone}>
                <SelectTrigger>
                  <SelectValue placeholder="Select undertone..." />
                </SelectTrigger>
                <SelectContent>
                  {UNDERTONE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Contrast (skin vs. hair/eyes)</Label>
              <Select value={contrast} onValueChange={setContrast}>
                <SelectTrigger>
                  <SelectValue placeholder="Select contrast..." />
                </SelectTrigger>
                <SelectContent>
                  {CONTRAST_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3">
              <Label>How would you describe yourself? (optional)</Label>
              {KIBBE_HINT_TOGGLES.map((t) => (
                <div key={t.key} className="flex items-center justify-between">
                  <span className="text-sm">{t.label}</span>
                  <Switch
                    checked={!!kibbeHints[t.key]}
                    onCheckedChange={() => toggleKibbeHint(t.key)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {step === STEP_PHOTO && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              A photo helps the AI give a more accurate colour season / Kibbe suggestion. This
              step is optional — you can skip it.
            </p>
            {imagePreview ? (
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="w-full h-48 object-cover rounded-lg"
                />
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  className="absolute top-2 right-2 h-8 w-8"
                  onClick={clearImage}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors">
                <Upload className="w-8 h-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">Click to upload a photo</p>
                <input type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              </label>
            )}
          </div>
        )}

        {step === STEP_CONFIRM && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-md border p-2">
                <div className="text-xs text-muted-foreground">Body Shape</div>
                <div className="text-sm font-medium">{formatLabel(styleProfile?.body_shape)}</div>
              </div>
              <div className="rounded-md border p-2">
                <div className="text-xs text-muted-foreground">Vertical Line</div>
                <div className="text-sm font-medium">
                  {formatLabel(styleProfile?.vertical_line)}
                </div>
              </div>
              <div className="rounded-md border p-2">
                <div className="text-xs text-muted-foreground">Frame</div>
                <div className="text-sm font-medium">{formatLabel(styleProfile?.frame)}</div>
              </div>
            </div>

            {!draftFetched && (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleGetSuggestion}
                disabled={styleDraft.isPending}
              >
                {styleDraft.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                Get AI Suggestion
              </Button>
            )}

            <div className="space-y-2">
              <Label>Colour Season {draftFetched && '(AI-suggested — edit if needed)'}</Label>
              <Select value={colorSeason} onValueChange={setColorSeason}>
                <SelectTrigger>
                  <SelectValue placeholder="Select colour season..." />
                </SelectTrigger>
                <SelectContent>
                  {COLOR_SEASON_OPTIONS.map((v) => (
                    <SelectItem key={v} value={v}>
                      {formatLabel(v)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Kibbe Lean {draftFetched && '(AI-suggested — edit if needed)'}</Label>
              <Select value={kibbeLean} onValueChange={setKibbeLean}>
                <SelectTrigger>
                  <SelectValue placeholder="Select Kibbe lean..." />
                </SelectTrigger>
                <SelectContent>
                  {KIBBE_LEAN_OPTIONS.map((v) => (
                    <SelectItem key={v} value={v}>
                      {formatLabel(v)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {draftFetched && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleGetSuggestion}
                disabled={styleDraft.isPending}
              >
                {styleDraft.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Re-run AI suggestion
              </Button>
            )}
          </div>
        )}

        <DialogFooter className="sm:justify-between">
          <div>
            {step > STEP_MEASUREMENTS && (
              <Button type="button" variant="ghost" onClick={goBack}>
                <ChevronLeft className="mr-2 h-4 w-4" /> Back
              </Button>
            )}
          </div>
          <div>
            {step < LAST_STEP ? (
              <Button type="button" onClick={goNext} disabled={!canAdvance(step, state)}>
                Next <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button
                type="button"
                onClick={handleSave}
                disabled={!canAdvance(step, state) || updateStyleProfile.isPending}
              >
                {updateStyleProfile.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
