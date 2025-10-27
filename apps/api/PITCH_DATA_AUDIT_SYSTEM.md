# Pitch Data Audit System Documentation

## Overview
A comprehensive audit and monitoring system for detecting and resolving missing pitch data in the prospect database. This system ensures data completeness for accurate composite rankings and player evaluations.

## System Components

### 1. **Quick Audit Report** (`quick_audit_report.py`)
Fast, console-based audit that provides immediate visibility into data coverage.

**Usage:**
```bash
python quick_audit_report.py
```

**Features:**
- Overall coverage statistics (99.7% current coverage!)
- Coverage breakdown by player
- Priority list of players needing collection
- Monthly coverage patterns
- Recent collection activity

### 2. **Comprehensive Audit** (`audit_pitch_data_completeness.py`)
Full audit system with detailed analysis and multiple report formats.

**Usage:**
```bash
python audit_pitch_data_completeness.py
```

**Outputs:**
- JSON report with complete audit data
- CSV file of missing data gaps
- HTML summary report with visualizations

**Features:**
- Identifies critical gaps (high-value prospects with missing data)
- Analyzes collection patterns by month and level
- Generates actionable recommendations
- Tracks recent collection activity

### 3. **Real-time Monitor** (`pitch_data_monitoring_dashboard.py`)
Live dashboard for monitoring collection progress.

**Usage:**
```bash
python pitch_data_monitoring_dashboard.py
```

**Features:**
- Auto-refreshes every 30 seconds
- Shows current collection rate (pitches/second)
- Displays top priority gaps
- Tracks recent activity (last 5 minutes)

### 4. **Scheduled Auditor** (`scheduled_pitch_audit.py`)
Automated audit process for regular monitoring via cron or Task Scheduler.

**Usage:**
```bash
# Basic audit
python scheduled_pitch_audit.py

# With collection trigger
python scheduled_pitch_audit.py --trigger-collection

# Custom output directory
python scheduled_pitch_audit.py --output /path/to/reports
```

**Features:**
- Configurable thresholds for alerts
- Automatic report generation
- Collection triggering for critical gaps
- Alert notifications (can be configured for email/Slack)

### 5. **Collection Scripts**

#### Primary Collection Script (`collect_missing_pitches_final.py`)
Collects missing pitch data for all identified gaps.

**Usage:**
```bash
python collect_missing_pitches_final.py
```

**Features:**
- Prioritizes Leo De Vries and other key players
- Processes 100 players with most missing data
- Collects ~23 pitches/second
- Handles all 2025 season data

## Scheduling

### Windows (Task Scheduler)
Use `run_pitch_audit.bat`:
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily, weekly, etc.)
4. Set action: Start `run_pitch_audit.bat`

### Linux/Mac (Cron)
Use `run_pitch_audit.sh`:
```bash
# Add to crontab (runs daily at 2 AM)
0 2 * * * /path/to/run_pitch_audit.sh >> /var/log/pitch_audit.log 2>&1
```

## Current Status (as of audit)

### Overall Statistics
- **Coverage: 99.7%** (Near perfect!)
- Total games: 10,214
- Games with pitch data: 10,184
- Missing games: 30 (only 0.3%!)
- Total pitches collected: 1,176,776

### Coverage Breakdown
- 735 prospects with 100% coverage
- 288 prospects with 80%+ coverage
- Only 4 prospects with <50% coverage
- 183 prospects with no pitch data (mostly pitchers)

### Key Players Status
- **Leo De Vries**: ✅ FIXED - 118/118 games (100% coverage)
- **Bryce Eldridge**: Data complete (showing data anomaly)
- Other top prospects: Most have complete or near-complete coverage

## Thresholds and Alerts

### Configured Thresholds
- **Coverage Alert**: < 95% overall coverage
- **Missing Games Alert**: > 100 games missing
- **No Data Alert**: > 5 players with 0% coverage

### Alert Responses
1. **LOW_COVERAGE**: Trigger comprehensive collection
2. **MISSING_GAMES**: Run targeted collection for gaps
3. **NO_DATA_PLAYERS**: Priority collection for affected players

## Troubleshooting

### Common Issues

1. **Collection Rate Slow**
   - Check API rate limits
   - Reduce batch size in collection script
   - Run during off-peak hours

2. **Missing Recent Games**
   - Games may not be available immediately
   - Wait 24-48 hours after game completion
   - Check if game data exists in MLB API

3. **Duplicate Data**
   - Unique constraints prevent duplicates
   - Safe to re-run collection scripts

## Maintenance

### Daily Tasks
- Review audit summary
- Check for alerts
- Monitor collection rate

### Weekly Tasks
- Run comprehensive audit
- Review coverage trends
- Update collection priorities

### Monthly Tasks
- Analyze coverage patterns
- Update thresholds if needed
- Clean up old report files

## API Endpoints Integration

The audit system integrates with:
- `/api/composite-rankings` - Uses complete pitch data
- `/api/player-stats` - Provides accurate metrics
- Pitch data aggregator service - Ensures full season coverage

## Success Metrics

Current system achieving:
- ✅ 99.7% data coverage
- ✅ < 1 hour collection time for 100 players
- ✅ Automatic gap detection
- ✅ Leo De Vries and priority players fixed
- ✅ Real-time monitoring capability

## Next Steps

1. **Immediate**: Monitor remaining 30 games for collection
2. **Short-term**: Set up automated daily audits
3. **Long-term**: Integrate with data pipeline for real-time collection

## Contact

For issues or improvements:
- Check audit reports in `./audit_reports/`
- Review logs in `pitch_audit.log`
- Run monitoring dashboard for real-time status