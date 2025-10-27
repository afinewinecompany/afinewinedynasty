import { CompositeRanking } from '@/types/prospect';

/**
 * Calculate percentile rank for a value within a dataset
 * Percentile = (Number of values below + 0.5) / Total number of values * 100
 * This gives us a percentile where 100 = best, 0 = worst
 */
export function calculatePercentileRank(value: number, allValues: number[], higherIsBetter: boolean = true): number {
  // Remove invalid values
  const validValues = allValues.filter(v => v !== null && v !== undefined && !isNaN(v));

  if (validValues.length === 0 || value === null || value === undefined || isNaN(value)) {
    return 0;
  }

  // Count how many values are worse than the current value
  let countWorse = 0;
  let countSame = 0;

  for (const v of validValues) {
    if (higherIsBetter) {
      if (v < value) countWorse++;
      else if (v === value) countSame++;
    } else {
      // For metrics where lower is better (like ERA, whiff rate for batters)
      if (v > value) countWorse++;
      else if (v === value) countSame++;
    }
  }

  // Use mid-point method for ties
  const percentile = ((countWorse + (countSame * 0.5)) / validValues.length) * 100;

  return Math.round(Math.max(0, Math.min(100, percentile)));
}

/**
 * Metrics where higher values are better
 */
const HIGHER_IS_BETTER_METRICS = {
  // Hitter metrics
  'exit_velo_90th': true,
  'hard_hit_rate': true,
  'contact_rate': true,
  'ops': true,
  'batting_avg': true,
  'on_base_pct': true,
  'slugging_pct': true,
  'wrc_plus': true,
  'barrel_rate': true,
  'sweet_spot_rate': true,
  'walk_rate': true,

  // Pitcher metrics
  'avg_fb_velo': true,
  'zone_rate': true,
  'whiff_rate': true, // For pitchers, higher whiff rate is good
  'k_rate': true,
  'k_minus_bb': true,
  'ground_ball_rate': true,
  'swinging_strike_rate': true,

  // Lower is better for these
  'chase_rate': false, // For hitters, lower chase rate is better
  'whiff_rate_batter': false, // For batters, lower whiff rate is better
  'era': false,
  'whip': false,
  'hard_contact_rate': false,
  'barrel_rate_against': false,
  'walk_rate_pitcher': false,
  'hr_per_9': false,
  'fip': false,
};

/**
 * Calculate percentiles for all players and all metrics
 */
export function calculateAllPercentiles(prospects: CompositeRanking[]) {
  const percentileData: Map<number, Record<string, number>> = new Map();

  // First, collect all values for each metric
  const metricValues: Record<string, number[]> = {};

  for (const prospect of prospects) {
    if (!prospect.performance_breakdown?.metrics) continue;

    for (const [metric, value] of Object.entries(prospect.performance_breakdown.metrics)) {
      if (!metricValues[metric]) {
        metricValues[metric] = [];
      }

      if (typeof value === 'number' && !isNaN(value)) {
        metricValues[metric].push(value);
      }
    }
  }

  // Now calculate percentiles for each player
  for (const prospect of prospects) {
    const prospectPercentiles: Record<string, number> = {};

    if (prospect.performance_breakdown?.metrics) {
      for (const [metric, value] of Object.entries(prospect.performance_breakdown.metrics)) {
        if (typeof value === 'number' && !isNaN(value) && metricValues[metric]) {
          // Determine if higher is better for this metric
          // Check if it's a pitcher or hitter based on position
          const isPitcher = ['SP', 'RP', 'P'].includes(prospect.position);
          let higherIsBetter = HIGHER_IS_BETTER_METRICS[metric as keyof typeof HIGHER_IS_BETTER_METRICS];

          // Special handling for whiff_rate (depends on pitcher vs hitter)
          if (metric === 'whiff_rate') {
            higherIsBetter = isPitcher; // For pitchers, higher is better; for hitters, lower is better
          }

          // Default to true if not specified
          if (higherIsBetter === undefined) {
            higherIsBetter = true;
          }

          prospectPercentiles[metric] = calculatePercentileRank(
            value,
            metricValues[metric],
            higherIsBetter
          );
        }
      }
    }

    percentileData.set(prospect.prospect_id, prospectPercentiles);
  }

  return percentileData;
}

/**
 * Calculate composite percentile based on weighted metrics
 */
