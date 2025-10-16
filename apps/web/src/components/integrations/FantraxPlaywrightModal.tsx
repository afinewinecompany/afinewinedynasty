/**
 * Fantrax Authentication Modal
 *
 * Simple, reliable cookie-based authentication.
 * Users log in to Fantrax, then paste their cookies.
 *
 * @component FantraxPlaywrightModal
 * @since 1.4.0
 */

'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Info,
  Copy
} from 'lucide-react';

interface FantraxPlaywrightModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type AuthState = 'instructions' | 'waiting-for-paste' | 'processing' | 'success' | 'failed';

const FANTRAX_URL = 'https://www.fantrax.com';

export function FantraxPlaywrightModal({
  isOpen,
  onClose,
  onSuccess,
}: FantraxPlaywrightModalProps): JSX.Element {
  const [state, setState] = useState<AuthState>('instructions');
  const [error, setError] = useState<string | null>(null);
  const [cookiesInput, setCookiesInput] = useState('');

  const getApiUrl = () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const getAuthToken = () => localStorage.getItem('access_token');

  /**
   * Open Fantrax in new tab
   */
  const openFantrax = () => {
    window.open(FANTRAX_URL, '_blank');
    setState('waiting-for-paste');
  };

  /**
   * Submit cookies to backend
   */
  const submitCookies = async () => {
    if (!cookiesInput.trim()) {
      setError('Please paste your cookies');
      return;
    }

    const token = getAuthToken();
    if (!token) {
      setError('Not authenticated. Please log in again.');
      setState('failed');
      return;
    }

    setState('processing');

    try {
      const response = await fetch(`${getApiUrl()}/api/v1/fantrax/auth/cookie-auth`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          cookies_json: cookiesInput.trim()
        }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setState('success');
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 1500);
      } else {
        setError(data.detail || 'Failed to save session');
        setState('failed');
      }
    } catch (err: any) {
      console.error('Failed to authenticate:', err);
      setError(err.message || 'Failed to connect');
      setState('failed');
    }
  };

  /**
   * Close and reset
   */
  const handleClose = () => {
    setState('instructions');
    setError(null);
    setCookiesInput('');
    onClose();
  };

  /**
   * Get the bookmarklet code
   */
  const getBookmarkletCode = () => {
    return `javascript:(function(){const c=document.cookie.split(';').map(c=>{const[n,...v]=c.trim().split('=');return{name:n.trim(),value:v.join('='),domain:'.fantrax.com',path:'/',secure:true,sameSite:'Lax'}}).filter(c=>c.name&&c.value);navigator.clipboard.writeText(JSON.stringify(c,null,2)).then(()=>alert('Cookies copied! Go back and paste them.')).catch(()=>alert('Please manually copy: '+JSON.stringify(c)))})();`;
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Connect to Fantrax</DialogTitle>
          <DialogDescription>
            Quick 2-step process to connect your account
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {state === 'success' ? (
            <div className="py-6 flex flex-col items-center gap-4">
              <CheckCircle2 className="h-16 w-16 text-green-600" />
              <div className="text-center">
                <p className="font-semibold text-lg">Successfully Connected!</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Loading your Fantrax leagues...
                </p>
              </div>
            </div>
          ) : state === 'failed' ? (
            <div className="py-6 flex flex-col items-center gap-4">
              <AlertCircle className="h-16 w-16 text-red-600" />
              <div className="text-center space-y-3 w-full">
                <p className="font-semibold text-lg">Authentication Failed</p>
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
                <Button onClick={() => { setState('instructions'); setError(null); }} className="w-full">
                  Try Again
                </Button>
              </div>
            </div>
          ) : state === 'processing' ? (
            <div className="py-6 flex flex-col items-center gap-4">
              <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
              <p className="font-medium">Connecting your account...</p>
            </div>
          ) : state === 'waiting-for-paste' ? (
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-2">After logging in to Fantrax:</p>
                  <ol className="text-sm space-y-2 list-decimal list-inside">
                    <li>
                      <strong>Option A (Easiest):</strong> Drag this button to your bookmarks bar, then click it on Fantrax:
                      <div className="mt-2">
                        <a
                          href={getBookmarkletCode()}
                          className="inline-block px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 cursor-move"
                          onClick={(e) => e.preventDefault()}
                        >
                          Copy Fantrax Cookies
                        </a>
                        <p className="text-xs text-muted-foreground mt-1">
                          ↑ Drag this to your bookmarks bar
                        </p>
                      </div>
                    </li>
                    <li className="mt-3">
                      <strong>Option B:</strong> Press F12 → Console tab → Paste this:
                      <code className="block mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                        {`copy(JSON.stringify(document.cookie.split(';').map(c=>{const[n,...v]=c.trim().split('=');return{name:n.trim(),value:v.join('='),domain:'.fantrax.com',path:'/',secure:true,sameSite:'Lax'}})))`}
                      </code>
                      <p className="text-xs text-muted-foreground mt-1">
                        Then press Enter. Your cookies will be copied.
                      </p>
                    </li>
                  </ol>
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <label className="text-sm font-medium">Paste your cookies here:</label>
                <textarea
                  value={cookiesInput}
                  onChange={(e) => setCookiesInput(e.target.value)}
                  placeholder='Paste the JSON here (starts with [{"name":...)'
                  className="w-full h-32 px-3 py-2 border rounded-md text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex gap-2">
                <Button onClick={submitCookies} className="flex-1" disabled={!cookiesInput.trim()}>
                  Connect Account
                </Button>
                <Button onClick={handleClose} variant="outline" className="flex-1">
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-2">Quick 2-step process:</p>
                  <ol className="text-sm space-y-1.5 list-decimal list-inside">
                    <li>Click below to open Fantrax and log in</li>
                    <li>Copy your cookies using our one-click tool</li>
                  </ol>
                  <p className="text-xs text-muted-foreground mt-2">
                    Takes less than 30 seconds • No extensions needed
                  </p>
                </AlertDescription>
              </Alert>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="text-xs text-blue-900">
                    <p className="font-semibold mb-1">Your credentials are secure</p>
                    <ul className="space-y-0.5 list-disc list-inside text-blue-800">
                      <li>Login happens in your browser</li>
                      <li>Only session cookies are captured (never passwords)</li>
                      <li>Cookies are encrypted before storage (AES-256)</li>
                      <li>You can review everything before submitting</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button onClick={openFantrax} className="w-full" size="lg">
                <ExternalLink className="mr-2 h-4 w-4" />
                Open Fantrax & Log In
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
