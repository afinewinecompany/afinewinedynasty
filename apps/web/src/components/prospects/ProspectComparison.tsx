'use client';

import { useState, useCallback } from 'react';
import {
  DragDropContext,
  Droppable,
  Draggable,
  DropResult,
} from 'react-beautiful-dnd';
import { Plus, X, BarChart3, FileDown, Share2 } from 'lucide-react';
import ProspectSelector from './ProspectSelector';
import ComparisonTable from './ComparisonTable';
import ComparisonExport from '../ui/ComparisonExport';
import ScoutingRadarComparison from './ScoutingRadarComparison';
import { useProspectComparison } from '@/hooks/useProspectComparison';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Brain } from 'lucide-react';

interface SelectedProspect {
  id: number;
  name: string;
  position: string;
  organization: string;
  level: string;
  age: number;
  eta_year: number;
}

const MAX_PROSPECTS = 4;
const MIN_PROSPECTS = 2;

// Generate AI-like analysis summary based on comparison data
function generateAIAnalysis(
  prospects: SelectedProspect[],
  comparisonData: any
): string {
  if (prospects.length < 2) return '';

  const [p1, p2] = prospects;
  const comparison = comparisonData?.prospects || [];

  // Simple analysis based on available data
  const p1Data = comparison.find((p: any) => p.id === p1.id);
  const p2Data = comparison.find((p: any) => p.id === p2.id);

  if (!p1Data || !p2Data) {
    return 'Analyzing prospects...';
  }

  const analyses: string[] = [];

  // Compare ML predictions if available
  if (p1Data.ml_prediction && p2Data.ml_prediction) {
    const p1Prob = p1Data.ml_prediction.success_probability * 100;
    const p2Prob = p2Data.ml_prediction.success_probability * 100;

    if (p1Prob > p2Prob) {
      analyses.push(
        `${p1.name} shows stronger ML projection (${p1Prob.toFixed(0)}% vs ${p2Prob.toFixed(0)}%)`
      );
    } else {
      analyses.push(
        `${p2.name} leads in ML success probability (${p2Prob.toFixed(0)}% vs ${p1Prob.toFixed(0)}%)`
      );
    }
  }

  // Compare ETA
  if (p1.eta_year && p2.eta_year) {
    if (p1.eta_year < p2.eta_year) {
      analyses.push(`${p1.name} offers earlier impact potential (${p1.eta_year} ETA)`);
    } else if (p2.eta_year < p1.eta_year) {
      analyses.push(`${p2.name} projects for earlier arrival (${p2.eta_year} ETA)`);
    }
  }

  // Add position context
  if (p1.position !== p2.position) {
    analyses.push(
      `Positional versatility consideration: ${p1.name} (${p1.position}) vs ${p2.name} (${p2.position})`
    );
  }

  // Dynasty recommendation
  const recommendation = p1Data.dynasty_score > p2Data.dynasty_score
    ? `For dynasty leagues prioritizing immediate impact and ceiling, ${p1.name} edges ahead. However, ${p2.name} provides compelling value as a strong floor play with developmental upside.`
    : `${p2.name} presents superior dynasty value with a balanced skill set. ${p1.name} remains a viable alternative for teams seeking ${p1.position} depth.`;

  return [...analyses, recommendation].join('. ');
}

