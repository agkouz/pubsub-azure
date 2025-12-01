# backend/api/metrics.py
from fastapi import APIRouter
from datetime import datetime, timezone

from backend.core import state

router = APIRouter()

@router.get("/metrics")
async def get_metrics():
    """
    Cost monitoring and scaling metrics endpoint.
    
    This endpoint provides real-time cost estimates and scaling recommendations
    based on actual usage patterns. It tells you EXACTLY when to migrate to
    Redis or Azure SignalR.
    
    Returns:
        dict: Comprehensive metrics including:
            - Message statistics (total, daily projection, messages/sec)
            - Cost estimates (operations, free tier usage, monthly cost)
            - Capacity (connections, rooms, active rooms)
            - Scaling recommendation (when to migrate)
            - Thresholds for different solutions
    
    Example Response:
        {
            "daily_messages_projected": 50000,
            "monthly_operations_projected": 3000000,
            "estimated_monthly_cost_usd": 0,
            "free_tier_percent_used": 24,
            "concurrent_connections": 100,
            "recommendation": "✅ CURRENT SOLUTION OPTIMAL",
            "reason": "Under free tier, single instance sufficient",
            "priority": "NONE",
            "thresholds": {
                "redis_at_messages_per_day": 200000,
                "redis_at_concurrent_users": 5000
            }
        }
    
    Use this to:
        - Monitor costs in real-time
        - Know when to scale
        - Plan infrastructure changes
        - Track growth
    """
   uptime_seconds = (datetime.now(timezone.utc) - state.app_start_time).total_seconds()

    if uptime_seconds > 0:
        messages_per_second = state.message_counter / uptime_seconds
        daily_messages = int(messages_per_second * 86400)
    else:
        messages_per_second = 0
        daily_messages = 0

    monthly_operations = daily_messages * 30 * 2  # 2 ops per message
    free_tier = 12_500_000

    if monthly_operations > free_tier:
        estimated_cost = (monthly_operations - free_tier) * 0.05 / 1_000_000
    else:
        estimated_cost = 0.0

    concurrent = len(state.connection_manager.connection_rooms)

    # Recommendation logic (same thresholds)
    if daily_messages > 200_000:
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = "High message volume - Redis has fixed cost ($46/mo)"
        priority = "HIGH"
    elif concurrent > 5_000:
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = "High concurrent users - need multi-instance support"
        priority = "MEDIUM"
    elif estimated_cost > 10:
        recommendation = "🔄 MIGRATE TO REDIS"
        reason = f"Monthly cost ${estimated_cost:.2f} - Redis cheaper at $46/mo"
        priority = "MEDIUM"
    elif concurrent > 1_000:
        recommendation = "⚠️ PREPARE FOR REDIS"
        reason = "Growing concurrent users - plan Redis migration"
        priority = "LOW"
    else:
        recommendation = "✅ CURRENT SOLUTION OPTIMAL"
        reason = "Under free tier, single instance sufficient"
        priority = "NONE"

    return {
        # Statistics
        "total_messages": state.message_counter,
        "uptime_hours": round(uptime_seconds / 3600, 2) if uptime_seconds > 0 else 0,
        "daily_messages_projected": daily_messages,
        "messages_per_second": round(messages_per_second, 2),

        # Costs
        "monthly_operations_projected": monthly_operations,
        "estimated_monthly_cost_usd": round(estimated_cost, 2),
        "free_tier_limit": free_tier,
        "free_tier_remaining": max(0, free_tier - monthly_operations),
        "free_tier_percent_used": (
            round((monthly_operations / free_tier) * 100, 1)
            if monthly_operations < free_tier
            else 100
        ),

        # Capacity
        "concurrent_connections": concurrent,
        "total_rooms": len(state.room_manager.rooms),
        "active_rooms_with_members": len(state.connection_manager.rooms),

        # Scaling
        "recommendation": recommendation,
        "reason": reason,
        "priority": priority,

        # Thresholds
        "thresholds": {
            "redis_at_messages_per_day": 200_000,
            "redis_at_concurrent_users": 5_000,
            "redis_at_monthly_cost": 10,
            "signalr_at_concurrent_users": 100_000,
        },
    }