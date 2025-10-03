import React, { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { X, ChevronRight, ChevronLeft, Star } from 'lucide-react';

interface TourStep {
  target: string;
  title: string;
  content: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
}

/**
 * Interactive tour component for premium features
 *
 * @component PremiumFeatureTour
 * @returns {JSX.Element|null} Rendered tour interface or null
 *
 * @example
 * ```tsx
 * <PremiumFeatureTour />
 * ```
 *
 * @since 1.0.0
 */
export const PremiumFeatureTour: React.FC = () => {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [hasSeenTour, setHasSeenTour] = useState(false);

  const steps: TourStep[] = [
    {
      target: '.full-rankings',
      title: 'Full Top 500 Rankings',
      content: 'Access all 500 prospects instead of just the top 100. Get comprehensive insights into deeper dynasty targets.',
      placement: 'bottom'
    },
    {
      target: '.advanced-filters',
      title: 'Advanced Filtering',
      content: 'Use complex multi-criteria filters with AND/OR logic to find exactly the prospects you need.',
      placement: 'right'
    },
    {
      target: '.comparison-tool',
      title: 'Unlimited Comparisons',
      content: 'Compare up to 10 prospects simultaneously with detailed analytics and export capabilities.',
      placement: 'left'
    },
    {
      target: '.historical-data',
      title: 'Historical Trends',
      content: 'View performance trajectories and season-over-season comparisons to identify rising stars.',
      placement: 'top'
    },
    {
      target: '.enhanced-outlooks',
      title: 'AI-Powered Outlooks',
      content: 'Get personalized ML predictions with detailed explanations tailored to your league settings.',
      placement: 'bottom'
    },
    {
      target: '.export-button',
      title: 'Data Export',
      content: 'Export rankings, comparisons, and reports in CSV, PDF, or JSON formats.',
      placement: 'left'
    },
    {
      target: '.priority-support',
      title: 'Priority Support',
      content: 'Get faster response times and direct access to feature requests with voting privileges.',
      placement: 'top'
    }
  ];

  useEffect(() => {
    // Check if user is premium and hasn't seen tour
    const tourSeen = localStorage.getItem('premium_tour_seen');
    if (user?.subscriptionTier === 'premium' && !tourSeen) {
      setIsOpen(true);
    }
    setHasSeenTour(!!tourSeen);
  }, [user]);

  const handleClose = () => {
    setIsOpen(false);
    localStorage.setItem('premium_tour_seen', 'true');
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleClose();
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleRestart = () => {
    setCurrentStep(0);
    setIsOpen(true);
  };

  if (!user || user.subscriptionTier !== 'premium') {
    return null;
  }

  const currentStepData = steps[currentStep];

  return (
    <>
      {/* Tour Button */}
      {!isOpen && (
        <Button
          onClick={handleRestart}
          variant="ghost"
          size="sm"
          className="fixed bottom-4 right-4 z-40"
        >
          <Star className="w-4 h-4 mr-2" />
          Premium Tour
        </Button>
      )}

      {/* Tour Overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/50" onClick={handleClose} />

          {/* Tour Card */}
          <Card className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-full max-w-md p-6 z-50">
            {/* Close Button */}
            <button
              onClick={handleClose}
              className="absolute top-4 right-4 p-1 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Content */}
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-r from-amber-500 to-amber-600 text-white">
                  <Star className="w-5 h-5 fill-current" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{currentStepData.title}</h3>
                  <p className="text-sm text-gray-600">
                    Step {currentStep + 1} of {steps.length}
                  </p>
                </div>
              </div>

              {/* Description */}
              <p className="text-gray-700">{currentStepData.content}</p>

              {/* Progress Bar */}
              <div className="w-full h-1 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-amber-600 transition-all duration-300"
                  style={{
                    width: `${((currentStep + 1) / steps.length) * 100}%`
                  }}
                />
              </div>

              {/* Navigation */}
              <div className="flex justify-between items-center">
                <Button
                  onClick={handlePrev}
                  variant="outline"
                  size="sm"
                  disabled={currentStep === 0}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </Button>

                <div className="flex gap-1">
                  {steps.map((_, index) => (
                    <div
                      key={index}
                      className={`w-2 h-2 rounded-full transition-colors ${
                        index === currentStep
                          ? 'bg-amber-600'
                          : index < currentStep
                          ? 'bg-amber-400'
                          : 'bg-gray-300'
                      }`}
                    />
                  ))}
                </div>

                <Button
                  onClick={handleNext}
                  size="sm"
                  className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700"
                >
                  {currentStep === steps.length - 1 ? 'Finish' : 'Next'}
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
};

export default PremiumFeatureTour;