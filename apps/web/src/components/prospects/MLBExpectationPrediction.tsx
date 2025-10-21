'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  TrendingUp,
  Award,
  Users,
  AlertCircle,
  Info,
} from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api/client';

interface MLBExpectationPrediction {
  prospect_id: number;
  name: string;
  position: string;
  player_type: 'hitter' | 'pitcher';
  year: number;
  prediction: {
    class: number;
    label: string;
    probabilities: {
      'Bench/Reserve': number;
      'Part-Time': number;
      'MLB Regular+': number;
    };
  };
  timestamp: string;
}

interface MLBExpectationPredictionProps {
  prospectId: number;
  year?: number;
  className?: string;
}

const CLASS_COLORS = {
  'Bench/Reserve': {
    bg: 'bg-gray-100',
    border: 'border-gray-300',
    text: 'text-gray-700',
    badge: 'bg-gray-500',
    icon: Users,
  },
  'Part-Time': {
    bg: 'bg-yellow-50',
    border: 'border-yellow-300',
    text: 'text-yellow-700',
    badge: 'bg-yellow-500',
    icon: TrendingUp,
  },
  'MLB Regular+': {
    bg: 'bg-green-50',
    border: 'border-green-300',
    text: 'text-green-700',
    badge: 'bg-green-500',
    icon: Award,
  },
};

const CLASS_DESCRIPTIONS = {
  'Bench/Reserve': 'Projects to MLB bench role or limited playing time. FV 35-40.',
  'Part-Time': 'Projects to platoon or part-time role. Useful depth piece. FV 45.',
  'MLB Regular+': 'Projects to regular starter or better. Core organizational piece. FV 50+.',
};

export function MLBExpectationPrediction({
  prospectId,
  year = new Date().getFullYear(),
  className = ''
}: MLBExpectationPredictionProps) {
  const [prediction, setPrediction] = useState<MLBExpectationPrediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchPrediction() {
      try {
        setLoading(true);
        setError(null);

        const data = await apiClient.get<{ success: boolean; data?: MLBExpectationPrediction; error?: string }>(
          `/prospects/${prospectId}/mlb-expectation?year=${year}`
        );

        if (data.success && data.data) {
          setPrediction(data.data);
        } else {
          setError(data.error || 'Unknown error');
        }
      } catch (err) {
        console.error('MLB Expectation prediction error:', err);
        setError(err instanceof Error ? err.message : 'Failed to load prediction');
      } finally {
        setLoading(false);
      }
    }

    if (prospectId) {
      fetchPrediction();
    }
  }, [prospectId, year]);

  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Award className="h-5 w-5" />
            MLB Expectation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Award className="h-5 w-5" />
            MLB Expectation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-amber-600">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!prediction) {
    return null;
  }

  const { prediction: pred } = prediction;
  const colorScheme = CLASS_COLORS[pred.label as keyof typeof CLASS_COLORS];
  const Icon = colorScheme.icon;
  const confidence = Math.max(...Object.values(pred.probabilities));

  // Sort probabilities by value (descending)
  const sortedProbs = Object.entries(pred.probabilities)
    .sort(([, a], [, b]) => b - a)
    .map(([label, prob]) => ({ label, prob }));

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Award className="h-5 w-5" />
          MLB Expectation
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger>
                <Info className="h-4 w-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p className="text-sm">
                  Machine learning prediction of MLB career outcome using Fangraphs grades
                  and MiLB performance data. Based on {prediction.player_type} model.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Main Prediction */}
        <div className={`p-4 rounded-lg border-2 ${colorScheme.bg} ${colorScheme.border}`}>
          <div className="flex items-center gap-3 mb-2">
            <Icon className={`h-6 w-6 ${colorScheme.text}`} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className={`text-2xl font-bold ${colorScheme.text}`}>
                  {pred.label}
                </h3>
                <Badge className={colorScheme.badge}>
                  {(confidence * 100).toFixed(0)}% confident
                </Badge>
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <p className="text-sm text-muted-foreground mt-1 cursor-help">
                      {CLASS_DESCRIPTIONS[pred.label as keyof typeof CLASS_DESCRIPTIONS]}
                    </p>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="text-xs">
                      FV (Future Value) is Fangraphs' 20-80 scouting scale where 50 is average MLB regular
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>

        {/* Probability Breakdown */}
        <div>
          <h4 className="text-sm font-medium mb-3">Probability Breakdown</h4>
          <div className="space-y-3">
            {sortedProbs.map(({ label, prob }) => {
              const colors = CLASS_COLORS[label as keyof typeof CLASS_COLORS];
              return (
                <div key={label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{label}</span>
                    <span className="text-muted-foreground">
                      {(prob * 100).toFixed(1)}%
                    </span>
                  </div>
                  <Progress
                    value={prob * 100}
                    className="h-2"
                    indicatorClassName={colors.badge}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Model Info */}
        <div className="pt-4 border-t">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="capitalize">{prediction.player_type} Model</span>
              <span>•</span>
              <span>XGBoost 3-Class</span>
            </div>
            <span>
              Predicted {new Date(prediction.timestamp).toLocaleDateString()}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default MLBExpectationPrediction;
