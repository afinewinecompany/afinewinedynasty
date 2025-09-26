import { Metadata, ResolvingMetadata } from 'next';
import { notFound } from 'next/navigation';
import ProspectProfile from '@/components/prospects/ProspectProfile';

interface ProspectPageProps {
  params: {
    id: string;
  };
  searchParams: { [key: string]: string | string[] | undefined };
}

// Mock function to get prospect data for metadata
// In production, this would fetch from your API
async function getProspectForMetadata(id: string) {
  // Mock data - replace with actual API call
  return {
    name: `Prospect ${id}`,
    position: 'SS',
    organization: 'Yankees',
    level: 'AA',
    age: 21,
    eta_year: 2025,
    dynasty_score: 75.5
  };
}

export async function generateMetadata(
  { params }: ProspectPageProps,
  parent: ResolvingMetadata
): Promise<Metadata> {
  const { id } = params;

  try {
    const prospect = await getProspectForMetadata(id);

    const title = `${prospect.name} - ${prospect.position} | A Fine Wine Dynasty`;
    const description = `Comprehensive prospect profile for ${prospect.name}, ${prospect.position} in the ${prospect.organization} organization. Features ML predictions, scouting grades, statistical analysis, and dynasty rankings.`;

    // Generate Open Graph image URL (this would point to a dynamic image generator)
    const ogImageUrl = `${process.env.NEXT_PUBLIC_SITE_URL || 'https://afinewinedynasty.com'}/api/og/prospect?id=${id}&name=${encodeURIComponent(prospect.name)}&position=${prospect.position}&organization=${encodeURIComponent(prospect.organization)}&score=${prospect.dynasty_score}`;

    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://afinewinedynasty.com';
    const prospectUrl = `${siteUrl}/prospects/${id}`;

    return {
      title,
      description,
      openGraph: {
        title,
        description,
        type: 'article',
        url: prospectUrl,
        images: [
          {
            url: ogImageUrl,
            width: 1200,
            height: 630,
            alt: `${prospect.name} prospect profile`
          }
        ],
        siteName: 'A Fine Wine Dynasty',
        locale: 'en_US'
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
        images: [ogImageUrl],
        creator: '@afinewinedynasty',
        site: '@afinewinedynasty'
      },
      keywords: [
        prospect.name,
        prospect.position,
        prospect.organization,
        'baseball prospect',
        'dynasty fantasy',
        'prospect rankings',
        'scouting report',
        'MLB prospect',
        'minor league',
        prospect.level,
        'baseball analysis',
        'prospect evaluation'
      ],
      authors: [{ name: 'A Fine Wine Dynasty' }],
      creator: 'A Fine Wine Dynasty',
      publisher: 'A Fine Wine Dynasty',
      robots: {
        index: true,
        follow: true,
        googleBot: {
          index: true,
          follow: true,
          'max-video-preview': -1,
          'max-image-preview': 'large',
          'max-snippet': -1,
        },
      },
      alternates: {
        canonical: prospectUrl,
      }
    };
  } catch (error) {
    // Fallback metadata if prospect fetch fails
    return {
      title: `Prospect ${id} | A Fine Wine Dynasty`,
      description: `Detailed prospect profile with stats, ML predictions, and scouting analysis for dynasty fantasy baseball.`,
      keywords: 'MLB prospect profile, dynasty fantasy baseball, prospect stats, baseball analysis',
    };
  }
}

export default async function ProspectPage({ params }: ProspectPageProps) {
  const { id } = params;

  // Validate that id is provided
  if (!id) {
    notFound();
  }

  // Get prospect data for JSON-LD
  let prospectData;
  try {
    prospectData = await getProspectForMetadata(id);
  } catch (error) {
    prospectData = null;
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://afinewinedynasty.com';

  return (
    <>
      {/* JSON-LD structured data for search engines */}
      {prospectData && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Person",
              "name": prospectData.name,
              "description": `Baseball prospect ${prospectData.name}, ${prospectData.position} in the ${prospectData.organization} organization`,
              "jobTitle": "Baseball Player",
              "memberOf": {
                "@type": "SportsOrganization",
                "name": prospectData.organization
              },
              "sport": "Baseball",
              "url": `${siteUrl}/prospects/${id}`,
              "image": `${siteUrl}/api/og/prospect?id=${id}`,
              "additionalProperty": [
                {
                  "@type": "PropertyValue",
                  "name": "Position",
                  "value": prospectData.position
                },
                {
                  "@type": "PropertyValue",
                  "name": "Organization",
                  "value": prospectData.organization
                },
                {
                  "@type": "PropertyValue",
                  "name": "Level",
                  "value": prospectData.level
                },
                {
                  "@type": "PropertyValue",
                  "name": "Age",
                  "value": prospectData.age.toString()
                },
                {
                  "@type": "PropertyValue",
                  "name": "ETA Year",
                  "value": prospectData.eta_year.toString()
                },
                {
                  "@type": "PropertyValue",
                  "name": "Dynasty Score",
                  "value": prospectData.dynasty_score.toString()
                }
              ],
              "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": `${siteUrl}/prospects/${id}`
              },
              "publisher": {
                "@type": "Organization",
                "name": "A Fine Wine Dynasty",
                "url": siteUrl
              }
            })
          }}
        />
      )}

      <ProspectProfile id={id} />
    </>
  );
}