export default function ProspectComparison() {
  const [selectedProspects, setSelectedProspects] = useState<
    SelectedProspect[]
  >([]);
  const [showSelector, setShowSelector] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [compareUrl, setCompareUrl] = useState('');

  const { comparisonData, isLoading, error, fetchComparison } =
    useProspectComparison();

  const handleProspectAdd = useCallback(
    (prospect: SelectedProspect) => {
      if (selectedProspects.length < MAX_PROSPECTS) {
        setSelectedProspects((prev) => [...prev, prospect]);
        setShowSelector(false);

        // If we have at least 2 prospects, fetch comparison
        if (selectedProspects.length >= 1) {
          const prospectIds = [...selectedProspects, prospect].map((p) => p.id);
          fetchComparison(prospectIds);

          // Generate shareable URL
          const url = `${window.location.origin}/compare?ids=${prospectIds.join(',')}`;
          setCompareUrl(url);
        }
      }
    },
    [selectedProspects, fetchComparison]
  );

  const handleProspectRemove = useCallback(
    (prospectId: number) => {
      const newProspects = selectedProspects.filter((p) => p.id !== prospectId);
      setSelectedProspects(newProspects);

      // Update comparison if we still have enough prospects
      if (newProspects.length >= MIN_PROSPECTS) {
        const prospectIds = newProspects.map((p) => p.id);
        fetchComparison(prospectIds);

        const url = `${window.location.origin}/compare?ids=${prospectIds.join(',')}`;
        setCompareUrl(url);
      } else {
        setCompareUrl('');
      }
    },
    [selectedProspects, fetchComparison]
  );

  const handleDragEnd = useCallback(
    (result: DropResult) => {
      if (!result.destination) return;

      const items = Array.from(selectedProspects);
      const [reorderedItem] = items.splice(result.source.index, 1);
      items.splice(result.destination.index, 0, reorderedItem);

      setSelectedProspects(items);
    },
    [selectedProspects]
  );

  const canAddProspect = selectedProspects.length < MAX_PROSPECTS;
  const canCompare = selectedProspects.length >= MIN_PROSPECTS;

  const handleShare = async () => {
    if (compareUrl) {
      try {
        await navigator.clipboard.writeText(compareUrl);
        // You could add a toast notification here
        alert('Comparison URL copied to clipboard!');
      } catch (err) {
        console.error('Failed to copy URL:', err);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Selected Prospects ({selectedProspects.length}/{MAX_PROSPECTS})
          </h2>
          <div className="flex items-center gap-3">
            {canCompare && (
              <>
                <button
                  onClick={() => setShowExport(true)}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  <FileDown className="w-4 h-4" />
                  Export
                </button>
                <button
                  onClick={handleShare}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  <Share2 className="w-4 h-4" />
                  Share
                </button>
              </>
            )}
            {canAddProspect && (
              <button
                onClick={() => setShowSelector(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Prospect
              </button>
            )}
          </div>
        </div>

        {/* Prospect Slots */}
        <DragDropContext onDragEnd={handleDragEnd}>
          <Droppable droppableId="prospects" direction="horizontal">
            {(provided) => (
              <div
                {...provided.droppableProps}
                ref={provided.innerRef}
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
              >
                {selectedProspects.map((prospect, index) => (
                  <Draggable
                    key={prospect.id}
                    draggableId={prospect.id.toString()}
                    index={index}
                  >
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                        className={`relative p-4 bg-blue-50 border-2 border-blue-200 rounded-lg transition-shadow ${
                          snapshot.isDragging ? 'shadow-lg' : ''
                        }`}
                      >
                        <button
                          onClick={() => handleProspectRemove(prospect.id)}
                          className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>

                        <div className="space-y-2">
                          <h3 className="font-semibold text-gray-900 text-sm">
                            {prospect.name}
                          </h3>
                          <div className="text-xs text-gray-600 space-y-1">
                            <div>
                              {prospect.position} • {prospect.organization}
                            </div>
                            <div>
                              {prospect.level} • Age {prospect.age}
                            </div>
                            <div>ETA: {prospect.eta_year || 'TBD'}</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </Draggable>
                ))}

                {/* Empty slots */}
                {Array.from({
                  length: MAX_PROSPECTS - selectedProspects.length,
                }).map((_, index) => (
                  <div
                    key={`empty-${index}`}
                    className="p-4 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center min-h-[120px]"
                  >
                    {index === 0 && selectedProspects.length === 0 ? (
                      <div className="text-center">
                        <BarChart3 className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">
                          Add prospects to compare
                        </p>
                      </div>
                    ) : (
                      <div className="text-center">
                        <div className="w-8 h-8 bg-gray-200 rounded-full mx-auto mb-2" />
                        <p className="text-xs text-gray-400">Empty slot</p>
                      </div>
                    )}
                  </div>
                ))}

                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>

        {/* Helper Text */}
        <div className="mt-4 text-sm text-gray-500">
          {selectedProspects.length === 0 && (
            <p>
              Add 2-4 prospects to start comparing. Drag to reorder comparison
              slots.
            </p>
          )}
          {selectedProspects.length === 1 && (
            <p>Add at least one more prospect to enable comparison.</p>
          )}
          {selectedProspects.length >= MIN_PROSPECTS && (
            <p>
              Comparison active! Add up to{' '}
              {MAX_PROSPECTS - selectedProspects.length} more prospects or
              remove prospects to adjust the comparison.
            </p>
          )}
        </div>
      </div>

      {/* Comparison Results */}
      {canCompare && (
        <>
          {/* Comparison Table */}
          <div className="bg-white rounded-lg shadow-sm border">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
                <p className="text-gray-600">Loading comparison data...</p>
              </div>
            ) : error ? (
              <div className="p-8 text-center">
                <div className="text-red-500 mb-2">⚠️</div>
                <p className="text-red-600 font-medium">
                  Failed to load comparison
                </p>
                <p className="text-sm text-gray-500 mt-1">{error}</p>
              </div>
            ) : comparisonData ? (
              <ComparisonTable
                comparisonData={comparisonData}
                selectedProspects={selectedProspects}
              />
            ) : null}
          </div>

          {/* Scouting Radar Comparison */}
          {comparisonData && !isLoading && !error && (
            <div className="bg-white rounded-lg shadow-sm border">
              <ScoutingRadarComparison
                comparisonData={comparisonData}
                selectedProspects={selectedProspects}
              />
            </div>
          )}

          {/* AI Analysis Summary */}
          {comparisonData && !isLoading && !error && selectedProspects.length >= 2 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-purple-600" />
                  AI Analysis Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-6">
                  <p className="text-gray-800 leading-relaxed italic">
                    &ldquo;{generateAIAnalysis(selectedProspects, comparisonData)}&rdquo;
                  </p>
                  <div className="mt-4 text-xs text-gray-500">
                    Generated by AI-powered dynasty analysis engine
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Prospect Selector Modal */}
      {showSelector && (
        <ProspectSelector
          onSelect={handleProspectAdd}
          onClose={() => setShowSelector(false)}
          excludeIds={selectedProspects.map((p) => p.id)}
        />
      )}

      {/* Export Modal */}
      {showExport && comparisonData && (
        <ComparisonExport
          comparisonData={comparisonData}
          selectedProspects={selectedProspects}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}
