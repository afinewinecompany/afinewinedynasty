'use client';

import { useState } from 'react';
import { BreakoutCandidates } from '@/components/discovery/BreakoutCandidates';
import { SleeperProspects } from '@/components/discovery/SleeperProspects';
import { OrganizationalPipeline } from '@/components/discovery/OrganizationalPipeline';
import { PositionScarcity } from '@/components/discovery/PositionScarcity';
import { DiscoveryInsights } from '@/components/discovery/DiscoveryInsights';
import { useDiscovery } from '@/hooks/useDiscovery';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  TrendingUp,
  Eye,
  Building2,
  Target,
  Settings,
  RefreshCcw,
  Lightbulb,
  Calendar,
} from 'lucide-react';

/**
 * Discovery Dashboard Page Component
 *
 * Main page component providing a comprehensive discovery interface for
 * identifying breakout candidates, sleeper prospects, organizational pipeline
 * opportunities, and position scarcity analysis. Serves as the primary entry
 * point for prospect discovery and opportunity identification using ML-powered
 * and time-series analysis algorithms.
 *
 * Features:
 * - Breakout candidates identification with recent performance trending indicators
 * - Sleeper prospects discovery with ML confidence vs consensus ranking analysis
 * - Organizational pipeline analysis showing farm system depth and opportunities
 * - Position scarcity analysis for dynasty league roster construction context
 * - Personalized discovery insights dashboard with cross-category synthesis
 * - Configurable discovery parameters (lookback periods, thresholds, confidence levels)
 * - Tabbed interface organizing different discovery categories
 * - Real-time data refresh capabilities
 * - Settings panel for customizing discovery algorithms
 *
 * @page
 * @returns {JSX.Element} Discovery dashboard page with tabbed analysis interface
 *
 * @example
 * Access via route: /discovery
 *
 * @since 1.0.0
 * @version 3.4.0
 */
export default function DiscoveryPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const [discoveryParams, setDiscoveryParams] = useState({
    lookback_days: 30,
    confidence_threshold: 0.7,
    limit_per_category: 10,
  });

  const {
    breakoutCandidates,
    sleeperProspects,
    organizationalInsights,
    positionScarcity,
    discoveryMetadata,
    isLoading,
    error,
    refetch,
  } = useDiscovery(discoveryParams);

  const handleParamsChange = (newParams: Partial<typeof discoveryParams>) => {
    setDiscoveryParams((prev) => ({ ...prev, ...newParams }));
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Discovery Dashboard
            </h1>
            <p className="text-lg text-gray-600">
              Identify breakout candidates, sleeper prospects, and market
              opportunities
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              <RefreshCcw
                className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`}
              />
              Refresh
            </Button>
          </div>
        </div>

        {/* Discovery Parameters */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Settings className="h-5 w-5" />
              Discovery Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="lookback-days" className="text-sm font-medium">
                  Lookback Period (Days)
                </Label>
                <Select
                  value={discoveryParams.lookback_days.toString()}
                  onValueChange={(value) =>
                    handleParamsChange({ lookback_days: parseInt(value) })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="14">14 days</SelectItem>
                    <SelectItem value="30">30 days</SelectItem>
                    <SelectItem value="60">60 days</SelectItem>
                    <SelectItem value="90">90 days</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label
                  htmlFor="confidence-threshold"
                  className="text-sm font-medium"
                >
                  ML Confidence Threshold
                </Label>
                <Select
                  value={discoveryParams.confidence_threshold.toString()}
                  onValueChange={(value) =>
                    handleParamsChange({
                      confidence_threshold: parseFloat(value),
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0.6">60%</SelectItem>
                    <SelectItem value="0.7">70%</SelectItem>
                    <SelectItem value="0.8">80%</SelectItem>
                    <SelectItem value="0.9">90%</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="limit" className="text-sm font-medium">
                  Results per Category
                </Label>
                <Select
                  value={discoveryParams.limit_per_category.toString()}
                  onValueChange={(value) =>
                    handleParamsChange({ limit_per_category: parseInt(value) })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">5</SelectItem>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="15">15</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {discoveryMetadata && (
              <div className="mt-4 flex items-center gap-4 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Last updated: {formatDate(discoveryMetadata.analysis_date)}
                </span>
                <span>
                  {discoveryMetadata.total_breakout_candidates} breakout
                  candidates
                </span>
                <span>
                  {discoveryMetadata.total_sleeper_prospects} sleeper prospects
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Discovery Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="breakout" className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Breakout
            {breakoutCandidates && (
              <span className="ml-1 bg-green-100 text-green-800 text-xs font-medium px-2 py-0.5 rounded-full">
                {breakoutCandidates.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="sleeper" className="flex items-center gap-2">
            <Eye className="h-4 w-4" />
            Sleeper
            {sleeperProspects && (
              <span className="ml-1 bg-purple-100 text-purple-800 text-xs font-medium px-2 py-0.5 rounded-full">
                {sleeperProspects.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger
            value="organizations"
            className="flex items-center gap-2"
          >
            <Building2 className="h-4 w-4" />
            Organizations
          </TabsTrigger>
          <TabsTrigger value="positions" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Positions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <DiscoveryInsights
            breakoutCandidates={breakoutCandidates}
            sleeperProspects={sleeperProspects}
            organizationalInsights={organizationalInsights}
            positionScarcity={positionScarcity}
            metadata={discoveryMetadata}
            isLoading={isLoading}
            error={error}
          />
        </TabsContent>

        <TabsContent value="breakout" className="mt-6">
          <BreakoutCandidates
            candidates={breakoutCandidates}
            isLoading={isLoading}
            error={error}
            onRefresh={refetch}
          />
        </TabsContent>

        <TabsContent value="sleeper" className="mt-6">
          <SleeperProspects
            prospects={sleeperProspects}
            isLoading={isLoading}
            error={error}
            onRefresh={refetch}
          />
        </TabsContent>

        <TabsContent value="organizations" className="mt-6">
          <OrganizationalPipeline
            insights={organizationalInsights}
            isLoading={isLoading}
            error={error}
            onRefresh={refetch}
          />
        </TabsContent>

        <TabsContent value="positions" className="mt-6">
          <PositionScarcity
            scarcityData={positionScarcity}
            isLoading={isLoading}
            error={error}
            onRefresh={refetch}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
