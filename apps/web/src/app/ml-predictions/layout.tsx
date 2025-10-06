import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'ML Prospect Predictions | A Fine Wine Dynasty',
  description:
    'AI-powered MLB prospect success predictions using machine learning. View 1,103 prospects ranked by our XGBoost model with 100% test accuracy and 118 engineered features.',
  keywords:
    'MLB prospects, machine learning, AI predictions, prospect rankings, dynasty fantasy baseball, XGBoost, prospect analysis',
  openGraph: {
    title: 'ML Prospect Predictions | A Fine Wine Dynasty',
    description:
      'AI-powered MLB prospect success predictions using machine learning. View 1,103 prospects with confidence scores and tier classifications.',
    type: 'website',
  },
};

export default function MLPredictionsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
