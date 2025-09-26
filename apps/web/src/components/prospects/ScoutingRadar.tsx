'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from 'recharts';
import {
  Eye,
  TrendingUp,
  Clock,
  Info,
  Star,
  Award,
  Filter
} from 'lucide-react';

interface ScoutingGrade {
  source: string;
  overall: number;
  future_value: number;
  hit: number;
  power: number;
  speed: number;
  field: number;
  arm: number;
  updated_at: string;
}

interface ScoutingRadarProps {
  scoutingGrades: ScoutingGrade[];
  prospectName: string;
  position: string;
  className?: string;
}

export function ScoutingRadar({
  scoutingGrades,
  prospectName,
  position,
  className = ''
}: ScoutingRadarProps) {
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [activeTab, setActiveTab] = useState('radar');

  // Available sources
  const sources = useMemo(() => {
    const allSources = Array.from(new Set(scoutingGrades.map(grade => grade.source)));
    return ['all', ...allSources];
  }, [scoutingGrades]);

  // Get grade color based on 20-80 scale
  const getGradeColor = (grade: number) => {
    if (grade >= 70) return 'text-green-600';
    if (grade >= 60) return 'text-blue-600';
    if (grade >= 50) return 'text-yellow-600';
    if (grade >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

  // Get grade description
  const getGradeDescription = (grade: number) => {
    if (grade >= 80) return 'Elite (80)';
    if (grade >= 70) return 'Plus-Plus (70)';
    if (grade >= 60) return 'Plus (60)';
    if (grade >= 55) return 'Above Average (55)';
    if (grade >= 50) return 'Average (50)';
    if (grade >= 45) return 'Below Average (45)';
    if (grade >= 40) return 'Well Below Average (40)';
    return 'Poor (20-35)';
  };

  // Get source credibility indicator
  const getSourceCredibility = (source: string) => {
    const credibilityMap: Record<string, { level: string; color: string }> = {
      'Fangraphs': { level: 'High', color: 'bg-green-100 text-green-800' },
      'MLB Pipeline': { level: 'High', color: 'bg-green-100 text-green-800' },
      'Baseball America': { level: 'High', color: 'bg-green-100 text-green-800' },
      'Keith Law': { level: 'High', color: 'bg-green-100 text-green-800' },
      'MLB.com': { level: 'Medium', color: 'bg-yellow-100 text-yellow-800' },
      'ESPN': { level: 'Medium', color: 'bg-yellow-100 text-yellow-800' }
    };

    return credibilityMap[source] || { level: 'Standard', color: 'bg-gray-100 text-gray-800' };
  };

  // Prepare radar chart data
  const radarData = useMemo(() => {
    const filteredGrades = selectedSource === 'all'
      ? scoutingGrades
      : scoutingGrades.filter(grade => grade.source === selectedSource);

    if (filteredGrades.length === 0) return [];

    // Average grades across selected sources
    const averageGrades = {
      hit: Math.round(filteredGrades.reduce((sum, grade) => sum + (grade.hit || 50), 0) / filteredGrades.length),
      power: Math.round(filteredGrades.reduce((sum, grade) => sum + (grade.power || 50), 0) / filteredGrades.length),
      speed: Math.round(filteredGrades.reduce((sum, grade) => sum + (grade.speed || 50), 0) / filteredGrades.length),
      field: Math.round(filteredGrades.reduce((sum, grade) => sum + (grade.field || 50), 0) / filteredGrades.length),
      arm: Math.round(filteredGrades.reduce((sum, grade) => sum + (grade.arm || 50), 0) / filteredGrades.length)
    };

    // Position-specific tool adjustments
    const tools = position.includes('P') || position === 'SP' || position === 'RP'
      ? [
          { skill: 'Stuff', value: averageGrades.power, fullMark: 80 },
          { skill: 'Command', value: averageGrades.hit, fullMark: 80 },
          { skill: 'Control', value: averageGrades.field, fullMark: 80 },
          { skill: 'Durability', value: averageGrades.speed, fullMark: 80 },
          { skill: 'Delivery', value: averageGrades.arm, fullMark: 80 }
        ]
      : [
          { skill: 'Hit', value: averageGrades.hit, fullMark: 80 },
          { skill: 'Power', value: averageGrades.power, fullMark: 80 },
          { skill: 'Speed', value: averageGrades.speed, fullMark: 80 },
          { skill: 'Field', value: averageGrades.field, fullMark: 80 },
          { skill: 'Arm', value: averageGrades.arm, fullMark: 80 }
        ];

    return tools;
  }, [scoutingGrades, selectedSource, position]);

  // Prepare timeline data for grade progression
  const timelineData = useMemo(() => {
    const gradesByDate = scoutingGrades
      .sort((a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime())
      .map(grade => ({
        date: new Date(grade.updated_at).toLocaleDateString(),
        overall: grade.overall,
        future_value: grade.future_value,
        source: grade.source
      }));

    return gradesByDate;
  }, [scoutingGrades]);

  // Calculate composite score
  const compositeScore = useMemo(() => {
    if (scoutingGrades.length === 0) return null;

    // Weight grades by source credibility
    let totalWeight = 0;
    let weightedSum = 0;

    scoutingGrades.forEach(grade => {
      const credibility = getSourceCredibility(grade.source);
      const weight = credibility.level === 'High' ? 1.0 : credibility.level === 'Medium' ? 0.8 : 0.6;

      totalWeight += weight;
      weightedSum += (grade.overall || 50) * weight;
    });

    return totalWeight > 0 ? Math.round(weightedSum / totalWeight) : null;
  }, [scoutingGrades]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold">{label}</p>
          <p className={`${getGradeColor(payload[0].value)}`}>
            Grade: {payload[0].value} ({getGradeDescription(payload[0].value)})
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card className={`w-full ${className}`}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <Eye className="h-5 w-5 text-purple-600" />
            <span>Scouting Grades</span>
          </CardTitle>
          {compositeScore && (
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="flex items-center space-x-1">
                <Star className="h-3 w-3" />
                <span>Composite: {compositeScore}</span>
              </Badge>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Source Filter */}
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-gray-500" />
          <Select value={selectedSource} onValueChange={setSelectedSource}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sources</SelectItem>
              {sources.slice(1).map(source => (
                <SelectItem key={source} value={source}>
                  {source}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="radar">Radar Chart</TabsTrigger>
            <TabsTrigger value="progression">Progression</TabsTrigger>
            <TabsTrigger value="sources">Sources</TabsTrigger>
          </TabsList>

          <TabsContent value="radar" className="space-y-4">
            {radarData.length > 0 ? (
              <div className="space-y-4">
                <ResponsiveContainer width="100%" height={400}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="skill" />
                    <PolarRadiusAxis
                      angle={0}
                      domain={[20, 80]}
                      tickCount={4}
                      tick={{ fontSize: 12 }}
                    />
                    <Radar
                      name={prospectName}
                      dataKey="value"
                      stroke="#8b5cf6"
                      fill="#8b5cf6"
                      fillOpacity={0.2}
                      strokeWidth={2}
                    />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>

                {/* Grade Breakdown */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  {radarData.map((tool, index) => (
                    <div key={index} className="text-center p-3 bg-gray-50 rounded-lg">
                      <div className={`text-lg font-bold ${getGradeColor(tool.value)}`}>
                        {tool.value}
                      </div>
                      <div className="text-sm font-medium text-gray-900">{tool.skill}</div>
                      <div className="text-xs text-gray-500">
                        {getGradeDescription(tool.value).split(' ')[0]}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No scouting data available for selected source
              </div>
            )}
          </TabsContent>

          <TabsContent value="progression" className="space-y-4">
            {timelineData.length > 1 ? (
              <div className="space-y-4">
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={timelineData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis domain={[20, 80]} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="overall"
                      stroke="#8b5cf6"
                      strokeWidth={2}
                      dot={{ fill: '#8b5cf6', strokeWidth: 2, r: 4 }}
                      name="Overall Grade"
                    />
                    <Line
                      type="monotone"
                      dataKey="future_value"
                      stroke="#06b6d4"
                      strokeWidth={2}
                      dot={{ fill: '#06b6d4', strokeWidth: 2, r: 4 }}
                      name="Future Value"
                    />
                  </LineChart>
                </ResponsiveContainer>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start space-x-2">
                    <TrendingUp className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <h4 className="font-semibold text-blue-900 mb-1">Grade Progression</h4>
                      <p className="text-blue-800 text-sm">
                        Tracking changes in scouting grades over time. Purple line shows overall grade,
                        blue line shows future value projection.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Insufficient data points to show progression
              </div>
            )}
          </TabsContent>

          <TabsContent value="sources" className="space-y-4">
            <div className="space-y-3">
              {scoutingGrades.map((grade, index) => {
                const credibility = getSourceCredibility(grade.source);

                return (
                  <div key={index} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        <h4 className="font-semibold text-gray-900">{grade.source}</h4>
                        <Badge className={credibility.color}>
                          {credibility.level}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Clock className="h-4 w-4 text-gray-400" />
                        <span className="text-sm text-gray-500">
                          {new Date(grade.updated_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="text-center">
                        <div className={`text-lg font-bold ${getGradeColor(grade.overall)}`}>
                          {grade.overall}
                        </div>
                        <div className="text-xs text-gray-600">Overall</div>
                      </div>
                      <div className="text-center">
                        <div className={`text-lg font-bold ${getGradeColor(grade.future_value)}`}>
                          {grade.future_value}
                        </div>
                        <div className="text-xs text-gray-600">Future Value</div>
                      </div>
                      <div className="text-center">
                        <div className={`text-lg font-bold ${getGradeColor(grade.hit || 50)}`}>
                          {grade.hit || 50}
                        </div>
                        <div className="text-xs text-gray-600">
                          {position.includes('P') ? 'Command' : 'Hit'}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className={`text-lg font-bold ${getGradeColor(grade.power || 50)}`}>
                          {grade.power || 50}
                        </div>
                        <div className="text-xs text-gray-600">
                          {position.includes('P') ? 'Stuff' : 'Power'}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Grading Scale Reference */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="flex items-start space-x-2">
                <Info className="h-5 w-5 text-gray-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">20-80 Scouting Scale</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    <div><span className="text-green-600 font-semibold">70-80:</span> Plus to Elite</div>
                    <div><span className="text-blue-600 font-semibold">55-65:</span> Above Avg to Plus</div>
                    <div><span className="text-yellow-600 font-semibold">45-55:</span> Average</div>
                    <div><span className="text-red-600 font-semibold">20-45:</span> Below Average</div>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}