import dynamic from 'next/dynamic';

const ProspectsPageClient = dynamic(() => import('./ProspectsPageClient'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
    </div>
  ),
});

export default function ProspectsPage() {
  return <ProspectsPageClient />;
}
