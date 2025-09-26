import { Metadata } from 'next';
import ProspectsList from '@/components/prospects/ProspectsList';

export const metadata: Metadata = {
  title: 'Prospect Rankings | A Fine Wine Dynasty',
  description:
    'Top 100 MLB prospects with detailed stats, analysis, and ML predictions for dynasty fantasy baseball.',
  keywords:
    'MLB prospects, dynasty fantasy baseball, prospect rankings, baseball stats',
};

export default function ProspectsPage() {
  return <ProspectsList />;
}
