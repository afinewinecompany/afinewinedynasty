import ProspectsPageClient from './ProspectsPageClient';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Prospect Rankings | A Fine Wine Dynasty',
  description:
    'Top 500 MLB prospects with detailed stats, analysis, and composite rankings combining FanGraphs grades with MiLB performance data for dynasty fantasy baseball.',
  keywords:
    'MLB prospects, dynasty fantasy baseball, prospect rankings, baseball stats, composite rankings, FanGraphs',
};

export default function ProspectsPage() {
  return <ProspectsPageClient />;
}
