'use client';

import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Box,
  Paper,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Switch,
  FormControlLabel,
  Chip,
  Tooltip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  CircularProgress,
  Alert,
  Collapse,
  Button,
  Card,
  CardContent,
  LinearProgress,
  Stack,
  Badge
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  TrendingUp as TrendingUpIcon,
  Refresh as RefreshIcon,
  Bolt as PowerIcon,
  Visibility as DisciplineIcon,
  TouchApp as ContactIcon,
  DirectionsRun as SpeedIcon,
  Psychology as ApproachIcon,
  Star as StarIcon,
  Info as InfoIcon
} from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

interface StatlinePlayer {
  rank: number;
  prospect_id?: number;
  mlb_batter_id: number;
  name: string;
  position?: string;
  age?: number;
  level: string;
  games?: number;
  total_pa: number;
  batting_avg?: number;
  on_base_pct?: number;
  slugging_pct?: number;
  walk_rate?: number;
  strikeout_rate?: number;
  home_run_rate?: number;

  // Composite scores
  discipline_score: number;
  power_score: number;
  overall_score: number;
  adjusted_score: number;

  // Letter grades
  discipline_grade?: string;
  power_grade?: string;
  overall_grade?: string;

  // Additional metrics
  contact_rate?: number;
  chase_rate?: number;
  hard_hit_rate?: number;
  fly_ball_rate?: number;
  age_adjustment?: number;

  // Legacy fields (for backward compatibility)
  skill_scores?: Record<string, any>;
  pitch_metrics?: any;
}

const SKILL_COLORS: Record<string, string> = {
  power: '#ef4444',      // red
  discipline: '#3b82f6',  // blue
  contact: '#10b981',     // green
  speed: '#f59e0b',       // yellow
  approach: '#8b5cf6'     // purple
};

function CompositeBadge({
  label,
  score,
  grade,
  color
}: {
  label: string;
  score: number;
  grade?: string;
  color: string;
}) {
  const getColorFromScore = (score: number) => {
    if (score >= 80) return '#22c55e';  // green
    if (score >= 60) return '#3b82f6';  // blue
    if (score >= 40) return '#f59e0b';  // yellow
    return '#ef4444';  // red
  };

  return (
    <Tooltip
      title={
        <Box>
          <Typography variant="body2">{label}</Typography>
          <Typography variant="caption">
            Score: {score.toFixed(1)}
          </Typography>
        </Box>
      }
    >
      <Badge
        badgeContent={grade || `${Math.round(score)}`}
        sx={{
          '& .MuiBadge-badge': {
            backgroundColor: getColorFromScore(score),
            color: 'white',
            fontWeight: 'bold',
            fontSize: '0.6rem',
            height: '16px',
            minWidth: '20px'
          }
        }}
      >
        <IconComponent
          sx={{
            fontSize: '1.2rem',
            color: SKILL_COLORS[skill]
          }}
        />
      </Badge>
    </Tooltip>
  );
}

