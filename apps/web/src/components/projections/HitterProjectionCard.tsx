'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';

interface HitterProjection {
  prospect_id: number;
  prospect_name: string;
  position: string;
  slash_line: string;
  projections: {
    avg: number;
    obp: number;
    slg: number;
    ops: number;
    bb_rate: number;
    k_rate: number;
    iso: number;
  };
  confidence_scores: {
    avg: number;
    obp: number;
    slg: number;
    ops: number;
    bb_rate: number;
    k_rate: number;
    iso: number;
  };
  overall_confidence: number;
  confidence_level: 'high' | 'medium' | 'low';
  model_version: string;
}

interface Props {
  prospectId: number;
}

export default function HitterProjectionCard({ prospectId }: Props) {
  const { data, isLoading, error } = useQuery<HitterProjection>({
    queryKey: ['hitter-projection', prospectId],
    queryFn: async () => {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/ml/projections/hitter/${prospectId}`
      );
      if (!res.ok) {
        if (res.status === 404) throw new Error('Projection not available');
        if (res.status === 503) throw new Error('Model not available');
        throw new Error('Failed to fetch projection');
      }
      return res.json();
    },
    retry: false,
  });

  if (isLoading) {
    return (
      <Card className="bg-wine-dark/50 border-wine-periwinkle/20 animate-pulse">
        <CardHeader>
          <div className="h-6 bg-wine-plum/50 rounded w-3/4"></div>
        </CardHeader>
        <CardContent>
          <div className="h-8 bg-wine-plum/50 rounded w-1/2 mb-4"></div>
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-12 bg-wine-plum/50 rounded"></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="bg-wine-dark/50 border-wine-periwinkle/20">
        <CardContent className="p-6 text-center">
          <p className="text-wine-periwinkle/70 text-sm">
            {error instanceof Error ? error.message : 'No projection available'}
          </p>
        </CardContent>
      </Card>
    );
  }

  const badgeConfig = {
    high: {
      variant: 'default' as const,
      className: 'bg-green-500/20 text-green-300 border-green-500/30',
    },
    medium: {
      variant: 'secondary' as const,
      className: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    },
    low: {
      variant: 'outline' as const,
      className: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    },
  };

  const confidenceBadge = badgeConfig[data.confidence_level];

  return (
    <Card className="bg-wine-dark/50 border-wine-periwinkle/20 hover:border-wine-periwinkle/40 transition-all">
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle className="text-white">
            <Link
              href={`/prospects/${data.prospect_id}`}
              className="hover:text-wine-periwinkle transition-colors"
            >
              {data.prospect_name}
            </Link>
            <span className="ml-2 text-wine-periwinkle/70 font-normal text-base">
              {data.position}
            </span>
          </CardTitle>
          <Badge
            variant={confidenceBadge.variant}
            className={confidenceBadge.className}
          >
            {data.confidence_level} confidence
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {/* Slash Line */}
        <div className="mb-6">
          <div className="text-wine-periwinkle/70 text-sm mb-1">
            Projected MLB Slash Line
          </div>
          <div className="text-3xl font-mono font-bold text-white">
            {data.slash_line}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <StatItem
            label="OPS"
            value={data.projections.ops.toFixed(3)}
            confidence={data.confidence_scores.ops}
          />
          <StatItem
            label="BB%"
            value={`${(data.projections.bb_rate * 100).toFixed(1)}%`}
            confidence={data.confidence_scores.bb_rate}
          />
          <StatItem
            label="K%"
            value={`${(data.projections.k_rate * 100).toFixed(1)}%`}
            confidence={data.confidence_scores.k_rate}
          />
          <StatItem
            label="ISO"
            value={data.projections.iso.toFixed(3)}
            confidence={data.confidence_scores.iso}
          />
        </div>

        {/* Overall Confidence Bar */}
        <div className="mt-4 pt-4 border-t border-wine-periwinkle/10">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-wine-periwinkle/70">Overall Confidence</span>
            <span className="text-wine-periwinkle">
              {(data.overall_confidence * 100).toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-wine-plum/50 rounded-full h-2">
            <div
              className="bg-wine-periwinkle h-2 rounded-full transition-all"
              style={{ width: `${data.overall_confidence * 100}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface StatItemProps {
  label: string;
  value: string;
  confidence: number;
}

function StatItem({ label, value, confidence }: StatItemProps) {
  const getConfidenceColor = (conf: number) => {
    if (conf > 0.4) return 'text-green-400';
    if (conf > 0.25) return 'text-blue-400';
    return 'text-orange-400';
  };

  return (
    <div className="bg-wine-plum/30 rounded-lg p-3">
      <div className="text-wine-periwinkle/70 text-xs mb-1">{label}</div>
      <div className="text-white text-lg font-semibold">{value}</div>
      <div className={`text-xs mt-1 ${getConfidenceColor(confidence)}`}>
        R² {confidence.toFixed(2)}
      </div>
    </div>
  );
}
