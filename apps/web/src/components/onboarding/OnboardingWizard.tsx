/**
 * Onboarding wizard component with multi-step flow
 *
 * @component OnboardingWizard
 * @param {OnboardingWizardProps} props - Component props
 * @returns {JSX.Element} Rendered onboarding wizard
 *
 * @example
 * ```tsx
 * <OnboardingWizard
 *   onComplete={() => console.log('Onboarding completed')}
 * />
 * ```
 *
 * @since 1.0.0
 */

import React from 'react';
import { useOnboarding } from '@/hooks/useOnboarding';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export interface OnboardingWizardProps {
  /** Callback when onboarding is completed */
  onComplete?: () => void;
  /** Callback when onboarding is skipped */
  onSkip?: () => void;
}

const STEP_CONTENT = {
  0: {
    title: 'Welcome to A Fine Wine Dynasty',
    description:
      'Your comprehensive prospect evaluation platform for dynasty fantasy baseball',
    content:
      'Get started with ranking prospects, comparing players, and making data-driven decisions.',
  },
  1: {
    title: 'Prospect Rankings',
    description:
      'Browse our comprehensive prospect rankings powered by ML predictions',
    content:
      'Filter by position, organization, and ETA. View detailed stats and scouting grades.',
  },
  2: {
    title: 'Prospect Profiles',
    description:
      'Deep dive into individual prospect analytics and AI-generated outlooks',
    content:
      'View performance trends, ML predictions, and historical comparisons.',
  },
  3: {
    title: 'Prospect Comparisons',
    description: 'Compare prospects side-by-side with statistical analysis',
    content:
      'Use our comparison tool to evaluate multiple prospects and make informed decisions.',
  },
  4: {
    title: 'Choose Your Plan',
    description: 'Select a subscription tier that fits your needs',
    content:
      'Start with our free tier or upgrade to Premium for advanced features.',
  },
  5: {
    title: 'Fantrax Integration (Optional)',
    description: 'Connect your Fantrax league for personalized recommendations',
    content:
      'Get prospect recommendations tailored to your league settings and roster needs.',
  },
};

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({
  onComplete,
  onSkip,
}) => {
  const { status, isLoading, error, nextStep, previousStep, complete, skip } =
    useOnboarding();

  if (isLoading && !status) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading onboarding...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-600">Error: {error.message}</div>
      </div>
    );
  }

  if (!status || status.is_completed) {
    return null;
  }

  const currentStepContent =
    STEP_CONTENT[status.current_step as keyof typeof STEP_CONTENT] ||
    STEP_CONTENT[0];
  const isFirstStep = status.current_step === 0;
  const isLastStep = status.current_step === status.total_steps - 1;

  const handleNext = async (): Promise<void> => {
    if (isLastStep) {
      await complete();
      onComplete?.();
    } else {
      await nextStep();
    }
  };

  const handleSkip = async (): Promise<void> => {
    await skip();
    onSkip?.();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <Card className="max-w-2xl w-full mx-4 p-8">
        <div className="mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">{currentStepContent.title}</h2>
            <button
              onClick={handleSkip}
              className="text-sm text-gray-500 hover:text-gray-700"
              disabled={isLoading}
            >
              Skip Tour
            </button>
          </div>

          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${status.progress_percentage}%` }}
            />
          </div>

          <p className="text-sm text-gray-600 mb-2">
            Step {status.current_step + 1} of {status.total_steps}
          </p>
        </div>

        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-2">
            {currentStepContent.description}
          </h3>
          <p className="text-gray-700">{currentStepContent.content}</p>
        </div>

        <div className="flex justify-between">
          <Button
            onClick={previousStep}
            disabled={isFirstStep || isLoading}
            variant="outline"
          >
            Previous
          </Button>

          <Button onClick={handleNext} disabled={isLoading}>
            {isLastStep ? 'Get Started' : 'Next'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
