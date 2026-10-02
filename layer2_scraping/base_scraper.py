import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random

@dataclass
class JobPosting:
    job_title: str
    company_name: str
    source: str
    source_url: str
    job_title_normalized: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[Dict[str, str]] = None
    salary: Optional[Dict[str, Any]] = None
    experience: Optional[Dict[str, Any]] = None
    education: Optional[str] = None
    level: Optional[str] = None
    skills_raw: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    benefits_raw: Optional[str] = None
    description_raw: Optional[str] = None
    posted_date: Optional[str] = None
    deadline: Optional[str] = None

class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.delay_min = config.get("scraping", {}).get("delay_min", 2)
        self.delay_max = config.get("scraping", {}).get("delay_max", 5)

    def _get_random_ua(self):
        # Fallback list if fake-useragent is not used or initialized yet
        uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        ]
        return random.choice(uas)

    @abstractmethod
    async def search_jobs(self, page, keywords: List[str], filters: dict) -> List[str]:
        """Return list of job URLs"""
        pass

    @abstractmethod
    async def parse_job(self, url: str, page) -> Optional[JobPosting]:
        """Parse a single job page"""
        pass

    async def _polite_delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.debug(f"Polite delay: sleeping for {delay:.2f} seconds")
        await asyncio.sleep(delay)

    @retry(stop=stop_after_attempt(3), wait=wait_random(min=2, max=5))
    async def scrape(self, keywords: List[str], filters: dict) -> List[JobPosting]:
        results = []
        logger.info(f"Starting scrape with keywords: {keywords}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self._get_random_ua(),
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            try:
                urls = await self.search_jobs(page, keywords, filters)
                logger.info(f"Found {len(urls)} job URLs to parse.")
                for url in urls:
                    await self._polite_delay()
                    try:
                        job = await self.parse_job(url, page)
                        if job:
                            results.append(job)
                            logger.info(f"Successfully parsed job: {job.job_title} at {job.company_name}")
                    except Exception as e:
                        logger.error(f"Error parsing job at {url}: {e}")
            finally:
                await browser.close()
                
        return results
