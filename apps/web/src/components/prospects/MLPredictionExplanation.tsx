'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Info,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Brain,
  ChevronDown,
  ChevronUp,
  AlertCircle
} from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface SHAPFeature {
  feature: string;
  shap_value: number;
  feature_value?: number;
  feature_display?: string;
}

interface MLPredictionData {
  success_probability: number;
  confidence_level: 'High' | 'Medium' | 'Low';
  prediction_date: string;
  shap_explanation: {
    top_positive_features: SHAPFeature[];
    top_negative_features: SHAPFeature[];
    expected_value: number;
    prediction_score: number;
    total_shap_contribution: number;
  };
  narrative: string;
  model_version: string;
}

interface MLPredictionExplanationProps {
  prediction: MLPredictionData;
  prospectName: string;
  className?: string;
}

export function MLPredictionExplanation({
  prediction,
  prospectName,
  className = ''
}: MLPredictionExplanationProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case 'High':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'Medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'Low':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getProbabilityColor = (probability: number) => {
    if (probability >= 0.7) return 'text-green-600';
    if (probability >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const formatFeatureName = (feature: string) => {
    return feature
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatFeatureValue = (value: number, feature: string) => {
    // Format based on feature type
    if (feature.includes('avg') || feature.includes('percentage')) {
      return value.toFixed(3);
    }
    if (feature.includes('age')) {
      return Math.round(value).toString();
    }
    return value.toFixed(2);
  };

  const SHAPFeatureItem = ({
    feature,
    isPositive
  }: {
    feature: SHAPFeature;
    isPositive: boolean
  }) => {
    const maxAbsValue = Math.max(
      ...prediction.shap_explanation.top_positive_features.map(f => Math.abs(f.shap_value)),
      ...prediction.shap_explanation.top_negative_features.map(f => Math.abs(f.shap_value))
    );

    const barWidth = (Math.abs(feature.shap_value) / maxAbsValue) * 100;

    return (
      <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-gray-900">
              {formatFeatureName(feature.feature)}
            </span>
            <div className="flex items-center space-x-2">
              {feature.feature_value !== undefined && (
                <span className="text-xs text-gray-500">
                  Value: {formatFeatureValue(feature.feature_value, feature.feature)}
                </span>
              )}
              <span className={`text-sm font-semibold ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                {isPositive ? '+' : ''}{feature.shap_value.toFixed(3)}
              </span>
            </div>
          </div>
          <div className="relative h-2 bg-gray-200 rounded-full">
            <div
              className={`absolute h-full rounded-full ${
                isPositive ? 'bg-green-500' : 'bg-red-500'
              }`}
              style={{ width: `${barWidth}%` }}
            />
          </div>
        </div>
      </div>
    );
  };

  return (
    <Card className={`w-full ${className}`}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <Brain className="h-5 w-5 text-blue-600" />
            <span>ML Prediction Analysis</span>
          </CardTitle>
          <Badge className={getConfidenceColor(prediction.confidence_level)}>
            {prediction.confidence_level} Confidence
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Main Prediction Display */}
        <div className="text-center space-y-4">
          <div className="space-y-2">
            <div className={`text-4xl font-bold ${getProbabilityColor(prediction.success_probability)}`}>
              {(prediction.success_probability * 100).toFixed(1)}%
            </div>
            <p className="text-gray-600">
              Probability of MLB Success
            </p>
          </div>

          <Progress
            value={prediction.success_probability * 100}
            className="w-full h-3"
          />

          <p className="text-sm text-gray-500">
            Prediction generated on {new Date(prediction.prediction_date).toLocaleDateString()}
          </p>
        </div>

        {/* Narrative Summary */}
        {prediction.narrative && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start space-x-2">
              <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div>
                <h4 className="font-semibold text-blue-900 mb-2">AI Analysis Summary</h4>
                <p className="text-blue-800 text-sm leading-relaxed">
                  {prediction.narrative}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* SHAP Explanation Toggle */}
        <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" className="w-full justify-between">
              <span className="flex items-center space-x-2">
                <BarChart3 className="h-4 w-4" />
                <span>View Detailed Feature Analysis</span>
              </span>
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>

          <CollapsibleContent className="space-y-4 mt-4">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="positive">Positive Factors</TabsTrigger>
                <TabsTrigger value="negative">Risk Factors</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-lg font-semibold text-gray-900">
                      {prediction.shap_explanation.expected_value.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">Base Prediction</div>
                  </div>
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-lg font-semibold text-gray-900">
                      {prediction.shap_explanation.total_shap_contribution.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">Feature Impact</div>
                  </div>
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-lg font-semibold text-gray-900">
                      {prediction.shap_explanation.prediction_score.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-600">Final Score</div>
                  </div>
                </div>

                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <div className="flex items-start space-x-2">
                    <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="font-semibold text-yellow-900 mb-1">How to Read This Analysis</h4>
                      <p className="text-yellow-800 text-sm">
                        The model starts with a base prediction, then adjusts up or down based on {prospectName}'s
                        specific features. Green bars show factors that increase success probability, while red bars
                        show factors that decrease it. The length of each bar represents the magnitude of impact.
                      </p>
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="positive" className="space-y-3">
                <div className="flex items-center space-x-2 mb-4">
                  <TrendingUp className="h-5 w-5 text-green-600" />
                  <h3 className="font-semibold text-green-900">
                    Positive Contributing Factors ({prediction.shap_explanation.top_positive_features.length})
                  </h3>
                </div>
                {prediction.shap_explanation.top_positive_features.length > 0 ? (
                  <div className="space-y-2">
                    {prediction.shap_explanation.top_positive_features.map((feature, index) => (
                      <SHAPFeatureItem
                        key={`positive-${index}`}
                        feature={feature}
                        isPositive={true}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">No significant positive contributing factors identified.</p>
                )}
              </TabsContent>

              <TabsContent value="negative" className="space-y-3">
                <div className="flex items-center space-x-2 mb-4">
                  <TrendingDown className="h-5 w-5 text-red-600" />
                  <h3 className="font-semibold text-red-900">
                    Risk Factors ({prediction.shap_explanation.top_negative_features.length})
                  </h3>
                </div>
                {prediction.shap_explanation.top_negative_features.length > 0 ? (
                  <div className="space-y-2">
                    {prediction.shap_explanation.top_negative_features.map((feature, index) => (
                      <SHAPFeatureItem
                        key={`negative-${index}`}
                        feature={feature}
                        isPositive={false}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-sm">No significant risk factors identified.</p>
                )}
              </TabsContent>
            </Tabs>

            {/* Model Information */}
            <div className="pt-4 border-t border-gray-200">
              <p className="text-xs text-gray-500">
                Model Version: {prediction.model_version} |
                Analysis uses SHAP (SHapley Additive exPlanations) for feature importance
              </p>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}