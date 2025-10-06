'use client';

export default function TestEnvPage() {
  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Environment Variable Test</h1>

      <div className="space-y-4">
        <div className="border p-4 rounded">
          <h2 className="font-semibold mb-2">NEXT_PUBLIC_GOOGLE_CLIENT_ID</h2>
          <p className="text-sm font-mono bg-gray-100 p-2 rounded break-all">
            {process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '❌ NOT SET'}
          </p>
        </div>

        <div className="border p-4 rounded">
          <h2 className="font-semibold mb-2">NEXT_PUBLIC_API_URL</h2>
          <p className="text-sm font-mono bg-gray-100 p-2 rounded break-all">
            {process.env.NEXT_PUBLIC_API_URL || '❌ NOT SET'}
          </p>
        </div>

        <div className="border p-4 rounded">
          <h2 className="font-semibold mb-2">NODE_ENV</h2>
          <p className="text-sm font-mono bg-gray-100 p-2 rounded">
            {process.env.NODE_ENV}
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 p-4 rounded">
          <p className="text-sm font-semibold mb-2">Instructions:</p>
          <ol className="list-decimal list-inside text-sm space-y-1">
            <li>If you see "❌ NOT SET", the env var is not loaded</li>
            <li>Stop your dev server (Ctrl+C)</li>
            <li>Run: <code className="bg-blue-100 px-1">npm run dev</code></li>
            <li>Refresh this page</li>
          </ol>
        </div>

        <button
          onClick={() => {
            console.log('=== Environment Variables ===');
            console.log('NEXT_PUBLIC_GOOGLE_CLIENT_ID:', process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID);
            console.log('NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL);
            console.log('NODE_ENV:', process.env.NODE_ENV);
            alert('Check browser console for environment variables');
          }}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
        >
          Log to Console
        </button>
      </div>
    </div>
  );
}
