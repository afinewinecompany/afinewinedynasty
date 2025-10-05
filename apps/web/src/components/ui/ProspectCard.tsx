import Link from 'next/link';
import { Prospect } from '@/types/prospect';
import ProspectOutlook from '@/components/prospects/ProspectOutlook';

interface ProspectCardProps {
  prospect: Prospect;
  rank?: number;
  showOutlook?: boolean;
  showRanking?: boolean;
  showConfidence?: boolean;
}

export function ProspectCard({
  prospect,
  rank,
  showOutlook = false,
  showRanking = false,
  showConfidence = false,
}: ProspectCardProps) {
  // Use dynastyRank from prospect if rank prop not provided and showRanking is true
  const displayRank = rank ?? (showRanking && 'dynastyRank' in prospect ? prospect.dynastyRank : undefined);
  return (
    <div className="rounded-lg border border-gray-200 bg-white hover:border-gray-300 hover:shadow-md transition-all duration-200">
      <Link href={`/prospects/${prospect.id}`} className="block p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center space-x-3">
              {displayRank && (
                <div className="flex-shrink-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-800">
                    #{displayRank}
                  </div>
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-900">
                  {prospect.name}
                </p>
                <div className="flex items-center space-x-2 text-xs text-gray-500">
                  <span>{prospect.position}</span>
                  <span>•</span>
                  <span className="truncate">{prospect.organization}</span>
                </div>
              </div>
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <div className="text-xs text-gray-500 mb-1">Age {prospect.age}</div>
            <div className="flex items-center space-x-1">
              <span className="text-xs text-gray-500">{prospect.level}</span>
              {prospect.eta_year && (
                <>
                  <span className="text-xs text-gray-300">•</span>
                  <span className="text-xs text-gray-500">
                    ETA {prospect.eta_year}
                  </span>
                </>
              )}
            </div>
            {showConfidence && 'confidenceLevel' in prospect && (
              <div className="text-xs font-medium text-gray-700 mt-1">
                {prospect.confidenceLevel}
              </div>
            )}
          </div>
        </div>
      </Link>

      {/* Compact AI Outlook */}
      {showOutlook && (
        <div className="px-4 pb-4">
          <ProspectOutlook prospectId={prospect.id.toString()} compact />
        </div>
      )}
    </div>
  );
}

export default ProspectCard;
