/**
 * Unified Account Management Page
 *
 * Provides centralized account management with tabbed navigation for:
 * - Profile management
 * - Subscription & billing
 * - Fantrax integration
 * - User preferences
 *
 * @module app/account/page
 * @since 1.0.0
 */

'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card } from '@/components/ui/card';
import { useAuth } from '@/hooks/useAuth';
import { ProfileTab } from '@/components/account/ProfileTab';
import { SubscriptionTab } from '@/components/account/SubscriptionTab';
import { FantraxTab } from '@/components/account/FantraxTab';
import { PreferencesTab } from '@/components/account/PreferencesTab';
import { User, CreditCard, Link as LinkIcon, Settings } from 'lucide-react';

/**
 * Valid tab identifiers
 */
type TabValue = 'profile' | 'subscription' | 'fantrax' | 'preferences';

const DEFAULT_TAB: TabValue = 'profile';

/**
 * Inner component that uses useSearchParams (wrapped in Suspense)
 */
function AccountPageContent(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading } = useAuth();

  // Get initial tab from URL query param
  const urlTab = searchParams.get('tab') as TabValue | null;
  const [activeTab, setActiveTab] = useState<TabValue>(
    isValidTab(urlTab) ? urlTab : DEFAULT_TAB
  );

  /**
   * Update URL when tab changes
   */
  useEffect(() => {
    const currentTab = searchParams.get('tab');
    if (currentTab !== activeTab) {
      router.push(`/account?tab=${activeTab}`, { scroll: false });
    }
  }, [activeTab, router, searchParams]);

  /**
   * Handle tab change and update URL
   */
  const handleTabChange = (value: string): void => {
    if (isValidTab(value)) {
      setActiveTab(value);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-6xl">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-8"></div>
          <div className="h-12 bg-gray-200 rounded mb-6"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!user) {
    router.push('/login?redirect=/account');
    return <></>;
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Account Settings</h1>
        <p className="text-muted-foreground">
          Manage your profile, subscription, integrations, and preferences
        </p>
      </div>

      {/* Tabbed Interface */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        {/* Tab Navigation */}
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger
            value="profile"
            className="flex items-center gap-2"
            data-testid="tab-profile"
          >
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">Profile</span>
          </TabsTrigger>
          <TabsTrigger
            value="subscription"
            className="flex items-center gap-2"
            data-testid="tab-subscription"
          >
            <CreditCard className="h-4 w-4" />
            <span className="hidden sm:inline">Subscription</span>
          </TabsTrigger>
          <TabsTrigger
            value="fantrax"
            className="flex items-center gap-2"
            data-testid="tab-fantrax"
          >
            <LinkIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Fantrax</span>
          </TabsTrigger>
          <TabsTrigger
            value="preferences"
            className="flex items-center gap-2"
            data-testid="tab-preferences"
          >
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">Preferences</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab Content */}
        <div className="mt-6">
          <TabsContent value="profile" className="space-y-6">
            <ProfileTab />
          </TabsContent>

          <TabsContent value="subscription" className="space-y-6">
            <SubscriptionTab />
          </TabsContent>

          <TabsContent value="fantrax" className="space-y-6">
            <FantraxTab />
          </TabsContent>

          <TabsContent value="preferences" className="space-y-6">
            <PreferencesTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

/**
 * Validates if a string is a valid tab value
 *
 * @param value - Value to validate
 * @returns True if valid tab, false otherwise
 *
 * @since 1.0.0
 */
function isValidTab(value: string | null): value is TabValue {
  const validTabs: TabValue[] = ['profile', 'subscription', 'fantrax', 'preferences'];
  return value !== null && validTabs.includes(value as TabValue);
}

/**
 * Loading fallback for Suspense boundary
 */
function AccountPageLoading(): JSX.Element {
  return (
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-8"></div>
        <div className="h-12 bg-gray-200 rounded mb-6"></div>
        <div className="h-64 bg-gray-200 rounded"></div>
      </div>
    </div>
  );
}

/**
 * Main account page component with Suspense boundary
 *
 * Wraps the content component in Suspense to handle useSearchParams() properly
 *
 * @returns {JSX.Element} Rendered account management interface
 *
 * @example
 * ```tsx
 * // Direct navigation
 * <Link href="/account">Account Settings</Link>
 *
 * // Navigate to specific tab
 * <Link href="/account?tab=fantrax">Fantrax Integration</Link>
 * ```
 *
 * @since 1.0.0
 */
export default function AccountPage(): JSX.Element {
  return (
    <Suspense fallback={<AccountPageLoading />}>
      <AccountPageContent />
    </Suspense>
  );
}
