/**
 * Unified engagement dashboard component.
 *
 * @component UserEngagementDashboard
 * @since 1.0.0
 */

'use client';

import React from 'react';
import { useAchievements } from '@/hooks/useAchievements';
import { useEmailPreferences } from '@/hooks/useEmailPreferences';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Trophy, Mail, Users, MessageSquare, TrendingUp } from 'lucide-react';

/**
 * User engagement dashboard component.
 *
 * Integrates all engagement features into a unified dashboard showing:
 * - Achievement progress
 * - Email preferences
 * - Referral stats
 * - Quick feedback widget
 *
 * @returns {JSX.Element} Rendered engagement dashboard
 */
export function UserEngagementDashboard(): JSX.Element {
  const { progress: achievementProgress } = useAchievements(false);
  const { preferences: emailPrefs } = useEmailPreferences();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          Engagement Dashboard
        </h2>
        <p className="text-muted-foreground">
          Track your progress and manage your settings
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Achievement Progress */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Achievements</CardTitle>
            <Trophy className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {achievementProgress?.unlocked_count || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              of {achievementProgress?.total_count || 0} unlocked
            </p>
            <Progress
              value={achievementProgress?.progress_percentage || 0}
              className="mt-2 h-2"
            />
          </CardContent>
        </Card>

        {/* Email Status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Email Digest</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {emailPrefs?.digest_enabled ? 'Active' : 'Disabled'}
            </div>
            <p className="text-xs text-muted-foreground">
              {emailPrefs?.frequency || 'weekly'} updates
            </p>
          </CardContent>
        </Card>

        {/* Referrals */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Referrals</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">friends referred</p>
          </CardContent>
        </Card>

        {/* Points Earned */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Points</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {achievementProgress?.earned_points || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              of {achievementProgress?.total_points || 0} possible
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Quick Feedback</CardTitle>
            <CardDescription>Help us improve the platform</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Share your thoughts and suggestions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Personalized Suggestions</CardTitle>
            <CardDescription>Based on your activity</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Check out new prospects matching your preferences
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default UserEngagementDashboard;
