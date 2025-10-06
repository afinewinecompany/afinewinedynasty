'use client';

import React from 'react';
import { getGoogleAuthUrl } from '@/lib/auth';

interface GoogleSignInButtonProps {
  className?: string;
  children?: React.ReactNode;
}

export default function GoogleSignInButton({
  className = '',
  children
}: GoogleSignInButtonProps) {
  const handleSignIn = () => {
    const authUrl = getGoogleAuthUrl();
    window.location.href = authUrl;
  };

  return (
    <button
      onClick={handleSignIn}
      className={`
        flex items-center justify-center gap-3
        bg-white text-gray-700 font-medium
        px-6 py-3 rounded-lg
        border-2 border-gray-300
        hover:border-gray-400 hover:bg-gray-50
        transition-all duration-200
        shadow-sm hover:shadow-md
        ${className}
      `}
      type="button"
    >
      {/* Google Logo SVG */}
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M19.6 10.227c0-.709-.064-1.39-.182-2.045H10v3.868h5.382a4.6 4.6 0 01-1.996 3.018v2.51h3.232c1.891-1.742 2.982-4.305 2.982-7.35z"
          fill="#4285F4"
        />
        <path
          d="M10 20c2.7 0 4.964-.895 6.618-2.423l-3.232-2.509c-.895.6-2.04.955-3.386.955-2.605 0-4.81-1.76-5.595-4.123H1.064v2.59A9.996 9.996 0 0010 20z"
          fill="#34A853"
        />
        <path
          d="M4.405 11.9c-.2-.6-.314-1.24-.314-1.9 0-.66.114-1.3.314-1.9V5.51H1.064A9.996 9.996 0 000 10c0 1.614.386 3.14 1.064 4.49l3.34-2.59z"
          fill="#FBBC04"
        />
        <path
          d="M10 3.977c1.468 0 2.786.505 3.823 1.496l2.868-2.868C14.959.99 12.695 0 10 0 6.09 0 2.71 2.24 1.064 5.51l3.34 2.59C5.19 5.736 7.395 3.977 10 3.977z"
          fill="#EA4335"
        />
      </svg>

      <span>
        {children || 'Sign in with Google'}
      </span>
    </button>
  );
}
