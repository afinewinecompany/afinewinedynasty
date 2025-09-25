# API Testing Suite for A Fine Wine Dynasty

This directory contains comprehensive API validation scripts for testing all external data sources required by the A Fine Wine Dynasty platform.

## 🎯 Critical Issues Being Addressed

Based on the PO Master Checklist validation, these scripts resolve the 3 CRITICAL blocking issues:

1. **❌ Missing Fangraphs Integration Strategy** → ✅ FanGraphs scraping validation
2. **❌ Fantrax OAuth Implementation Gap** → ✅ Fantrax API comprehensive testing
3. **❌ MLB Training → Inference Sequence Risk** → ✅ MLB API data quality assessment

## 📁 Files Overview

### Core Testing Scripts
- **`api_validation_suite.py`** - Comprehensive testing of all 3 APIs
- **`fantrax_integration_test.py`** - Detailed Fantrax API integration testing
- **`requirements_api_validation.txt`** - Python dependencies

### Execution Files
- **`run_api_tests.bat`** - Windows batch file to run all tests
- **`README_API_TESTING.md`** - This documentation

## 🚀 Quick Start

### Option 1: Windows Batch Execution
```bash
# Run all tests automatically
./run_api_tests.bat
```

### Option 2: Manual Python Execution
```bash
# Install requirements
pip install -r requirements_api_validation.txt

# Run comprehensive test suite
python api_validation_suite.py

# Run detailed Fantrax testing
python fantrax_integration_test.py
```

## 📊 What Gets Tested

### MLB Stats API Testing
- ✅ Basic connectivity and response times
- ✅ Minor league prospect data availability
- ✅ Rate limiting behavior and constraints
- ✅ Data completeness analysis for ML training
- ✅ Prospect search capabilities

### Fantrax API Testing (Based on v1.2 Documentation)
- ✅ **Public Endpoints** (no auth required):
  - `getPlayerIds` - Player identification mapping
  - `getAdp` - Average Draft Position data
- ✅ **Authenticated Endpoints** (requires User Secret ID):
  - `getLeagues` - User's league list
  - `getLeagueInfo` - League configuration and team data
  - `getTeamRosters` - Dynasty roster information
  - `getDraftPicks` - Future draft picks
  - `getDraftResults` - Draft history
  - `getStandings` - League standings

### FanGraphs Scraping Testing
- ✅ Site accessibility and response times
- ✅ Prospect page structure analysis
- ✅ Data extraction capabilities (tables, rankings, scouting grades)
- ✅ Rate limiting best practices (2-second delays)
- ✅ Legal compliance (`robots.txt` analysis)

## 🔐 Authentication Requirements

### Fantrax API
To test authenticated endpoints, you need your **User Secret ID**:
1. Log into Fantrax.com
2. Go to your User Profile screen
3. Find the "Secret ID" field
4. Use this ID when prompted by the test script

**Note**: Without the Secret ID, only public endpoints will be tested.

## 📈 Expected Outcomes

### Success Scenarios
```
✅ MLB API: Ready for integration
✅ Fantrax API: Ready for integration
✅ FanGraphs: Scraping possible with proper rate limiting
```

### Partial Success
```
⚠️ MLB API: Available but rate limited
⚠️ Fantrax API: Public endpoints only
⚠️ FanGraphs: Limited scraping capability
```

### Failure Scenarios
```
❌ MLB API: Connectivity issues
❌ Fantrax API: Authentication failures
❌ FanGraphs: Site blocking or restrictions
```

## 📄 Output Files

After running tests, you'll get:
- **`api_validation_results.json`** - Complete test results in JSON format
- **`fantrax_api_results_TIMESTAMP.json`** - Detailed Fantrax testing results
- **Console output** - Human-readable summary and recommendations

## 🎯 Integration Decision Tree

Based on test results, follow this decision path:

### If All APIs Pass ✅
- **Action**: Proceed with all Epic stories as planned
- **Timeline**: Original 6-month development timeline
- **Risk**: LOW

### If Fantrax API Fails ❌
- **Action**: Implement manual CSV roster import as fallback
- **Impact**: Reduced premium user experience
- **Timeline**: Add 1 week for alternative implementation

### If FanGraphs Scraping Blocked 🚫
- **Action**: Focus on MLB API + Baseball Savant data only
- **Impact**: Reduced ML model accuracy (-20%)
- **Timeline**: Simplified data pipeline (-1 week)

### If MLB API Issues ⚠️
- **Action**: Investigate alternative data sources
- **Impact**: Core functionality at risk
- **Timeline**: +2 weeks for alternative data sources

## 🔄 Next Steps After Testing

1. **Review Results**: Analyze all API test outputs
2. **Update PRD**: Revise Story 2.4 and 4.3 based on findings
3. **Architecture Adjustments**: Modify data pipeline design for confirmed APIs
4. **Legal Review**: Ensure compliance with all terms of service
5. **Begin Development**: Start Epic 1 with confirmed API constraints

## 📞 Support

If tests reveal unexpected issues:
1. Check network connectivity and firewall settings
2. Verify API endpoint URLs haven't changed
3. Review rate limiting and retry logic
4. Consider running tests from different IP addresses

## ⚖️ Legal Considerations

- **FanGraphs**: Respect robots.txt and implement polite scraping (2+ second delays)
- **MLB API**: Review terms for commercial use limitations
- **Fantrax**: Ensure user consent for accessing league data

Remember: Proper attribution and respectful usage of all data sources is required.