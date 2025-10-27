'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { CompositeRanking } from '@/types/prospect';
import { calculateAllPercentiles } from '@/utils/calculatePercentiles';

interface PercentilesContextType {
  percentiles: Map<number, Record<string, number>>;
  allProspects: CompositeRanking[];
}

const PercentilesContext = createContext<PercentilesContextType | null>(null);

export function PercentilesProvider({
  children,
  prospects,
}: {
  children: React.ReactNode;
  prospects: CompositeRanking[];
}) {
  // Calculate percentiles for all prospects whenever the prospect list changes
  const percentiles = useMemo(() => {
    return calculateAllPercentiles(prospects);
  }, [prospects]);

  return (
    <PercentilesContext.Provider value={{ percentiles, allProspects: prospects }}>
      {children}
    </PercentilesContext.Provider>
  );
}

export function usePercentiles() {
  const context = useContext(PercentilesContext);
  if (!context) {
    throw new Error('usePercentiles must be used within a PercentilesProvider');
  }
  return context;
}

/**
 * Hook to get percentiles for a specific prospect
 */
export function useProspectPercentiles(prospectId: number): Record<string, number> {
  const { percentiles } = usePercentiles();
  return percentiles.get(prospectId) || {};
}