function PlayerRow({ player, onExpand, expanded }: {
  player: StatlinePlayer;
  onExpand: () => void;
  expanded: boolean;
}) {
  const router = useRouter();

  const getAgeIndicator = () => {
    const adjustment = player.age_adjustment;
    if (adjustment > 0.05) {
      return (
        <Tooltip title="Older than average for level">
          <Chip label="Old" size="small" color="warning" sx={{ height: 20 }} />
        </Tooltip>
      );
    } else if (adjustment < -0.05) {
      return (
        <Tooltip title="Younger than average for level">
          <Chip label="Young" size="small" color="success" sx={{ height: 20 }} />
        </Tooltip>
      );
    }
    return null;
  };

  const formatTripleSlash = () => {
    const avg = player.batting_avg ? (player.batting_avg / 100).toFixed(3) : '.000';
    const obp = player.on_base_pct ? (player.on_base_pct / 100).toFixed(3) : '.000';
    const slg = player.slugging_pct ? (player.slugging_pct / 100).toFixed(3) : '.000';
    return `${avg}/${obp}/${slg}`;
  };

  return (
    <>
      <TableRow hover sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell component="th" scope="row">
          <Typography variant="h6" fontWeight="bold" color="primary">
            #{player.rank}
          </Typography>
        </TableCell>
        <TableCell>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography
              variant="body1"
              fontWeight="medium"
              sx={{
                cursor: player.prospect_id ? 'pointer' : 'default',
                '&:hover': player.prospect_id ? { color: 'primary.main', textDecoration: 'underline' } : {}
              }}
              onClick={() => player.prospect_id && router.push(`/prospects/${player.prospect_id}`)}
            >
              {player.name}
            </Typography>
            {getAgeIndicator()}
          </Box>
          <Typography variant="caption" color="textSecondary">
            {player.position || 'N/A'} | Age {player.age || 'N/A'} | {player.level}
          </Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body2" fontWeight="medium">
            {formatTripleSlash()}
          </Typography>
          <Typography variant="caption" color="textSecondary">
            {player.games || 0}G / {player.total_pa}PA
          </Typography>
        </TableCell>
        <TableCell>
          <Stack direction="row" spacing={1}>
            <CompositeBadge
              label="Discipline"
              score={player.discipline_score}
              grade={player.discipline_grade}
              color={SKILL_COLORS.discipline}
            />
            <CompositeBadge
              label="Power"
              score={player.power_score}
              grade={player.power_grade}
              color={SKILL_COLORS.power}
            />
          </Stack>
        </TableCell>
        <TableCell align="center">
          <Box>
            <Typography variant="h5" fontWeight="bold" color="primary">
              {player.overall_grade || Math.round(player.adjusted_score)}
            </Typography>
            <Typography variant="caption" color="textSecondary">
              Overall
            </Typography>
          </Box>
        </TableCell>
        <TableCell>
          <IconButton size="small" onClick={onExpand}>
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={6} sx={{ py: 0 }}>
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ p: 3 }}>
              <Grid container spacing={3}>
                {/* Composite Scores */}
                <Grid item xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        Composite Scores
                      </Typography>

                      {/* Discipline Score */}
                      <Box mb={3}>
                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                          <Typography variant="body2" fontWeight="medium">
                            Discipline
                          </Typography>
                          <Typography variant="body2" color="primary" fontWeight="bold">
                            {player.discipline_grade} ({player.discipline_score.toFixed(0)})
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={player.discipline_score}
                          sx={{
                            height: 10,
                            borderRadius: 5,
                            backgroundColor: '#e0e0e0',
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 5,
                              background: `linear-gradient(90deg, ${SKILL_COLORS.discipline}88, ${SKILL_COLORS.discipline})`
                            }
                          }}
                        />
                        <Box mt={1}>
                          <Typography variant="caption" color="textSecondary">
                            Contact: {player.contact_rate?.toFixed(0) || 'N/A'}% |
                            Chase: {player.chase_rate?.toFixed(0) || 'N/A'}% |
                            Walk: {player.walk_rate?.toFixed(1) || 'N/A'}%
                          </Typography>
                        </Box>
                      </Box>

                      {/* Power Score */}
                      <Box mb={3}>
                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                          <Typography variant="body2" fontWeight="medium">
                            Power
                          </Typography>
                          <Typography variant="body2" color="primary" fontWeight="bold">
                            {player.power_grade} ({player.power_score.toFixed(0)})
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={player.power_score}
                          sx={{
                            height: 10,
                            borderRadius: 5,
                            backgroundColor: '#e0e0e0',
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 5,
                              background: `linear-gradient(90deg, ${SKILL_COLORS.power}88, ${SKILL_COLORS.power})`
                            }
                          }}
                        />
                        <Box mt={1}>
                          <Typography variant="caption" color="textSecondary">
                            Hard Hit: {player.hard_hit_rate?.toFixed(0) || 'N/A'}% |
                            Fly Ball: {player.fly_ball_rate?.toFixed(0) || 'N/A'}% |
                            HR Rate: {player.home_run_rate?.toFixed(1) || 'N/A'}%
                          </Typography>
                        </Box>
                      </Box>

                      {/* Overall Score */}
                      <Box>
                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                          <Typography variant="body2" fontWeight="medium">
                            Overall (Age Adjusted)
                          </Typography>
                          <Typography variant="body2" color="primary" fontWeight="bold">
                            {player.overall_grade} ({player.adjusted_score.toFixed(0)})
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={player.adjusted_score}
                          sx={{
                            height: 10,
                            borderRadius: 5,
                            backgroundColor: '#e0e0e0',
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 5,
                              background: 'linear-gradient(90deg, #6366f188, #6366f1)'
                            }
                          }}
                        />
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>

                {/* Advanced Stats */}
                <Grid item xs={12} md={6}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        Advanced Metrics
                      </Typography>
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              Batting Avg
                            </Typography>
                            <Typography variant="h6">
                              {player.batting_avg ? (player.batting_avg / 100).toFixed(3) : '.000'}
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              OBP
                            </Typography>
                            <Typography variant="h6">
                              {player.on_base_pct ? (player.on_base_pct / 100).toFixed(3) : '.000'}
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              SLG
                            </Typography>
                            <Typography variant="h6">
                              {player.slugging_pct ? (player.slugging_pct / 100).toFixed(3) : '.000'}
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              Walk Rate
                            </Typography>
                            <Typography variant="h6">
                              {player.walk_rate?.toFixed(1) || '0.0'}%
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              K Rate
                            </Typography>
                            <Typography variant="h6">
                              {player.strikeout_rate?.toFixed(1) || '0.0'}%
                            </Typography>
                          </Box>
                        </Grid>
                        <Grid item xs={6}>
                          <Box mb={2}>
                            <Typography variant="caption" color="textSecondary">
                              HR Rate
                            </Typography>
                            <Typography variant="h6">
                              {player.home_run_rate?.toFixed(1) || '0.0'}%
                            </Typography>
                          </Box>
                        </Grid>
                      </Grid>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export default function StatlinePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rankings, setRankings] = useState<StatlinePlayer[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  // Filters
  const [level, setLevel] = useState<string>('');
  const [minPA, setMinPA] = useState<number>(100);
  const [includePitchData, setIncludePitchData] = useState(true);
  const [season] = useState(2025);

  // Sorting
  const [orderBy, setOrderBy] = useState<string>('rank');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');

  useEffect(() => {
    const controller = new AbortController();

    const fetchRankingsWithAbort = async () => {
      await fetchRankings(controller.signal);
    };

    fetchRankingsWithAbort();

    // Cleanup function to abort request if component unmounts
    return () => {
      controller.abort('Component unmounted');
    };
  }, [level, minPA, includePitchData]);

  const fetchRankings = async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        min_pa: minPA.toString(),
        season: season.toString(),
        include_pitch_data: includePitchData.toString()
      });

      if (level) {
        params.append('level', level);
      }

      // Use longer timeout for complex statline queries
      const response = await api.get(
        `/prospects/rankings/statline?${params}`,
        undefined, // no caching
        { timeout: 60000, signal } // 60 seconds timeout with abort signal
      );
      setRankings(response.rankings || []);
    } catch (err: any) {
      // Don't show error if request was aborted due to component unmount
      if (err.name === 'AbortError' || err.message?.includes('Component unmounted')) {
        return;
      }

      console.error('Error fetching statline rankings:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load rankings');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (property: string) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const toggleRowExpanded = (playerId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(playerId)) {
      newExpanded.delete(playerId);
    } else {
      newExpanded.add(playerId);
    }
    setExpandedRows(newExpanded);
  };

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h3" component="h1" gutterBottom fontWeight="bold">
            Statline Rankings
          </Typography>
          <Typography variant="body1" color="textSecondary">
            Performance-based prospect rankings using in-season statistics and advanced metrics
          </Typography>
        </Box>
        <IconButton
          onClick={fetchRankings}
          disabled={loading}
          size="large"
          color="primary"
        >
          <RefreshIcon />
        </IconButton>
      </Box>

      {/* Info Alert */}
      <Alert severity="info" sx={{ mb: 3 }} icon={<InfoIcon />}>
        Rankings combine traditional stats with pitch-level data to create skill-based scores.
        Players are compared to peers at their level with age adjustments applied.
      </Alert>

      {/* Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Filters</Typography>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Level</InputLabel>
              <Select
                value={level}
                label="Level"
                onChange={(e) => setLevel(e.target.value)}
              >
                <MenuItem value="">All Levels</MenuItem>
                <MenuItem value="AAA">Triple-A</MenuItem>
                <MenuItem value="AA">Double-A</MenuItem>
                <MenuItem value="A+">High-A</MenuItem>
                <MenuItem value="A">Low-A</MenuItem>
                <MenuItem value="ROK">Rookie</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={4}>
            <Box>
              <Typography gutterBottom>
                Min Plate Appearances: {minPA}
              </Typography>
              <Slider
                value={minPA}
                onChange={(e, val) => setMinPA(val as number)}
                min={50}
                max={500}
                step={50}
                marks={[
                  { value: 50, label: '50' },
                  { value: 200, label: '200' },
                  { value: 350, label: '350' },
                  { value: 500, label: '500' }
                ]}
                valueLabelDisplay="auto"
              />
            </Box>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={includePitchData}
                  onChange={(e) => setIncludePitchData(e.target.checked)}
                  color="primary"
                />
              }
              label="Include Pitch Metrics"
            />
          </Grid>

          <Grid item xs={12} sm={6} md={2}>
            <Chip
              label={`${season} Season`}
              color="primary"
              variant="outlined"
              icon={<TrendingUpIcon />}
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Rankings Table */}
      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress size={60} />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : rankings.length === 0 ? (
        <Alert severity="warning">
          No players found matching the criteria. Try adjusting the filters.
        </Alert>
      ) : (
        <Paper>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>
                    <TableSortLabel
                      active={orderBy === 'rank'}
                      direction={orderBy === 'rank' ? order : 'asc'}
                      onClick={() => handleSort('rank')}
                    >
                      Rank
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>Player</TableCell>
                  <TableCell>Triple Slash</TableCell>
                  <TableCell>Skill Scores</TableCell>
                  <TableCell align="center">
                    <TableSortLabel
                      active={orderBy === 'adjusted_percentile'}
                      direction={orderBy === 'adjusted_percentile' ? order : 'asc'}
                      onClick={() => handleSort('adjusted_percentile')}
                    >
                      Overall
                    </TableSortLabel>
                  </TableCell>
                  <TableCell></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rankings.map((player) => (
                  <PlayerRow
                    key={player.mlb_player_id}
                    player={player}
                    expanded={expandedRows.has(player.mlb_player_id)}
                    onExpand={() => toggleRowExpanded(player.mlb_player_id)}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}
    </Container>
  );
}