"""
Database initialization script for Jarvis
"""
import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis.init")


async def init_database():
    """Initialize database tables"""
    from core.config import load_config, get_config
    from services.memory.service import MemoryService
    
    # Load config
    config = load_config()
    logger.info(f"Using database type: {config.memory.db_type}")
    
    # Create data directory
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    # Initialize memory service
    memory_service = MemoryService()
    await memory_service.initialize()
    
    logger.info("Database initialized successfully")


async def seed_default_data():
    """Seed default data for new installations"""
    from services.memory.service import get_memory_service
    
    memory_service = get_memory_service()
    
    # Add default preferences
    default_preferences = [
        {
            "key": "communication_style",
            "value": "Direct, analytical, no fluff",
            "confidence": 10
        },
        {
            "key": "feedback_style",
            "value": "Brutal honesty, challenge assumptions",
            "confidence": 10
        },
        {
            "key": "working_hours",
            "value": "Flexible, but prefers focused work in morning",
            "confidence": 7
        }
    ]
    
    for pref in default_preferences:
        await memory_service.add_profile_entry(
            key=pref["key"],
            value=pref["value"],
            confidence=pref["confidence"]
        )
    
    # Add default playbooks
    await memory_service.add_playbook(
        name="Daily Standup",
        description="Quick daily check-in workflow",
        steps=[
            {"action": "check_schedule", "description": "Check calendar for today"},
            {"action": "review_tasks", "description": "Review pending tasks"},
            {"action": "prioritize", "description": "Prioritize top 3 tasks"}
        ],
        tags=["daily", "productivity"]
    )
    
    logger.info("Default data seeded")


async def main():
    """Main entry point"""
    import sys
    
    seed = "--seed" in sys.argv
    
    await init_database()
    
    if seed:
        await seed_default_data()
    
    logger.info("Initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
