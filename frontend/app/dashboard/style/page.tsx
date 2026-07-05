'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Sparkles, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useStyleProfile, useGuidance } from '@/lib/hooks/use-style-profile';
import { ProfileWizard } from '@/components/style/profile-wizard';
import { CLOTHING_COLORS } from '@/lib/types';

function formatLabel(value: string | null | undefined): string {
  if (!value) return 'Not set';
  return value
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Palette/season colour names largely reuse the CLOTHING_COLORS vocab (e.g. "navy",
// "burgundy"); a handful of season-only names (e.g. "silver", "gold", "light-blue") have
// no hex entry there, so those fall back to a plain labelled chip instead of a swatch.
function ColorSwatch({ name }: { name: string }) {
  const colorInfo = CLOTHING_COLORS.find((c) => c.value === name);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-muted/40 px-2.5 py-1 text-xs">
      {colorInfo && (
        <span
          className="h-3 w-3 shrink-0 rounded-full border"
          style={{ backgroundColor: colorInfo.hex }}
        />
      )}
      {colorInfo?.name ?? formatLabel(name)}
    </span>
  );
}

function AttrChipGroup({
  title,
  attrs,
  variant,
}: {
  title: string;
  attrs: Record<string, string[]>;
  variant: 'default' | 'outline';
}) {
  const entries = Object.entries(attrs).filter(([, values]) => values.length > 0);
  if (entries.length === 0) return null;

  return (
    <div>
      <h4 className="mb-2 text-sm font-medium">{title}</h4>
      <div className="space-y-2">
        {entries.map(([key, values]) => (
          <div key={key} className="flex flex-wrap items-center gap-1.5">
            <span className="w-20 shrink-0 text-xs capitalize text-muted-foreground">{key}</span>
            {values.map((value) => (
              <Badge key={value} variant={variant}>
                {formatLabel(value)}
              </Badge>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-6 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function StyleProfilePage() {
  const { data: profile, isLoading: profileLoading, isError: profileIsError } = useStyleProfile();
  const { data: guidance, isLoading: guidanceLoading } = useGuidance();
  const [wizardOpen, setWizardOpen] = useState(false);

  if (profileLoading) {
    return <LoadingSkeleton />;
  }

  const hasProfile =
    !!profile &&
    Boolean(
      profile.body_shape ||
        profile.vertical_line ||
        profile.frame ||
        profile.color_season ||
        profile.kibbe_lean
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Sparkles className="h-6 w-6" />
            Style Profile
          </h1>
          <p className="text-muted-foreground">
            Your body shape, colour season, Kibbe lean, and personalized styling guidance.
          </p>
        </div>
        <Button onClick={() => setWizardOpen(true)}>
          {hasProfile ? 'Edit Profile' : 'Set Up Profile'}
        </Button>
      </div>

      {profileIsError && (
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load your style profile</CardTitle>
            <CardDescription>Please refresh the page or try again shortly.</CardDescription>
          </CardHeader>
        </Card>
      )}

      {!profileIsError && !hasProfile && (
        <Card>
          <CardHeader>
            <CardTitle>No style profile yet</CardTitle>
            <CardDescription>
              Add your body measurements in Settings to compute your shape, then confirm a
              colour season and Kibbe lean to unlock personalized styling guidance. Use the
              guided setup wizard above, or add measurements manually first.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href="/dashboard/settings">Add measurements in Settings</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {!profileIsError && hasProfile && profile && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Body Shape</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-semibold">{formatLabel(profile.body_shape)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Vertical Line</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-semibold">{formatLabel(profile.vertical_line)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Frame</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-semibold">{formatLabel(profile.frame)}</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Colour Season &amp; Kibbe Lean</CardTitle>
              <CardDescription>Confirmed values used to personalize recommendations.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-muted-foreground">Colour Season</div>
                  <div className="font-medium">{formatLabel(profile.color_season)}</div>
                </div>
                <Badge variant={profile.season_confirmed ? 'default' : 'secondary'}>
                  {profile.season_confirmed && <CheckCircle2 className="mr-1 h-3 w-3" />}
                  {profile.season_confirmed ? 'Confirmed' : 'Unconfirmed'}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-muted-foreground">Kibbe Lean</div>
                  <div className="font-medium">{formatLabel(profile.kibbe_lean)}</div>
                </div>
                <Badge variant={profile.kibbe_confirmed ? 'default' : 'secondary'}>
                  {profile.kibbe_confirmed && <CheckCircle2 className="mr-1 h-3 w-3" />}
                  {profile.kibbe_confirmed ? 'Confirmed' : 'Unconfirmed'}
                </Badge>
              </div>
              {profile.palette.length > 0 && (
                <div>
                  <div className="mb-2 text-sm text-muted-foreground">Palette</div>
                  <div className="flex flex-wrap gap-2">
                    {profile.palette.map((color) => (
                      <ColorSwatch key={color} name={color} />
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Styling Guidance</CardTitle>
              <CardDescription>
                Deterministic fit/cut recommendations for your body shape, plus your season palette.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {guidanceLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : guidance ? (
                <>
                  {guidance.summary && <p className="text-sm">{guidance.summary}</p>}
                  <AttrChipGroup title="Recommended" attrs={guidance.recommended} variant="default" />
                  <AttrChipGroup title="Avoid" attrs={guidance.avoid} variant="outline" />
                  {guidance.palette.length > 0 && (
                    <div>
                      <h4 className="mb-2 text-sm font-medium">Palette</h4>
                      <div className="flex flex-wrap gap-2">
                        {guidance.palette.map((color) => (
                          <ColorSwatch key={color} name={color} />
                        ))}
                      </div>
                    </div>
                  )}
                  {!guidance.summary &&
                    Object.keys(guidance.recommended).length === 0 &&
                    Object.keys(guidance.avoid).length === 0 &&
                    guidance.palette.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No guidance available yet — add measurements and confirm a colour season
                        to unlock personalized tips.
                      </p>
                    )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Guidance is unavailable right now.</p>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <ProfileWizard open={wizardOpen} onOpenChange={setWizardOpen} />
    </div>
  );
}
