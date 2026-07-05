import { describe, it, expect } from 'vitest'

import {
  canAdvance,
  hasShapeMeasurements,
  STEP_MEASUREMENTS,
  STEP_HINTS,
  STEP_PHOTO,
  STEP_CONFIRM,
  type WizardState,
} from '@/components/style/profile-wizard'

function baseState(overrides: Partial<WizardState> = {}): WizardState {
  return {
    hasMeasurements: true,
    undertone: 'cool',
    contrast: 'medium',
    colorSeason: 'cool-winter',
    kibbeLean: 'classic',
    ...overrides,
  }
}

describe('hasShapeMeasurements', () => {
  it('is false for null/undefined measurements', () => {
    expect(hasShapeMeasurements(null)).toBe(false)
    expect(hasShapeMeasurements(undefined)).toBe(false)
  })

  it('is false when waist or hips are missing', () => {
    expect(hasShapeMeasurements({ bust: 90 })).toBe(false)
    expect(hasShapeMeasurements({ bust: 90, waist: 70 })).toBe(false)
  })

  it('accepts chest as an alternative to bust', () => {
    expect(hasShapeMeasurements({ chest: 96, waist: 82, hips: 98 })).toBe(true)
  })

  it('is true when bust, waist, and hips are all positive', () => {
    expect(hasShapeMeasurements({ bust: 90, waist: 70, hips: 96 })).toBe(true)
  })

  it('rejects zero/negative or non-numeric values', () => {
    expect(hasShapeMeasurements({ bust: 0, waist: 70, hips: 96 })).toBe(false)
    expect(hasShapeMeasurements({ bust: -1, waist: 70, hips: 96 })).toBe(false)
    expect(hasShapeMeasurements({ bust: 'n/a', waist: 70, hips: 96 })).toBe(false)
  })

  it('accepts numeric strings (as stored via the settings form)', () => {
    expect(hasShapeMeasurements({ bust: '90', waist: '70', hips: '96' })).toBe(true)
  })
})

describe('canAdvance', () => {
  it('gates the measurements step on hasMeasurements', () => {
    expect(canAdvance(STEP_MEASUREMENTS, baseState({ hasMeasurements: false }))).toBe(false)
    expect(canAdvance(STEP_MEASUREMENTS, baseState({ hasMeasurements: true }))).toBe(true)
  })

  it('gates the hints step on undertone + contrast both being chosen', () => {
    expect(canAdvance(STEP_HINTS, baseState({ undertone: '', contrast: 'medium' }))).toBe(false)
    expect(canAdvance(STEP_HINTS, baseState({ undertone: 'cool', contrast: '' }))).toBe(false)
    expect(canAdvance(STEP_HINTS, baseState({ undertone: 'cool', contrast: 'medium' }))).toBe(true)
  })

  it('never blocks the optional photo step', () => {
    expect(canAdvance(STEP_PHOTO, baseState())).toBe(true)
  })

  it('gates the confirm/save step on both season and kibbe lean being set', () => {
    expect(canAdvance(STEP_CONFIRM, baseState({ colorSeason: '', kibbeLean: 'classic' }))).toBe(
      false
    )
    expect(canAdvance(STEP_CONFIRM, baseState({ colorSeason: 'cool-winter', kibbeLean: '' }))).toBe(
      false
    )
    expect(
      canAdvance(STEP_CONFIRM, baseState({ colorSeason: 'cool-winter', kibbeLean: 'classic' }))
    ).toBe(true)
  })

  it('returns false for an unknown step', () => {
    expect(canAdvance(99, baseState())).toBe(false)
  })
})
