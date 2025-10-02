'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import { Badge } from '@/components/ui/badge';
import {
  Lightbulb,
  TrendingUp,
  Eye,
  Building2,
  Target,
  ArrowRight,
  AlertCircle,
  Star
} from 'lucide-react';
import Link from 'next/link';

/**
 * Props for the DiscoveryInsights component
 *
 * @interface DiscoveryInsightsProps
 * @since 1.0.0
 */
interface DiscoveryInsightsProps {
  /** Array of breakout candidate data */
  breakoutCandidates?: any[];
  /** Array of sleeper prospect data */
  sleeperProspects?: any[];
  /** Array of organizational insight data */
  organizationalInsights?: any[];
  /** Array of position scarcity data */
  positionScarcity?: any[];
  /** Additional metadata about discovery analysis */
  metadata?: any;
  /** Loading state indicator */
  isLoading?: boolean;
  /** Error object from failed operations */
  error?: any;
}

/**
 * Discovery Insights Overview Component
 *
 * Provides a comprehensive summary dashboard of discovery findings with
 * personalized recommendations synthesized from all discovery categories
 * (breakout candidates, sleeper prospects, organizational pipeline, and
 * position scarcity). Serves as the executive summary for discovery analysis.
 *
 * Features:
 * - Key discovery highlights with icon indicators
 * - Top recommendations across all categories
 * - Quick stats and count summaries
 * - Actionable insights with priority indicators
 * - Navigation links to detailed category views
 * - Visual badges for discovery types
 * - Personalized recommendations based on patterns
 * - Cross-category synthesis and correlations
 *
 * @component
 * @param {DiscoveryInsightsProps} props - Component properties
 * @returns {JSX.Element} Discovery insights summary dashboard
 *
 * @example
 * ```tsx
 * <DiscoveryInsights
 *   breakoutCandidates={breakouts}
 *   sleeperProspects={sleepers}
 *   organizationalInsights={orgData}
 *   positionScarcity={scarcityData}
 *   metadata={analysisMetadata}
 *   isLoading={isLoading}
 *   error={error}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function DiscoveryInsights({
  breakoutCandidates = [],
  sleeperProspects = [],
  organizationalInsights = [],
  positionScarcity = [],
  metadata,
  isLoading = false,
  error
}: DiscoveryInsightsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <ErrorMessage message="Failed to load discovery insights" />
        </CardContent>
      </Card>
    );
  }

  // Calculate key insights
  const topBreakout = breakoutCandidates[0];
  const topSleeper = sleeperProspects[0];
  const bestOpportunity = organizationalInsights.sort((a, b) => b.opportunity_score - a.opportunity_score)[0];
  const mostScarce = positionScarcity.sort((a, b) => b.scarcity_score - a.scarcity_score)[0];

  const insights = [
    {
      category: 'Top Breakout Candidate',
      icon: TrendingUp,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      data: topBreakout,
      title: topBreakout?.prospect_name,
      subtitle: topBreakout && `${topBreakout.position} | ${topBreakout.organization}`,
      metric: topBreakout?.breakout_score?.toFixed(1),
      metricLabel: 'Breakout Score',
      description: topBreakout && `${topBreakout.improvement_rate.toFixed(0)}% improvement over last ${topBreakout.lookback_days} days`
    },
    {
      category: 'Top Sleeper Prospect',
      icon: Eye,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      data: topSleeper,
      title: topSleeper?.prospect_name,
      subtitle: topSleeper && `${topSleeper.position} | ${topSleeper.organization}`,
      metric: topSleeper?.sleeper_score?.toFixed(1),
      metricLabel: 'Sleeper Score',
      description: topSleeper && `ML ranks ${topSleeper.ranking_differential} spots higher than consensus`
    },
    {
      category: 'Best Opportunity',
      icon: Building2,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      data: bestOpportunity,
      title: bestOpportunity?.organization,
      subtitle: bestOpportunity && `#${bestOpportunity.system_ranking} farm system`,
      metric: bestOpportunity?.opportunity_score,
      metricLabel: 'Opportunity',
      description: bestOpportunity && `${bestOpportunity.total_prospects} prospects with ${bestOpportunity.strengths[0]} strength`
    },
    {
      category: 'Scarcest Position',
      icon: Target,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      data: mostScarce,
      title: mostScarce?.position,
      subtitle: mostScarce && `${mostScarce.total_prospects} total prospects`,
      metric: mostScarce?.scarcity_score,
      metricLabel: 'Scarcity',
      description: mostScarce && `Only ${mostScarce.elite_prospects} elite prospects available`
    }
  ];

  return (
    <div className="space-y-6">
      {/* Key Insights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {insights.map((insight) => {
          const Icon = insight.icon;
          if (!insight.data) return null;

          return (
            <Card key={insight.category} className="hover:shadow-lg transition-all">
              <CardContent className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={`p-2 rounded-lg ${insight.bgColor}`}>
                    <Icon className={`h-6 w-6 ${insight.color}`} />
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {insight.category}
                  </Badge>
                </div>

                <div className="space-y-2">
                  <div>
                    <h3 className="font-semibold text-lg">{insight.title}</h3>
                    <p className="text-sm text-gray-600">{insight.subtitle}</p>
                  </div>

                  <div className="flex items-baseline gap-2">
                    <span className={`text-3xl font-bold ${insight.color}`}>
                      {insight.metric}
                    </span>
                    <span className="text-sm text-gray-500">{insight.metricLabel}</span>
                  </div>

                  <p className="text-sm text-gray-700 mt-2">
                    {insight.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary Statistics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Star className="h-5 w-5" />
            Discovery Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {breakoutCandidates.length}
              </div>
              <div className="text-sm text-gray-600 mt-1">Breakout Candidates</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {sleeperProspects.length}
              </div>
              <div className="text-sm text-gray-600 mt-1">Sleeper Prospects</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {organizationalInsights.filter(o => o.opportunity_score >= 70).length}
              </div>
              <div className="text-sm text-gray-600 mt-1">High Opportunity Orgs</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">
                {positionScarcity.filter(p => p.scarcity_score >= 60).length}
              </div>
              <div className="text-sm text-gray-600 mt-1">Scarce Positions</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Actionable Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Recommended Actions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {topBreakout && (
              <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
                <AlertCircle className="h-5 w-5 text-green-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-green-900">
                    Consider acquiring {topBreakout.prospect_name}
                  </p>
                  <p className="text-xs text-green-700 mt-1">
                    Showing significant improvement with {topBreakout.improvement_rate.toFixed(0)}% performance gain
                  </p>
                </div>
                <Link href={`/prospects/${topBreakout.prospect_id}`}>
                  <Button size="sm" variant="ghost" className="text-green-600">
                    View Profile
                    <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </Link>
              </div>
            )}

            {topSleeper && (
              <div className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
                <AlertCircle className="h-5 w-5 text-purple-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-purple-900">
                    {topSleeper.prospect_name} is potentially undervalued
                  </p>
                  <p className="text-xs text-purple-700 mt-1">
                    ML models project significantly higher value than current consensus ranking
                  </p>
                </div>
                <Link href={`/prospects/${topSleeper.prospect_id}`}>
                  <Button size="sm" variant="ghost" className="text-purple-600">
                    View Profile
                    <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </Link>
              </div>
            )}

            {mostScarce && mostScarce.scarcity_score >= 70 && (
              <div className="flex items-start gap-3 p-3 bg-red-50 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-900">
                    Prioritize {mostScarce.position} prospects
                  </p>
                  <p className="text-xs text-red-700 mt-1">
                    High scarcity with limited elite prospects available in the pipeline
                  </p>
                </div>
                <Link href="/search/advanced">
                  <Button size="sm" variant="ghost" className="text-red-600">
                    Search {mostScarce.position}
                    <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link href="/search/advanced?breakout=true">
          <Button variant="outline" className="w-full justify-start">
            <TrendingUp className="h-4 w-4 mr-2" />
            View All Breakouts
          </Button>
        </Link>
        <Link href="/search/advanced?sleeper=true">
          <Button variant="outline" className="w-full justify-start">
            <Eye className="h-4 w-4 mr-2" />
            View All Sleepers
          </Button>
        </Link>
        <Link href="/discovery?tab=organizations">
          <Button variant="outline" className="w-full justify-start">
            <Building2 className="h-4 w-4 mr-2" />
            Org Analysis
          </Button>
        </Link>
        <Link href="/discovery?tab=positions">
          <Button variant="outline" className="w-full justify-start">
            <Target className="h-4 w-4 mr-2" />
            Position Analysis
          </Button>
        </Link>
      </div>
    </div>
  );
}