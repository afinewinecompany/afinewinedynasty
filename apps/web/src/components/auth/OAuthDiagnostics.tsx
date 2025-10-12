/**
 * OAuth Diagnostics Component
 *
 * Displays environment variable status for debugging OAuth issues.
 * Only shows in development mode.
 */

'use client';

import React, { useState } from 'react';

export default function OAuthDiagnostics() {
  const [isExpanded, setIsExpanded] = useState(false);

  // Only show in development
  if (process.env.NODE_ENV === 'production') {
    return null;
  }

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="bg-blue-600 text-white px-4 py-2 rounded-md shadow-lg hover:bg-blue-700 transition-colors text-sm font-medium"
      >
        {isExpanded ? '✖ Close' : '🔧 OAuth Debug'}
      </button>

      {isExpanded && (
        <div className="absolute bottom-12 right-0 bg-white border border-gray-300 rounded-lg shadow-2xl p-4 w-96 max-h-96 overflow-y-auto">
          <h3 className="font-bold text-gray-900 mb-3 text-lg">OAuth Configuration Status</h3>

          <div className="space-y-3">
            {/* Google Client ID */}
            <div className="border-b border-gray-200 pb-2">
              <div className="flex items-center gap-2 mb-1">
                {clientId ? (
                  <span className="text-green-600 text-xl">✅</span>
                ) : (
                  <span className="text-red-600 text-xl">❌</span>
                )}
                <span className="font-semibold text-gray-700">NEXT_PUBLIC_GOOGLE_CLIENT_ID</span>
              </div>
              {clientId ? (
                <div className="text-xs text-gray-600 font-mono bg-gray-50 p-2 rounded">
                  {clientId.substring(0, 20)}...
                </div>
              ) : (
                <div className="text-xs text-red-600 bg-red-50 p-2 rounded">
                  Not set! Add to .env.local and restart dev server
                </div>
              )}
            </div>

            {/* API URL */}
            <div className="border-b border-gray-200 pb-2">
              <div className="flex items-center gap-2 mb-1">
                {apiUrl ? (
                  <span className="text-green-600 text-xl">✅</span>
                ) : (
                  <span className="text-yellow-600 text-xl">⚠️</span>
                )}
                <span className="font-semibold text-gray-700">NEXT_PUBLIC_API_URL</span>
              </div>
              <div className="text-xs text-gray-600 font-mono bg-gray-50 p-2 rounded">
                {apiUrl || 'Using default: http://localhost:8000'}
              </div>
            </div>

            {/* Dev Server Status */}
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <p className="text-xs text-blue-800 font-semibold mb-1">💡 Important:</p>
              <p className="text-xs text-blue-700">
                If you just added environment variables, you MUST restart your dev server:
              </p>
              <code className="text-xs bg-blue-100 text-blue-900 px-2 py-1 rounded block mt-2">
                Ctrl+C → npm run dev
              </code>
            </div>

            {/* Quick Actions */}
            <div className="space-y-2 pt-2">
              <button
                onClick={() => {
                  console.log('=== OAuth Environment Variables ===');
                  console.log('NEXT_PUBLIC_GOOGLE_CLIENT_ID:', clientId || 'NOT SET');
                  console.log('NEXT_PUBLIC_API_URL:', apiUrl || 'NOT SET (using default)');
                  console.log('NODE_ENV:', process.env.NODE_ENV);
                }}
                className="w-full bg-gray-700 text-white px-3 py-2 rounded text-xs hover:bg-gray-800 transition-colors"
              >
                📋 Log to Console
              </button>

              <a
                href="/OAUTH_SETUP.md"
                target="_blank"
                className="block w-full bg-green-600 text-white px-3 py-2 rounded text-xs text-center hover:bg-green-700 transition-colors"
              >
                📖 View Setup Guide
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
