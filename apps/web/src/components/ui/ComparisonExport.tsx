'use client';

import { useState } from 'react';
import { X, Download, FileText, Table, Share2, Link } from 'lucide-react';
import { useComparisonExport } from '@/hooks/useProspectComparison';

interface ComparisonExportProps {
  comparisonData: any;
  selectedProspects: any[];
  onClose: () => void;
}

export default function ComparisonExport({
  comparisonData,
  selectedProspects,
  onClose,
}: ComparisonExportProps) {
  const [selectedFormat, setSelectedFormat] = useState<'pdf' | 'csv'>('pdf');
  const [includeAnalytics, setIncludeAnalytics] = useState(true);
  const [includeCharts, setIncludeCharts] = useState(true);
  const [shareUrl, setShareUrl] = useState('');

  const { isExporting, error, exportComparison } = useComparisonExport();

  const handleExport = async () => {
    try {
      const prospectIds = selectedProspects.map((p) => p.id);
      const result = await exportComparison(prospectIds, selectedFormat);

      // Trigger download
      const link = document.createElement('a');
      link.href = result.downloadUrl;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      onClose();
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  const generateShareUrl = () => {
    const prospectIds = selectedProspects.map((p) => p.id);
    const url = `${window.location.origin}/compare?ids=${prospectIds.join(',')}`;
    setShareUrl(url);
  };

  const copyShareUrl = async () => {
    if (shareUrl) {
      try {
        await navigator.clipboard.writeText(shareUrl);
        alert('Share URL copied to clipboard!');
      } catch (err) {
        console.error('Failed to copy URL:', err);
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">
            Export Comparison
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Export Format Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Export Format
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setSelectedFormat('pdf')}
                className={`p-4 border-2 rounded-lg flex flex-col items-center gap-2 transition-colors ${
                  selectedFormat === 'pdf'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <FileText className="w-6 h-6" />
                <span className="text-sm font-medium">PDF Report</span>
                <span className="text-xs text-gray-500">
                  Comprehensive report with charts
                </span>
              </button>

              <button
                onClick={() => setSelectedFormat('csv')}
                className={`p-4 border-2 rounded-lg flex flex-col items-center gap-2 transition-colors ${
                  selectedFormat === 'csv'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Table className="w-6 h-6" />
                <span className="text-sm font-medium">CSV Data</span>
                <span className="text-xs text-gray-500">
                  Raw data for analysis
                </span>
              </button>
            </div>
          </div>

          {/* Export Options (for PDF) */}
          {selectedFormat === 'pdf' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Include Options
              </label>
              <div className="space-y-3">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={includeAnalytics}
                    onChange={(e) => setIncludeAnalytics(e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">
                    ML Analytics & Insights
                  </span>
                </label>

                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={includeCharts}
                    onChange={(e) => setIncludeCharts(e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="ml-2 text-sm text-gray-700">
                    Charts & Visualizations
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Preview Info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">
              Export Preview
            </h4>
            <div className="space-y-1 text-sm text-gray-600">
              <div>Prospects: {selectedProspects.length}</div>
              <div>
                Names: {selectedProspects.map((p) => p.name).join(', ')}
              </div>
              <div>
                Generated:{' '}
                {new Date(
                  comparisonData.comparison_metadata.generated_at
                ).toLocaleDateString()}
              </div>
            </div>
          </div>

          {/* Share URL Section */}
          <div className="border-t pt-6">
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-gray-700">
                Share Comparison
              </label>
              <button
                onClick={generateShareUrl}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Generate URL
              </button>
            </div>

            {shareUrl && (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md bg-gray-50"
                />
                <button
                  onClick={copyShareUrl}
                  className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  <Link className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Error Display */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center gap-3 pt-4">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-md transition-colors flex items-center justify-center gap-2"
            >
              {isExporting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Export {selectedFormat.toUpperCase()}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
