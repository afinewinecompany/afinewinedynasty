import { Metadata } from 'next';
import { Suspense } from 'react';
import ProspectsList from '@/components/prospects/ProspectsList';
import LoadingSpinner from '@/components/ui/LoadingSpinner';

export const metadata: Metadata = {
  title: 'Prospect Rankings | A Fine Wine Dynasty',
  description:
    'Top 100 MLB prospects with detailed stats, analysis, and ML predictions for dynasty fantasy baseball.',
  keywords:
    'MLB prospects, dynasty fantasy baseball, prospect rankings, baseball stats',
};

export default function ProspectsPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <ProspectsList />
    </Suspense>
  );
}
