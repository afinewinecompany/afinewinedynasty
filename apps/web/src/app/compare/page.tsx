'use client';

import ProspectComparison from '@/components/prospects/ProspectComparison';

export default function ComparePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Prospect Comparison Tool
          </h1>
          <p className="text-gray-600">
            Compare 2-4 prospects side-by-side with comprehensive analytics, ML
            predictions, and historical comparisons
          </p>
        </div>

        <ProspectComparison />
      </div>
    </div>
  );
}