export function calculateCompositePercentile(
  metrics: Record<string, number>,
  percentiles: Record<string, number>,
  position: string
): number {
  const isPitcher = ['SP', 'RP', 'P'].includes(position);

  // Define weights for different metrics
  const weights = isPitcher ? {
    'avg_fb_velo': 0.25,
    'whiff_rate': 0.25,
    'zone_rate': 0.15,
    'k_minus_bb': 0.20,
    'hard_contact_rate': 0.15,
  } : {
    'exit_velo_90th': 0.25,
    'hard_hit_rate': 0.20,
    'contact_rate': 0.20,
    'whiff_rate': 0.15,
    'chase_rate': 0.10,
    'ops': 0.10,
  };

  let totalWeight = 0;
  let weightedSum = 0;

  for (const [metric, weight] of Object.entries(weights)) {
    const percentile = percentiles[metric];
    if (percentile !== undefined && !isNaN(percentile)) {
      weightedSum += percentile * weight;
      totalWeight += weight;
    }
  }

  if (totalWeight === 0) return 0;

  return Math.round(weightedSum / totalWeight);
}

/**
 * Get percentile color and label
 */
export function getPercentileInfo(percentile: number) {
  if (percentile >= 90) {
    return {
      label: 'Elite',
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
      borderColor: 'border-emerald-200',
      barColor: 'bg-gradient-to-r from-emerald-400 to-green-500',
    };
  } else if (percentile >= 75) {
    return {
      label: 'Plus',
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      barColor: 'bg-gradient-to-r from-green-400 to-green-500',
    };
  } else if (percentile >= 60) {
    return {
      label: 'Above Average',
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
      barColor: 'bg-gradient-to-r from-blue-400 to-blue-500',
    };
  } else if (percentile >= 40) {
    return {
      label: 'Average',
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
      borderColor: 'border-gray-200',
      barColor: 'bg-gray-400',
    };
  } else if (percentile >= 25) {
    return {
      label: 'Below Average',
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      borderColor: 'border-orange-200',
      barColor: 'bg-gradient-to-r from-orange-400 to-orange-500',
    };
  } else {
    return {
      label: 'Poor',
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      barColor: 'bg-gradient-to-r from-red-400 to-red-500',
    };
  }
}

/**
 * Format a metric name for display
 */
export function formatMetricName(metric: string): string {
  const names: Record<string, string> = {
    'exit_velo_90th': '90th %ile Exit Velo',
    'hard_hit_rate': 'Hard Hit Rate',
    'contact_rate': 'Contact Rate',
    'whiff_rate': 'Whiff Rate',
    'whiff_rate_batter': 'Whiff Rate',
    'chase_rate': 'Chase Rate',
    'zone_rate': 'Zone Rate',
    'avg_fb_velo': 'Fastball Velocity',
    'hard_contact_rate': 'Hard Contact',
    'ops': 'OPS',
    'k_minus_bb': 'K-BB%',
    'era': 'ERA',
    'whip': 'WHIP',
    'batting_avg': 'Batting Average',
    'on_base_pct': 'On-Base %',
    'slugging_pct': 'Slugging %',
    'wrc_plus': 'wRC+',
    'barrel_rate': 'Barrel Rate',
    'sweet_spot_rate': 'Sweet Spot Rate',
    'walk_rate': 'Walk Rate',
    'k_rate': 'Strikeout Rate',
    'ground_ball_rate': 'Ground Ball Rate',
    'swinging_strike_rate': 'SwStr Rate',
    'fip': 'FIP',
    'hr_per_9': 'HR/9',
  };

  return names[metric] || metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Format raw value with appropriate units
 */
export function formatMetricValue(metric: string, value: any): string {
  if (value === null || value === undefined) return '--';

  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(numValue)) return '--';

  // Percentage metrics
  if (metric.includes('rate') || metric.includes('pct') || metric === 'k_minus_bb' ||
      metric === 'chase_rate' || metric === 'zone_rate' || metric === 'whiff_rate' ||
      metric === 'contact_rate') {
    return `${numValue.toFixed(1)}%`;
  }

  // Velocity metrics
  if (metric.includes('velo')) {
    return `${numValue.toFixed(1)} mph`;
  }

  // Counting stats with decimals
  if (metric === 'ops' || metric === 'batting_avg' || metric === 'on_base_pct' ||
      metric === 'slugging_pct' || metric === 'whip') {
    return numValue.toFixed(3);
  }

  // ERA, FIP
  if (metric === 'era' || metric === 'fip' || metric === 'hr_per_9') {
    return numValue.toFixed(2);
  }

  // wRC+
  if (metric === 'wrc_plus') {
    return Math.round(numValue).toString();
  }

  // Default
  return numValue.toFixed(1);
}