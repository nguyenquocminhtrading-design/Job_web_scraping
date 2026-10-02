import os
from telegram import Bot
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

async def send_new_job_alert(job_title: str, company: str, salary: str, location: str, url: str, keywords: list):
    if not TOKEN or not CHANNEL_ID:
        logger.warning("Telegram token or channel ID not set. Skipping alert.")
        return
        
    bot = Bot(token=TOKEN)
    message = f"""
🔔 <b>JD MỚI KHỚP KEYWORD!</b>

💼 <b>{job_title}</b> | {company}
📍 {location} | 💰 {salary}
🏷️ Keywords: {', '.join(keywords)}

<a href='{url}'>Xem JD</a>
"""
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
        logger.info(f"Alert sent for job: {job_title}")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
