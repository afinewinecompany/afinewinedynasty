# 2. Data Pipeline

## Historical Data Ingestion

The system processes 15+ years of historical minor league data (~50,000 prospect records) for ML model training:

```
External Sources → Raw Data Ingestion → Data Validation → Feature Engineering → ML Training Data
     ↓                    ↓                    ↓               ↓                    ↓
• MLB Stats API      • Apache Airflow     • Data Quality    • Age Adjustments   • PostgreSQL
• Fangraphs         • Error Handling      • Duplicate       • Rate Statistics    • TimescaleDB
• Baseball America  • Rate Limiting       • Detection       • Level Progression  • Feature Store
```

**Data Sources & Integration:**
- **MLB Stats API**: Free tier, official player data, 1000 requests/day limit
- **Fangraphs**: Web scraping with 1 req/sec rate limiting, scouting grades
- **Baseball America**: Potential partnership for additional scouting data

**Data Processing Pipeline:**
```python
# Apache Airflow DAG structure
prospect_data_pipeline = DAG(
    'prospect_data_ingestion',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1)
)

# Task sequence
extract_mlb_data >> extract_fangraphs_data >> validate_data >>
clean_data >> feature_engineering >> update_rankings >> cache_results
```

## Real-Time Processing

**Daily Update Process:**
1. **6:00 AM ET**: Automated data collection from all sources
2. **6:30 AM ET**: Data validation and deduplication
3. **7:00 AM ET**: ML model inference for updated prospects
4. **7:30 AM ET**: Cache refresh and rankings update
5. **8:00 AM ET**: User notifications for significant changes

**Data Quality Assurance:**
- Schema validation using Pydantic models
- Statistical outlier detection for performance metrics
- Cross-source data consistency checks
- Data freshness monitoring with alerts

---
