#!/bin/bash
# Quick collection monitoring script

echo ""
echo "================================================================================"
echo "MiLB PITCHER PITCH COLLECTION MONITOR"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================================"

echo ""
echo "### 2023 Collection ###"
if [ -f "logs/2023_pitcher_collection.log" ]; then
    tail -3 logs/2023_pitcher_collection.log | grep -E "(PROGRESS|Collecting:|COMPLETE)"
else
    echo "  Log file not found"
fi

echo ""
echo "### 2024 Collection ###"
if [ -f "logs/2024_pitcher_collection.log" ]; then
    tail -3 logs/2024_pitcher_collection.log | grep -E "(PROGRESS|Collecting:|COMPLETE)"
else
    echo "  Log file not found"
fi

echo ""
echo "================================================================================"
echo "Run 'bash monitor_collections.sh' to check progress again"
echo "================================================================================"
echo ""
