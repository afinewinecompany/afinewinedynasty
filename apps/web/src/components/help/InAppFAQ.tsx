import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Search, X, HelpCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface FAQItem {
  id: string;
  question: string;
  answer: string;
  category: string;
  tags: string[];
}

const faqData: FAQItem[] = [
  {
    id: '1',
    question: 'How do I upgrade my subscription?',
    answer:
      'Navigate to Account Settings > Subscription and click "Upgrade Plan". Select your desired tier and enter payment information. Your new features will be available immediately.',
    category: 'Billing',
    tags: ['subscription', 'upgrade', 'payment'],
  },
  {
    id: '2',
    question: 'What data sources do you use for prospect information?',
    answer:
      'We aggregate data from official MLB statistics, MiLB.com, Statcast measurements, team reports, and our proprietary scouting network to provide comprehensive prospect analysis.',
    category: 'Data',
    tags: ['data', 'sources', 'statistics'],
  },
  {
    id: '3',
    question: 'How often are rankings updated?',
    answer:
      'Rankings are updated weekly during the season and bi-weekly during the off-season. ML predictions are recalculated daily based on the latest performance data.',
    category: 'Features',
    tags: ['rankings', 'updates', 'frequency'],
  },
  {
    id: '4',
    question: 'Can I export prospect data?',
    answer:
      'Pro and Premium subscribers can export data to CSV format. Premium users also get API access for programmatic data retrieval and bulk exports.',
    category: 'Features',
    tags: ['export', 'csv', 'data', 'api'],
  },
  {
    id: '5',
    question: 'How do saved searches work?',
    answer:
      'Saved searches remember your filter criteria and can be quickly accessed from your dashboard. Premium users can set up notifications when new prospects match their search criteria.',
    category: 'Features',
    tags: ['search', 'saved', 'filters', 'notifications'],
  },
  {
    id: '6',
    question: 'What is the prospect comparison tool?',
    answer:
      'The comparison tool allows you to select 2-4 prospects and view their statistics side-by-side with radar chart visualizations. You can compare current stats, projections, and historical performance.',
    category: 'Features',
    tags: ['comparison', 'prospects', 'visualization'],
  },
  {
    id: '7',
    question: 'How accurate are the ML predictions?',
    answer:
      'Our models have shown 78% accuracy for next-season predictions and 65% for 3-year projections. We have an 82% success rate in identifying breakout candidates.',
    category: 'ML',
    tags: ['predictions', 'accuracy', 'machine learning'],
  },
  {
    id: '8',
    question: 'Can I integrate with my fantasy baseball platform?',
    answer:
      'We are developing integrations with major fantasy platforms. Fantrax integration is coming Q1 2025, with Yahoo and ESPN planned for later in the year.',
    category: 'Integrations',
    tags: ['fantasy', 'integration', 'fantrax'],
  },
];

export const InAppFAQ: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [isOpen, setIsOpen] = useState(false);

  const categories = Array.from(new Set(faqData.map((item) => item.category)));

  const filteredFAQ = faqData.filter((item) => {
    const matchesSearch =
      searchQuery === '' ||
      item.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.answer.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some((tag) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase())
      );

    const matchesCategory =
      !selectedCategory || item.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedItems(newExpanded);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-full shadow-lg hover:bg-blue-700 transition-colors z-50"
        aria-label="Open FAQ"
      >
        <span className="flex items-center gap-2">
          <HelpCircle className="h-5 w-5" />
          Help
        </span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 max-h-[600px] shadow-xl">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              Frequently Asked Questions
            </CardTitle>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
              aria-label="Close FAQ"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="mt-3 space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search FAQ..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-2"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  !selectedCategory
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                All
              </button>
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    selectedCategory === category
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="max-h-[400px] overflow-y-auto">
          {filteredFAQ.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-4">
              No questions found. Try adjusting your search.
            </p>
          ) : (
            <div className="space-y-2">
              {filteredFAQ.map((item) => (
                <div
                  key={item.id}
                  className="border rounded-lg overflow-hidden"
                >
                  <button
                    onClick={() => toggleExpanded(item.id)}
                    className="w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors flex items-center justify-between"
                  >
                    <span className="text-sm font-medium pr-2">
                      {item.question}
                    </span>
                    {expandedItems.has(item.id) ? (
                      <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
                    )}
                  </button>
                  {expandedItems.has(item.id) && (
                    <div className="px-4 pb-3 pt-1 bg-gray-50">
                      <p className="text-sm text-gray-600">{item.answer}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.tags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-block px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 pt-4 border-t">
            <p className="text-xs text-gray-500 text-center">
              Can't find what you're looking for?{' '}
              <a
                href="mailto:support@afinewinedynasty.com"
                className="text-blue-600 hover:underline"
              >
                Contact Support
              </a>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default InAppFAQ;
