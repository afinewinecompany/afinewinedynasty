'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface DashboardTileProps {
  title: string;
  icon?: LucideIcon;
  className?: string;
  children: React.ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
  isLoading?: boolean;
}

export default function DashboardTile({
  title,
  icon: Icon,
  className,
  children,
  action,
  isLoading = false,
}: DashboardTileProps) {
  return (
    <div
      className={cn(
        'bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {Icon && <Icon className="w-5 h-5 text-blue-600" />}
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        </div>
        {action && (
          <button
            onClick={action.onClick}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            {action.label}
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="tile-content">{children}</div>
      )}
    </div>
  );
}