'use client';

import { useState, useMemo } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Eye,
  Filter,
  Info,
  ChevronDown,
  ChevronRight,
  Target,
  BarChart3,
} from 'lucide-react';

interface ScoutingRadarComparisonProps {
  comparisonData: any;
  selectedProspects: any[];
}

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

export default function ScoutingRadarComparison({
  comparisonData,
  selectedProspects,
}: ScoutingRadarComparisonProps) {
  const [expandedRadar, setExpandedRadar] = useState(true);
  const [expandedGrades, setExpandedGrades] = useState(false);
  const [selectedSource, setSelectedSource] = useState('all');

  const prospects = comparisonData?.prospects || [];

  // Filter prospects that have scouting grades
  const prospectsWithGrades = prospects.filter((p) => p.scouting_grades);

  // Get all available sources
  const availableSources = useMemo(() => {
    const sources = new Set<string>();
    prospectsWithGrades.forEach((prospect) => {
      if (prospect.scouting_grades?.source) {
        sources.add(prospect.scouting_grades.source);
      }
    });
    return ['all', ...Array.from(sources)];
  }, [prospectsWithGrades]);

  // Determine if we're comparing hitters or pitchers
  const isPitching =
    prospectsWithGrades.length > 0 &&
    (prospectsWithGrades[0].position === 'SP' ||
      prospectsWithGrades[0].position === 'RP');

  // Get grade color based on 20-80 scale
  const getGradeColor = (grade: number) => {
    if (grade >= 70) return 'text-green-600';
    if (grade >= 60) return 'text-blue-600';
    if (grade >= 50) return 'text-yellow-600';
    if (grade >= 40) return 'text-orange-600';
    return 'text-red-600';
  };

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

  // Prepare radar chart data
  const radarData = useMemo(() => {
    if (prospectsWithGrades.length === 0) return [];

    // Define tools based on position
    const tools = isPitching
      ? ['Stuff', 'Command', 'Control', 'Durability', 'Delivery']
      : ['Hit', 'Power', 'Speed', 'Field', 'Arm'];

    const gradeMapping = isPitching
      ? {
          Stuff: 'power',
          Command: 'hit',
          Control: 'field',
          Durability: 'speed',
          Delivery: 'arm',
        }
      : {
          Hit: 'hit',
          Power: 'power',
          Speed: 'speed',
          Field: 'field',
          Arm: 'arm',
        };

    return tools.map((tool) => {
      const dataPoint: any = { skill: tool };

      prospectsWithGrades.forEach((prospect) => {
        const grades = prospect.scouting_grades;
        if (grades) {
          const gradeKey = gradeMapping[tool];
          dataPoint[prospect.name] = grades[gradeKey] || 50;
        }
      });

      return dataPoint;
    });
  }, [prospectsWithGrades, isPitching]);

  // Grade progression analysis
  const gradeProgression = useMemo(() => {
    return prospectsWithGrades
      .map((prospect) => {
        const grades = prospect.scouting_grades;
        if (!grades) return null;

        const toolGrades = isPitching
          ? {
              Stuff: grades.power || 50,
              Command: grades.hit || 50,
              Control: grades.field || 50,
              Durability: grades.speed || 50,
              Delivery: grades.arm || 50,
            }
          : {
              Hit: grades.hit || 50,
              Power: grades.power || 50,
              Speed: grades.speed || 50,
              Field: grades.field || 50,
              Arm: grades.arm || 50,
            };

        const avgGrade =
          Object.values(toolGrades).reduce((sum, grade) => sum + grade, 0) / 5;
        const strengths = Object.entries(toolGrades)
          .filter(([_, grade]) => grade >= 60)
          .map(([tool, grade]) => ({ tool, grade }));
        const weaknesses = Object.entries(toolGrades)
          .filter(([_, grade]) => grade < 45)
          .map(([tool, grade]) => ({ tool, grade }));

        return {
          prospect: prospect.name,
          overall: grades.overall || Math.round(avgGrade),
          futureValue: grades.future_value || Math.round(avgGrade),
          avgGrade: Math.round(avgGrade),
          strengths,
          weaknesses,
          toolGrades,
        };
      })
      .filter(Boolean);
  }, [prospectsWithGrades, isPitching]);

  if (prospectsWithGrades.length < 2) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <Info className="w-5 h-5 text-yellow-600" />
          <div>
            <h3 className="font-medium text-yellow-800">
              Limited Scouting Data
            </h3>
            <p className="text-sm text-yellow-700 mt-1">
              At least 2 prospects with scouting grades are required for radar
              comparison.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Radar Chart Comparison */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setExpandedRadar(!expandedRadar)}
          className="w-full flex items-center justify-between p-4 bg-purple-50 hover:bg-purple-100 transition-colors"
        >
          <h3 className="font-semibold text-purple-900 flex items-center gap-2">
            <Eye className="w-5 h-5" />
            Scouting Radar Comparison
          </h3>
          {expandedRadar ? (
            <ChevronDown className="w-5 h-5 text-purple-600" />
          ) : (
            <ChevronRight className="w-5 h-5 text-purple-600" />
          )}
        </button>

        {expandedRadar && (
          <div className="p-6">
            {/* Source Filter */}
            <div className="flex items-center gap-4 mb-6">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-gray-500" />
                <select
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  {availableSources.map((source) => (
                    <option key={source} value={source}>
                      {source === 'all' ? 'All Sources' : source}
                    </option>
                  ))}
                </select>
              </div>

              <div className="text-sm text-gray-500">
                Comparing {prospectsWithGrades.length} prospects
              </div>
            </div>

            {/* Radar Chart */}
            <div className="h-96 mb-6">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart
                  data={radarData}
                  margin={{ top: 20, right: 80, bottom: 20, left: 80 }}
                >
                  <PolarGrid stroke="#e5e7eb" />
                  <PolarAngleAxis
                    dataKey="skill"
                    tick={{ fontSize: 12, fontWeight: 500 }}
                  />
                  <PolarRadiusAxis
                    angle={0}
                    domain={[20, 80]}
                    tickCount={4}
                    tick={{ fontSize: 10 }}
                    axisLine={false}
                  />

                  {prospectsWithGrades.map((prospect, index) => (
                    <Radar
                      key={prospect.id}
                      name={prospect.name}
                      dataKey={prospect.name}
                      stroke={COLORS[index % COLORS.length]}
                      fill={COLORS[index % COLORS.length]}
                      fillOpacity={0.1}
                      strokeWidth={2.5}
                    />
                  ))}

                  <Legend
                    wrapperStyle={{ paddingTop: '20px' }}
                    iconType="circle"
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Legend with Colors */}
            <div className="flex flex-wrap justify-center gap-4 mb-6">
              {prospectsWithGrades.map((prospect, index) => (
                <div key={prospect.id} className="flex items-center gap-2">
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-sm font-medium text-gray-900">
                    {prospect.name}
                  </span>
                  <span className="text-xs text-gray-500">
                    ({prospect.position} • {prospect.organization})
                  </span>
                </div>
              ))}
            </div>

            {/* Tool Comparison Grid */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tool
                    </th>
                    {prospectsWithGrades.map((prospect, index) => (
                      <th
                        key={prospect.id}
                        className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
                      >
                        <div className="flex items-center justify-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{
                              backgroundColor: COLORS[index % COLORS.length],
                            }}
                          />
                          {prospect.name}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {radarData.map((tool, toolIndex) => (
                    <tr key={toolIndex} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {tool.skill}
                      </td>
                      {prospectsWithGrades.map((prospect, prospectIndex) => {
                        const grade = tool[prospect.name];
                        return (
                          <td
                            key={prospect.id}
                            className="px-4 py-3 text-center"
                          >
                            <div
                              className={`text-lg font-bold ${getGradeColor(grade)}`}
                            >
                              {grade}
                            </div>
                            <div className="text-xs text-gray-500">
                              {getGradeDescription(grade).split(' ')[0]}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Grade Analysis */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <button
          onClick={() => setExpandedGrades(!expandedGrades)}
          className="w-full flex items-center justify-between p-4 bg-green-50 hover:bg-green-100 transition-colors"
        >
          <h3 className="font-semibold text-green-900 flex items-center gap-2">
            <Target className="w-5 h-5" />
            Grade Progression Analysis
          </h3>
          {expandedGrades ? (
            <ChevronDown className="w-5 h-5 text-green-600" />
          ) : (
            <ChevronRight className="w-5 h-5 text-green-600" />
          )}
        </button>

        {expandedGrades && (
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {gradeProgression.map((analysis, index) => (
                <div
                  key={index}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-semibold text-gray-900">
                      {analysis.prospect}
                    </h4>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{
                          backgroundColor: COLORS[index % COLORS.length],
                        }}
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">
                        Overall Grade
                      </span>
                      <span
                        className={`font-bold text-lg ${getGradeColor(analysis.overall)}`}
                      >
                        {analysis.overall}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">
                        Future Value
                      </span>
                      <span
                        className={`font-bold text-lg ${getGradeColor(analysis.futureValue)}`}
                      >
                        {analysis.futureValue}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">
                        Tool Average
                      </span>
                      <span
                        className={`font-semibold ${getGradeColor(analysis.avgGrade)}`}
                      >
                        {analysis.avgGrade}
                      </span>
                    </div>

                    {analysis.strengths.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-700 mb-1">
                          Strengths
                        </h5>
                        <div className="space-y-1">
                          {analysis.strengths.map((strength, idx) => (
                            <div
                              key={idx}
                              className="flex justify-between text-sm"
                            >
                              <span className="text-gray-600">
                                {strength.tool}
                              </span>
                              <span
                                className={`font-semibold ${getGradeColor(strength.grade)}`}
                              >
                                {strength.grade}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {analysis.weaknesses.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-700 mb-1">
                          Areas to Develop
                        </h5>
                        <div className="space-y-1">
                          {analysis.weaknesses.map((weakness, idx) => (
                            <div
                              key={idx}
                              className="flex justify-between text-sm"
                            >
                              <span className="text-gray-600">
                                {weakness.tool}
                              </span>
                              <span
                                className={`font-semibold ${getGradeColor(weakness.grade)}`}
                              >
                                {weakness.grade}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Comparative Analysis */}
            <div className="mt-6 p-4 bg-purple-50 rounded-lg">
              <h4 className="font-semibold text-purple-900 mb-3 flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Comparative Tool Analysis
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h5 className="font-medium text-purple-800 mb-2">
                    Highest Graded Tools
                  </h5>
                  <div className="space-y-1 text-sm">
                    {radarData.map((tool) => {
                      const bestProspect = prospectsWithGrades.reduce(
                        (best, prospect) =>
                          tool[prospect.name] > tool[best.name]
                            ? prospect
                            : best
                      );
                      const bestGrade = tool[bestProspect.name];

                      return (
                        <div key={tool.skill} className="flex justify-between">
                          <span className="text-purple-700">{tool.skill}</span>
                          <span className="font-medium">
                            {bestProspect.name} ({bestGrade})
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <h5 className="font-medium text-purple-800 mb-2">
                    Grade Distribution
                  </h5>
                  <div className="space-y-1 text-sm">
                    {[
                      'Plus (60+)',
                      'Above Avg (55-59)',
                      'Average (45-54)',
                      'Below Avg (<45)',
                    ].map((range, idx) => {
                      const thresholds = [60, 55, 45, 0];
                      const lowerBound = thresholds[idx];
                      const upperBound = idx === 0 ? 100 : thresholds[idx - 1];

                      const count = radarData.reduce((total, tool) => {
                        return (
                          total +
                          prospectsWithGrades.reduce((toolTotal, prospect) => {
                            const grade = tool[prospect.name];
                            return (
                              toolTotal +
                              (grade >= lowerBound && grade < upperBound
                                ? 1
                                : 0)
                            );
                          }, 0)
                        );
                      }, 0);

                      return (
                        <div key={range} className="flex justify-between">
                          <span className="text-purple-700">{range}</span>
                          <span className="font-medium">{count} tools</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Grading Scale Reference */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="flex items-start gap-2">
          <Info className="w-5 h-5 text-gray-600 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="font-semibold text-gray-900 mb-2">
              20-80 Scouting Scale Reference
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div>
                <span className="text-green-600 font-semibold">70-80:</span>{' '}
                Plus to Elite
              </div>
              <div>
                <span className="text-blue-600 font-semibold">55-65:</span>{' '}
                Above Avg to Plus
              </div>
              <div>
                <span className="text-yellow-600 font-semibold">45-55:</span>{' '}
                Average
              </div>
              <div>
                <span className="text-red-600 font-semibold">20-45:</span> Below
                Average
              </div>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              {isPitching
                ? 'Pitching tools: Stuff (velocity/movement), Command (strike zone control), Control (precision), Durability (workload), Delivery (mechanics)'
                : 'Hitting tools: Hit (contact ability), Power (home run capability), Speed (running/basestealing), Field (defensive ability), Arm (throwing strength/accuracy)'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
