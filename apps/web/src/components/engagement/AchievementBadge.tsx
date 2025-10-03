/**
 * Achievement badge component with icon and animation.
 *
 * @component AchievementBadge
 * @module AchievementBadge
 * @since 1.0.0
 */

'use client';

import React from 'react';
import { Achievement } from '@/lib/api/achievements';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Lock, Trophy } from 'lucide-react';

/**
 * Props for AchievementBadge component.
 *
 * @interface AchievementBadgeProps
 * @since 1.0.0
 */
export interface AchievementBadgeProps {
  /** Achievement data */
  achievement: Achievement;
  /** Show progress bar for locked achievements */
  showProgress?: boolean;
  /** Optional CSS class name */
  className?: string;
}

/**
 * Achievement badge display component.
 *
 * Displays individual achievement with icon, name, description, and
 * unlock status. Shows progress bar for locked achievements.
 *
 * @param {AchievementBadgeProps} props - Component props
 * @returns {JSX.Element} Rendered achievement badge
 *
 * @example
 * ```tsx
 * <AchievementBadge
 *   achievement={achievement}
 *   showProgress={true}
 * />
 * ```
 *
 * @since 1.0.0
 */
export function AchievementBadge({
  achievement,
  showProgress = false,
  className,
}: AchievementBadgeProps): JSX.Element {
  const isUnlocked = achievement.unlocked || false;
  const progress = achievement.progress || 0;

  return (
    <Card
      className={`p-4 ${
        isUnlocked ? 'bg-gradient-to-br from-yellow-50 to-amber-50 border-amber-200' : 'bg-gray-50'
      } ${className || ''}`}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={`text-4xl ${
            isUnlocked ? 'animate-bounce-once' : 'opacity-40'
          }`}
        >
          {achievement.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <h4
                className={`font-semibold ${
                  isUnlocked ? 'text-amber-900' : 'text-gray-600'
                }`}
              >
                {achievement.name}
                {!isUnlocked && (
                  <Lock className="inline-block ml-2 h-4 w-4 text-gray-400" />
                )}
              </h4>
              <p
                className={`text-sm mt-1 ${
                  isUnlocked ? 'text-amber-700' : 'text-gray-500'
                }`}
              >
                {achievement.description}
              </p>
            </div>

            {/* Points badge */}
            <Badge
              variant={isUnlocked ? 'default' : 'secondary'}
              className={isUnlocked ? 'bg-amber-500' : ''}
            >
              <Trophy className="h-3 w-3 mr-1" />
              {achievement.points}
            </Badge>
          </div>

          {/* Progress bar for locked achievements */}
          {!isUnlocked && showProgress && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                <span>Progress</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}

          {/* Unlock date for unlocked achievements */}
          {isUnlocked && achievement.unlocked_at && (
            <p className="text-xs text-amber-600 mt-2">
              Unlocked{' '}
              {new Date(achievement.unlocked_at).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

export default AchievementBadge;
