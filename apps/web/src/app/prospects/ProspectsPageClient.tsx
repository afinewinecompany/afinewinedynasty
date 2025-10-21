'use client';

import { useState } from 'react';
import ProspectRankingsDashboard from '@/components/rankings/ProspectRankingsDashboard';
import CompositeRankingsDashboard from '@/components/rankings/CompositeRankingsDashboard';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function ProspectsPageClient() {
  const [activeTab, setActiveTab] = useState('composite');

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-2 mb-6">
            <TabsTrigger value="composite">Composite Rankings</TabsTrigger>
            <TabsTrigger value="dynasty">Dynasty Rankings</TabsTrigger>
          </TabsList>

          <TabsContent value="composite">
            <CompositeRankingsDashboard />
          </TabsContent>

          <TabsContent value="dynasty">
            <ProspectRankingsDashboard />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
