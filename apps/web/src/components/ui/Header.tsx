import React from 'react';
import Link from 'next/link';

const Header: React.FC = () => {
  return (
    <header className="bg-blue-600 text-white shadow-lg">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold">
            A Fine Wine Dynasty
          </Link>
          <nav className="hidden md:flex space-x-6">
            <Link href="/prospects" className="hover:text-blue-200">
              Prospects
            </Link>
            <Link href="/analysis" className="hover:text-blue-200">
              Analysis
            </Link>
            <Link href="/dashboard" className="hover:text-blue-200">
              Dashboard
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header;
