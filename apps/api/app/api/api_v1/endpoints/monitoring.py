"""Monitoring and compliance API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, Optional
import logging

from app.services.pipeline_monitoring import (
    create_monitoring_dashboard,
    PerformanceDashboard,
    get_circuit_breaker_metrics
)
from app.services.compliance_scheduler import compliance_scheduler
from app.services.compliance_attribution import ComplianceAuditor
from app.core.circuit_breaker import circuit_breaker_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Global performance dashboard instance
performance_dashboard = PerformanceDashboard()


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_monitoring_dashboard():
    """Get comprehensive monitoring dashboard data."""
    try:
        dashboard_data = create_monitoring_dashboard()
        return {
            "status": "success",
            "data": dashboard_data,
            "message": "Dashboard data retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_metrics(time_range_minutes: int = 60):
    """Get performance metrics for specified time range."""
    try:
        # Collect current metrics
        current_metrics = await performance_dashboard.collect_metrics()

        # Get dashboard data for time range
        dashboard_data = performance_dashboard.get_dashboard_data(time_range_minutes)

        return {
            "status": "success",
            "data": {
                "current_metrics": current_metrics,
                "dashboard": dashboard_data,
                "time_range_minutes": time_range_minutes
            },
            "message": f"Performance metrics for last {time_range_minutes} minutes"
        }
    except Exception as e:
        logger.error(f"Error retrieving performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuit-breakers", response_model=Dict[str, Any])
async def get_circuit_breaker_status():
    """Get status of all circuit breakers."""
    try:
        metrics = get_circuit_breaker_metrics()
        return {
            "status": "success",
            "data": metrics,
            "message": "Circuit breaker status retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error retrieving circuit breaker status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breakers/{breaker_name}/reset", response_model=Dict[str, Any])
async def reset_circuit_breaker(breaker_name: str):
    """Manually reset a specific circuit breaker."""
    try:
        breaker = circuit_breaker_registry.get(breaker_name)
        if not breaker:
            raise HTTPException(status_code=404, detail=f"Circuit breaker '{breaker_name}' not found")

        await breaker.reset()

        return {
            "status": "success",
            "data": {"breaker_name": breaker_name, "state": "reset"},
            "message": f"Circuit breaker '{breaker_name}' reset successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker {breaker_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/status", response_model=Dict[str, Any])
async def get_compliance_status():
    """Get current compliance monitoring status."""
    try:
        status = compliance_scheduler.get_monitoring_status()
        return {
            "status": "success",
            "data": status,
            "message": "Compliance status retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error retrieving compliance status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/check/{check_name}", response_model=Dict[str, Any])
async def run_compliance_check(check_name: str, background_tasks: BackgroundTasks):
    """Run a manual compliance check."""
    try:
        # Validate check name
        valid_checks = [
            'rate_limiting', 'attribution', 'data_retention',
            'tos_compliance', 'cost_monitoring', 'full_audit'
        ]

        if check_name not in valid_checks:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid check name. Valid options: {', '.join(valid_checks)}"
            )

        # Run check in background
        background_tasks.add_task(compliance_scheduler.run_manual_check, check_name)

        return {
            "status": "success",
            "data": {"check_name": check_name, "status": "started"},
            "message": f"Compliance check '{check_name}' started in background"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting compliance check {check_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/report", response_model=Dict[str, Any])
async def generate_compliance_report():
    """Generate comprehensive compliance report."""
    try:
        auditor = ComplianceAuditor()
        report = await auditor.generate_compliance_report()

        return {
            "status": "success",
            "data": report,
            "message": "Compliance report generated successfully"
        }
    except Exception as e:
        logger.error(f"Error generating compliance report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/compliance/interval/{check_name}", response_model=Dict[str, Any])
async def update_compliance_interval(check_name: str, interval_minutes: int):
    """Update the interval for a compliance check."""
    try:
        if interval_minutes < 1:
            raise HTTPException(status_code=400, detail="Interval must be at least 1 minute")

        await compliance_scheduler.update_check_interval(check_name, interval_minutes)

        return {
            "status": "success",
            "data": {
                "check_name": check_name,
                "interval_minutes": interval_minutes
            },
            "message": f"Interval for '{check_name}' updated to {interval_minutes} minutes"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating compliance interval: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/start", response_model=Dict[str, Any])
async def start_compliance_monitoring(background_tasks: BackgroundTasks):
    """Start automated compliance monitoring."""
    try:
        if compliance_scheduler.is_running:
            return {
                "status": "success",
                "data": {"is_running": True},
                "message": "Compliance monitoring is already running"
            }

        # Start monitoring in background
        background_tasks.add_task(compliance_scheduler.start_monitoring)

        return {
            "status": "success",
            "data": {"is_running": True},
            "message": "Compliance monitoring started"
        }
    except Exception as e:
        logger.error(f"Error starting compliance monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/stop", response_model=Dict[str, Any])
async def stop_compliance_monitoring():
    """Stop automated compliance monitoring."""
    try:
        await compliance_scheduler.stop_monitoring()

        return {
            "status": "success",
            "data": {"is_running": False},
            "message": "Compliance monitoring stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping compliance monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health():
    """Get overall system health status."""
    try:
        # Get circuit breaker status
        circuit_breakers = get_circuit_breaker_metrics()

        # Get compliance status
        compliance_status = compliance_scheduler.get_monitoring_status()

        # Get basic performance metrics
        current_metrics = await performance_dashboard.collect_metrics()

        # Determine overall health
        is_healthy = True
        issues = []

        # Check circuit breakers
        for name, metrics in circuit_breakers.items():
            if metrics.get('state') == 'open':
                is_healthy = False
                issues.append(f"Circuit breaker {name} is open")

        # Check compliance monitoring
        if not compliance_status.get('is_running'):
            issues.append("Compliance monitoring is not running")

        # Check system performance
        system_metrics = current_metrics.get('system', {})
        cpu_usage = system_metrics.get('cpu', {}).get('usage_percent', 0)
        memory_usage = system_metrics.get('memory', {}).get('used_percent', 0)

        if cpu_usage > 90:
            is_healthy = False
            issues.append(f"High CPU usage: {cpu_usage:.1f}%")

        if memory_usage > 90:
            is_healthy = False
            issues.append(f"High memory usage: {memory_usage:.1f}%")

        health_status = "healthy" if is_healthy else "degraded"

        return {
            "status": "success",
            "data": {
                "health_status": health_status,
                "is_healthy": is_healthy,
                "issues": issues,
                "circuit_breakers": circuit_breakers,
                "compliance_monitoring": compliance_status['is_running'],
                "system_metrics": {
                    "cpu_usage_percent": cpu_usage,
                    "memory_usage_percent": memory_usage
                }
            },
            "message": f"System health: {health_status}"
        }
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))