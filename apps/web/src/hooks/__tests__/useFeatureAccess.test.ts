import { renderHook } from '@testing-library/react';
import {
  useFeatureAccess,
  isPremiumFeature,
  getFeatureLimit,
} from '../useFeatureAccess';
import { useAuth } from '../useAuth';

// Mock useAuth hook
jest.mock('../useAuth');

describe('useFeatureAccess Hook', () => {
  const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Premium User Access', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '1',
          email: 'premium@test.com',
          subscriptionTier: 'premium',
          isActive: true,
        },
        login: jest.fn(),
        logout: jest.fn(),
        loading: false,
        error: null,
      });
    });

    it('returns correct limits for premium user', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.prospectsLimit).toBe(500);
      expect(result.current.maxSavedSearches).toBe(50);
      expect(result.current.maxComparisons).toBe(10);
    });

    it('enables all premium features', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.canExport).toBe(true);
      expect(result.current.canUseAdvancedFilters).toBe(true);
      expect(result.current.canCompare).toBe(true);
      expect(result.current.canAccessHistorical).toBe(true);
      expect(result.current.canAccessEnhancedOutlooks).toBe(true);
      expect(result.current.hasPrioritySupport).toBe(true);
      expect(result.current.canVoteOnFeatures).toBe(true);
      expect(result.current.canCreateFeatureRequests).toBe(true);
      expect(result.current.canAccessBetaFeatures).toBe(true);
    });
  });

  describe('Free User Access', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '2',
          email: 'free@test.com',
          subscriptionTier: 'free',
          isActive: true,
        },
        login: jest.fn(),
        logout: jest.fn(),
        loading: false,
        error: null,
      });
    });

    it('returns correct limits for free user', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.prospectsLimit).toBe(100);
      expect(result.current.maxSavedSearches).toBe(5);
      expect(result.current.maxComparisons).toBe(2);
    });

    it('disables premium features', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.canExport).toBe(false);
      expect(result.current.canUseAdvancedFilters).toBe(false);
      expect(result.current.canCompare).toBe(false);
      expect(result.current.canAccessHistorical).toBe(false);
      expect(result.current.canAccessEnhancedOutlooks).toBe(false);
      expect(result.current.hasPrioritySupport).toBe(false);
      expect(result.current.canVoteOnFeatures).toBe(false);
      expect(result.current.canCreateFeatureRequests).toBe(false);
      expect(result.current.canAccessBetaFeatures).toBe(false);
    });
  });

  describe('Admin User Access', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        user: {
          id: '3',
          email: 'admin@test.com',
          subscriptionTier: 'admin',
          isActive: true,
        },
        login: jest.fn(),
        logout: jest.fn(),
        loading: false,
        error: null,
      });
    });

    it('grants full access to admin users', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.prospectsLimit).toBe(500);
      expect(result.current.canExport).toBe(true);
      expect(result.current.canUseAdvancedFilters).toBe(true);
      expect(result.current.canAccessBetaFeatures).toBe(true);
    });
  });

  describe('No User', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        user: null,
        login: jest.fn(),
        logout: jest.fn(),
        loading: false,
        error: null,
      });
    });

    it('returns free tier limits when no user', () => {
      const { result } = renderHook(() => useFeatureAccess());

      expect(result.current.prospectsLimit).toBe(100);
      expect(result.current.canExport).toBe(false);
      expect(result.current.maxSavedSearches).toBe(5);
    });
  });
});

describe('isPremiumFeature Function', () => {
  it('correctly identifies premium features', () => {
    expect(isPremiumFeature('canExport')).toBe(true);
    expect(isPremiumFeature('canUseAdvancedFilters')).toBe(true);
    expect(isPremiumFeature('canCompare')).toBe(true);
    expect(isPremiumFeature('canAccessHistorical')).toBe(true);
  });

  it('correctly identifies non-premium features', () => {
    expect(isPremiumFeature('prospectsLimit')).toBe(false);
    expect(isPremiumFeature('maxSavedSearches')).toBe(false);
    expect(isPremiumFeature('maxComparisons')).toBe(false);
  });
});

describe('getFeatureLimit Function', () => {
  it('returns correct limits for premium users', () => {
    expect(getFeatureLimit('prospectsLimit', true)).toBe(500);
    expect(getFeatureLimit('maxSavedSearches', true)).toBe(50);
    expect(getFeatureLimit('maxComparisons', true)).toBe(10);
    expect(getFeatureLimit('canExport', true)).toBe(true);
  });

  it('returns correct limits for free users', () => {
    expect(getFeatureLimit('prospectsLimit', false)).toBe(100);
    expect(getFeatureLimit('maxSavedSearches', false)).toBe(5);
    expect(getFeatureLimit('maxComparisons', false)).toBe(2);
    expect(getFeatureLimit('canExport', false)).toBe(false);
  });

  it('returns false for unknown features', () => {
    expect(getFeatureLimit('unknownFeature' as any, true)).toBe(false);
    expect(getFeatureLimit('unknownFeature' as any, false)).toBe(false);
  });
});
