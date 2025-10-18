import { Metadata } from 'next';
import ProspectRankingsDashboard from '@/components/rankings/ProspectRankingsDashboard';

export const metadata: Metadata = {
  title: 'Prospect Rankings | A Fine Wine Dynasty',
  description:
    'Top 100 MLB prospects with detailed stats, analysis, and ML predictions for dynasty fantasy baseball.',
  keywords:
    'MLB prospects, dynasty fantasy baseball, prospect rankings, baseball stats',
};

export default function ProspectsPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <ProspectRankingsDashboard />
    </main>
  );
}
