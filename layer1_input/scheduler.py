import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

scheduler = AsyncIOScheduler()

async def run_weekly_scrape():
    logger.info("Starting weekly scrape task...")
    # This is where we would trigger the scraper pipeline
    # e.g., await VietnamWorksScraper(config).scrape(...)
    logger.info("Weekly scrape completed.")

async def run_daily_trend_update():
    logger.info("Starting daily trend update...")
    # Trigger analytics
    logger.info("Daily trend update completed.")

def setup_scheduler():
    # Schedule every Monday at 2 AM
    scheduler.add_job(run_weekly_scrape, 'cron', day_of_week='mon', hour=2)
    # Schedule every day at 6 AM
    scheduler.add_job(run_daily_trend_update, 'cron', hour=6)
    
    scheduler.start()
    logger.info("Scheduler started.")

if __name__ == "__main__":
    setup_scheduler()
    # Keep the script running
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
