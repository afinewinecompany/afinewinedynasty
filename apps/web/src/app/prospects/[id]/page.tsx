import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ProspectProfile from '@/components/prospects/ProspectProfile';

interface ProspectPageProps {
  params: {
    id: string;
  };
}

export async function generateMetadata({
  params,
}: ProspectPageProps): Promise<Metadata> {
  // In a real app, you might fetch the prospect name here for better SEO
  // For now, we'll use a generic title based on the id
  const { id } = params;

  return {
    title: `Prospect ${id} | A Fine Wine Dynasty`,
    description: `Detailed prospect profile with stats, ML predictions, and scouting analysis for dynasty fantasy baseball.`,
    keywords:
      'MLB prospect profile, dynasty fantasy baseball, prospect stats, baseball analysis',
  };
}

export default function ProspectPage({ params }: ProspectPageProps) {
  const { id } = params;

  // Validate that id is provided
  if (!id) {
    notFound();
  }

  return <ProspectProfile id={id} />;
}
