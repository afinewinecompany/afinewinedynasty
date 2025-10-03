/**
 * Achievements list component for user profile.
 *
 * @component AchievementsList
 * @module AchievementsList
 * @since 1.0.0
 */

'use client';

import React, { useState } from 'react';
import { useAchievements } from '@/hooks/useAchievements';
import { AchievementBadge } from './AchievementBadge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Trophy, Target, AlertCircle } from 'lucide-react';

/**
 * Props for AchievementsList component.
 *
 * @interface AchievementsListProps
 * @since 1.0.0
 */
export interface AchievementsListProps {
  /** Optional CSS class name */
  className?: string;
}

/**
 * Achievements list component.
 *
 * Displays user's achievements with tabs for unlocked/locked,
 * progress summary, and next achievement to unlock.
 *
 * @param {AchievementsListProps} props - Component props
 * @returns {JSX.Element} Rendered achievements list
 *
 * @example
 * ```tsx
 * <AchievementsList className="max-w-4xl mx-auto" />
 * ```
 *
 * @since 1.0.0
 */
export function AchievementsList({ className }: AchievementsListProps): JSX.Element {
  const { achievements, progress, isLoading, error } = useAchievements(true);
  const [activeTab, setActiveTab] = useState<string>('unlocked');

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className || ''}`}>
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Failed to load achievements. Please try again later.
        </AlertDescription>
      </Alert>
    );
  }

  const unlockedAchievements = achievements.filter((a) => a.unlocked);
  const lockedAchievements = achievements.filter((a) => !a.unlocked);

  return (
    <div className={className}>
      {/* Progress Summary Card */}
      {progress && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-500" />
              Achievement Progress
            </CardTitle>
            <CardDescription>
              Track your progress and earn rewards
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Overall Progress */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Achievements</span>
                <span className="text-sm text-muted-foreground">
                  {progress.unlocked_count} / {progress.total_count}
                </span>
              </div>
              <Progress value={progress.progress_percentage} className="h-3" />
            </div>

            {/* Points Progress */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Points Earned</span>
                <span className="text-sm text-muted-foreground">
                  {progress.earned_points} / {progress.total_points}
                </span>
              </div>
              <Progress
                value={(progress.earned_points / progress.total_points) * 100}
                className="h-3"
              />
            </div>

            {/* Next Achievement */}
            {progress.next_achievement && (
              <div className="pt-4 border-t">
                <div className="flex items-center gap-2 mb-3">
                  <Target className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium">Next Achievement</span>
                </div>
                <AchievementBadge
                  achievement={progress.next_achievement}
                  showProgress={true}
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Achievements List */}
      <Card>
        <CardHeader>
          <CardTitle>All Achievements</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="unlocked">
                Unlocked ({unlockedAchievements.length})
              </TabsTrigger>
              <TabsTrigger value="locked">
                Locked ({lockedAchievements.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="unlocked" className="mt-4">
              {unlockedAchievements.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Trophy className="h-12 w-12 mx-auto mb-3 opacity-20" />
                  <p>No achievements unlocked yet</p>
                  <p className="text-sm mt-1">Start exploring to earn your first achievement!</p>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {unlockedAchievements.map((achievement) => (
                    <AchievementBadge
                      key={achievement.id}
                      achievement={achievement}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="locked" className="mt-4">
              {lockedAchievements.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Trophy className="h-12 w-12 mx-auto mb-3 text-amber-500" />
                  <p className="font-semibold text-lg">All Achievements Unlocked!</p>
                  <p className="text-sm mt-1">Congratulations on completing everything!</p>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {lockedAchievements.map((achievement) => (
                    <AchievementBadge
                      key={achievement.id}
                      achievement={achievement}
                      showProgress={true}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

export default AchievementsList;
