'use client';

import { useState, useEffect } from 'react';
import { useProspectOutlook } from '@/hooks/useProspectOutlook';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import ErrorMessage from '@/components/ui/ErrorMessage';

interface ProspectOutlookProps {
  prospectId: string;
  compact?: boolean;
}

interface QualityMetrics {
  quality_score: number;
  readability_score: number;
  coherence_score: number;
  sentence_count: number;
  word_count: number;
}

interface OutlookData {
  narrative: string;
  quality_metrics: QualityMetrics;
  generated_at: string;
  template_version: string;
  model_version: string;
  risk_level: string;
  timeline: string;
}

function QualityIndicator({ score, label }: { score: number; label: string }) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-100';
    if (score >= 60) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getScoreIcon = (score: number) => {
    if (score >= 80) return '●';
    if (score >= 60) return '●';
    return '●';
  };

  return (
    <div className="flex items-center space-x-1">
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getScoreColor(score)}`}>
        {getScoreIcon(score)} {score.toFixed(0)}
      </span>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  );
}

function OutlookMetrics({ metrics }: { metrics: QualityMetrics }) {
  return (
    <div className="mt-3 p-3 bg-gray-50 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-700">Quality Metrics</span>
        <button className="text-xs text-blue-600 hover:text-blue-700">
          Details
        </button>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <QualityIndicator score={metrics.quality_score} label="Overall" />
        <QualityIndicator score={metrics.readability_score} label="Clarity" />
        <QualityIndicator score={metrics.coherence_score} label="Flow" />
      </div>
      <div className="mt-2 text-xs text-gray-500">
        {metrics.sentence_count} sentences • {metrics.word_count} words
      </div>
    </div>
  );
}

function OutlookControls({
  onRefresh,
  onFeedback,
  isLoading
}: {
  onRefresh: () => void;
  onFeedback: (helpful: boolean) => void;
  isLoading: boolean;
}) {
  return (
    <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-200">
      <div className="flex items-center space-x-4">
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50 flex items-center space-x-1"
        >
          {isLoading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          <span>Refresh</span>
        </button>
      </div>

      <div className="flex items-center space-x-2">
        <span className="text-xs text-gray-500">Helpful?</span>
        <button
          onClick={() => onFeedback(true)}
          className="text-sm text-gray-400 hover:text-green-600 transition-colors"
          title="Mark as helpful"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L9 7v3m-3 10h3m-3 0h3" />
          </svg>
        </button>
        <button
          onClick={() => onFeedback(false)}
          className="text-sm text-gray-400 hover:text-red-600 transition-colors"
          title="Mark as not helpful"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L15 17v-3m-6-10h3m6 0h-3" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function ProspectOutlook({ prospectId, compact = false }: ProspectOutlookProps) {
  const { data: outlook, loading, error, refetch } = useProspectOutlook(prospectId);
  const [showMetrics, setShowMetrics] = useState(false);

  const handleFeedback = async (helpful: boolean) => {
    try {
      // Call feedback API
      await fetch(`/api/ml/outlook/${prospectId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ helpful, timestamp: new Date().toISOString() })
      });
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  if (loading) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-white ${compact ? 'p-4' : 'p-6'}`}>
        <div className="flex items-center space-x-2 mb-3">
          <div className="flex items-center space-x-2">
            <svg className="h-5 w-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <h3 className={`font-medium text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
              AI Outlook
            </h3>
          </div>
          <LoadingSpinner size="sm" />
        </div>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-5/6 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-4/6"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-white ${compact ? 'p-4' : 'p-6'}`}>
        <div className="flex items-center space-x-2 mb-3">
          <svg className="h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L5.268 19.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <h3 className={`font-medium text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
            AI Outlook
          </h3>
        </div>
        <ErrorMessage
          message="Failed to generate prospect outlook"
          onRetry={refetch}
          compact={compact}
        />
      </div>
    );
  }

  if (!outlook) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-white ${compact ? 'p-4' : 'p-6'}`}>
        <div className="flex items-center space-x-2 mb-3">
          <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <h3 className={`font-medium text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
            AI Outlook
          </h3>
        </div>
        <p className="text-gray-500 text-sm">No outlook available for this prospect</p>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-gray-200 bg-white ${compact ? 'p-4' : 'p-6'}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <svg className="h-5 w-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <h3 className={`font-medium text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
            AI Outlook
          </h3>
        </div>

        {!compact && (
          <div className="flex items-center space-x-2">
            {outlook.risk_level && (
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                outlook.risk_level === 'Low' ? 'bg-green-100 text-green-800' :
                outlook.risk_level === 'Medium' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {outlook.risk_level} Risk
              </span>
            )}
            {outlook.timeline && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {outlook.timeline}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Narrative Content */}
      <div className={`prose prose-sm max-w-none ${compact ? 'text-sm' : ''}`}>
        <p className="text-gray-800 leading-relaxed">
          {outlook.narrative}
        </p>
      </div>

      {/* Quality Metrics (show on demand) */}
      {!compact && outlook.quality_metrics && (
        <div className="mt-4">
          <button
            onClick={() => setShowMetrics(!showMetrics)}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center space-x-1"
          >
            <span>Quality Score: {outlook.quality_metrics.quality_score.toFixed(0)}/100</span>
            <svg
              className={`h-3 w-3 transition-transform ${showMetrics ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {showMetrics && <OutlookMetrics metrics={outlook.quality_metrics} />}
        </div>
      )}

      {/* Controls and Metadata */}
      {!compact && (
        <>
          <OutlookControls
            onRefresh={refetch}
            onFeedback={handleFeedback}
            isLoading={loading}
          />

          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>
                Generated {new Date(outlook.generated_at).toLocaleDateString()} •
                Model {outlook.model_version}
              </span>
              <span>
                Template {outlook.template_version}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}