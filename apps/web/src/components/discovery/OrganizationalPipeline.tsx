'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Building2, Users, TrendingUp, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';

interface ProspectByPosition {
  position: string;
  count: number;
  avg_grade: number;
  top_prospects: string[];
}

interface OrganizationalInsight {
  organization: string;
  total_prospects: number;
  system_ranking: number;
  depth_score: number;
  opportunity_score: number;
  strengths: string[];
  weaknesses: string[];
  prospects_by_position: ProspectByPosition[];
  eta_distribution: {
    [year: string]: number;
  };
  competitive_depth: {
    position: string;
    current_mlb_blocked: boolean;
    depth_ahead: number;
    opportunity_window: string;
  }[];
}

interface OrganizationalPipelineProps {
  insights?: OrganizationalInsight[];
  isLoading?: boolean;
  error?: any;
  onRefresh?: () => void;
}

/**
 * Organizational Pipeline Analysis Component
 *
 * Provides comprehensive farm system depth analysis with prospect density
 * calculation and opportunity identification. Evaluates organizational strengths,
 * weaknesses, and positional opportunities for dynasty league decision-making.
 *
 * Features:
 * - Farm system ranking and depth scoring (0-100 scale)
 * - Positional depth charts showing top prospects by position
 * - ETA timeline distribution for prospect arrival projections
 * - Competitive depth analysis with MLB blocking assessment
 * - Opportunity window identification for optimal call-up timing
 * - Expandable/collapsible organizational detail views
 * - Strengths and weaknesses identification
 * - Top prospects highlighting by organization
 *
 * @component
 * @param {OrganizationalPipelineProps} props - Component properties
 * @returns {JSX.Element} Organizational pipeline analysis interface with depth metrics
 *
 * @example
 * ```tsx
 * <OrganizationalPipeline
 *   insights={organizationalData}
 *   isLoading={isLoadingPipeline}
 *   error={pipelineError}
 *   onRefresh={refetchPipelineData}
 * />
 * ```
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export function OrganizationalPipeline({
  insights = [],
  isLoading = false,
  error,
  onRefresh
}: OrganizationalPipelineProps) {
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'depth' | 'opportunity'>('depth');

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <ErrorMessage message="Failed to load organizational insights" />
          {onRefresh && (
            <Button onClick={onRefresh} className="mt-4">
              Try Again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const sortedInsights = [...insights].sort((a, b) => {
    if (viewMode === 'depth') {
      return b.depth_score - a.depth_score;
    } else {
      return b.opportunity_score - a.opportunity_score;
    }
  });

  const getDepthScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-blue-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getOpportunityIndicator = (score: number) => {
    if (score >= 80) return { color: 'bg-green-500', label: 'High' };
    if (score >= 60) return { color: 'bg-yellow-500', label: 'Medium' };
    return { color: 'bg-red-500', label: 'Low' };
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                Organizational Pipeline Analysis
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">
                Farm system depth and prospect opportunity assessment
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={viewMode === 'depth' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setViewMode('depth')}
              >
                Depth View
              </Button>
              <Button
                variant={viewMode === 'opportunity' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setViewMode('opportunity')}
              >
                Opportunity View
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {sortedInsights.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No organizational data available
            </div>
          ) : (
            <div className="space-y-4">
              {sortedInsights.map((org) => {
                const isExpanded = expandedOrg === org.organization;
                const opportunityIndicator = getOpportunityIndicator(org.opportunity_score);

                return (
                  <Card
                    key={org.organization}
                    className={`transition-all ${
                      isExpanded ? 'shadow-lg' : 'hover:shadow-md'
                    }`}
                  >
                    <CardContent className="p-4">
                      {/* Header */}
                      <div
                        className="cursor-pointer"
                        onClick={() => setExpandedOrg(isExpanded ? null : org.organization)}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h3 className="text-lg font-semibold">{org.organization}</h3>
                              <Badge variant="outline">
                                #{org.system_ranking} System
                              </Badge>
                              <Badge className={`${opportunityIndicator.color} text-white`}>
                                {opportunityIndicator.label} Opportunity
                              </Badge>
                            </div>
                            <div className="flex items-center gap-4 mt-2 text-sm">
                              <span className="flex items-center gap-1">
                                <Users className="h-4 w-4 text-gray-500" />
                                {org.total_prospects} prospects
                              </span>
                              <span className={`font-semibold ${getDepthScoreColor(org.depth_score)}`}>
                                Depth: {org.depth_score}/100
                              </span>
                              <span className="font-semibold text-purple-600">
                                Opportunity: {org.opportunity_score}/100
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center">
                            {isExpanded ? (
                              <ChevronUp className="h-5 w-5 text-gray-400" />
                            ) : (
                              <ChevronDown className="h-5 w-5 text-gray-400" />
                            )}
                          </div>
                        </div>

                        {/* Quick Stats */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                          <div className="text-center p-2 bg-gray-50 rounded">
                            <div className="text-xs text-gray-500">Strengths</div>
                            <div className="text-sm font-medium mt-1">
                              {org.strengths.slice(0, 2).join(', ')}
                            </div>
                          </div>
                          <div className="text-center p-2 bg-gray-50 rounded">
                            <div className="text-xs text-gray-500">Weaknesses</div>
                            <div className="text-sm font-medium mt-1">
                              {org.weaknesses.slice(0, 2).join(', ') || 'None'}
                            </div>
                          </div>
                          <div className="text-center p-2 bg-gray-50 rounded">
                            <div className="text-xs text-gray-500">Top Position</div>
                            <div className="text-sm font-medium mt-1">
                              {org.prospects_by_position[0]?.position || 'N/A'}
                              ({org.prospects_by_position[0]?.count || 0})
                            </div>
                          </div>
                          <div className="text-center p-2 bg-gray-50 rounded">
                            <div className="text-xs text-gray-500">Next Wave</div>
                            <div className="text-sm font-medium mt-1">
                              {Object.keys(org.eta_distribution)[0] || 'N/A'}
                              ({org.eta_distribution[Object.keys(org.eta_distribution)[0]] || 0})
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Expanded Content */}
                      {isExpanded && (
                        <div className="mt-4 pt-4 border-t space-y-4">
                          {/* Positional Depth */}
                          <div>
                            <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                              <Users className="h-4 w-4" />
                              Positional Depth
                            </h4>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                              {org.prospects_by_position.map((pos) => (
                                <div
                                  key={pos.position}
                                  className="flex items-center justify-between p-2 bg-gray-50 rounded"
                                >
                                  <div>
                                    <div className="font-medium">{pos.position}</div>
                                    <div className="text-xs text-gray-500">
                                      {pos.count} prospects
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-sm font-semibold">
                                      {pos.avg_grade.toFixed(1)}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      Avg Grade
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* ETA Distribution */}
                          <div>
                            <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                              <TrendingUp className="h-4 w-4" />
                              ETA Timeline Distribution
                            </h4>
                            <div className="flex items-end gap-2 h-24">
                              {Object.entries(org.eta_distribution).map(([year, count]) => {
                                const maxCount = Math.max(...Object.values(org.eta_distribution));
                                const height = (count / maxCount) * 100;
                                return (
                                  <div
                                    key={year}
                                    className="flex-1 flex flex-col items-center"
                                  >
                                    <div className="w-full bg-blue-500 rounded-t transition-all hover:bg-blue-600"
                                      style={{ height: `${height}%` }}
                                      title={`${count} prospects`}
                                    />
                                    <div className="text-xs mt-1">{year}</div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* Competitive Depth / Opportunity */}
                          <div>
                            <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                              <AlertTriangle className="h-4 w-4" />
                              Position Opportunities
                            </h4>
                            <div className="space-y-2">
                              {org.competitive_depth.slice(0, 5).map((depth, idx) => (
                                <div
                                  key={idx}
                                  className="flex items-center justify-between p-2 bg-gray-50 rounded"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium">{depth.position}</span>
                                    {depth.current_mlb_blocked && (
                                      <Badge variant="outline" className="text-xs">
                                        Blocked
                                      </Badge>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-3 text-sm">
                                    <span className="text-gray-600">
                                      {depth.depth_ahead} ahead
                                    </span>
                                    <Badge
                                      className={`text-xs ${
                                        depth.opportunity_window === 'Immediate'
                                          ? 'bg-green-100 text-green-800'
                                          : depth.opportunity_window === '1-2 years'
                                          ? 'bg-yellow-100 text-yellow-800'
                                          : 'bg-gray-100 text-gray-800'
                                      }`}
                                    >
                                      {depth.opportunity_window}
                                    </Badge>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Top Prospects */}
                          <div>
                            <h4 className="text-sm font-semibold mb-2">
                              Top Prospects in System
                            </h4>
                            <div className="flex flex-wrap gap-2">
                              {org.prospects_by_position.flatMap(p => p.top_prospects).slice(0, 8).map((name, idx) => (
                                <Badge key={idx} variant="outline">
                                  {name}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Statistics */}
      {insights.length > 0 && (
        <Card>
          <CardContent className="py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-gray-500">Organizations</div>
                <div className="text-2xl font-bold">{insights.length}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Total Prospects</div>
                <div className="text-2xl font-bold">
                  {insights.reduce((sum, org) => sum + org.total_prospects, 0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Avg Depth Score</div>
                <div className="text-2xl font-bold">
                  {(insights.reduce((sum, org) => sum + org.depth_score, 0) / insights.length).toFixed(0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">High Opportunity</div>
                <div className="text-2xl font-bold">
                  {insights.filter(org => org.opportunity_score >= 80).length}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}