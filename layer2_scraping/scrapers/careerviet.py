import urllib.parse
from typing import List, Optional
from loguru import logger
from layer2_scraping.base_scraper import BaseScraper, JobPosting

class CareerVietScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = "https://careerviet.vn"

    async def search_jobs(self, keywords: List[str], filters: dict) -> List[str]:
        urls = []
        for keyword in keywords:
            encoded_kw = urllib.parse.quote(keyword)
            search_url = f"{self.base_url}/viec-lam/{encoded_kw}-k-vi.html"
            logger.info(f"Searching CareerViet for: {keyword}")
        return urls

    async def parse_job(self, url: str, page) -> Optional[JobPosting]:
        logger.info(f"Parsing JD from {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded")
            
            # CareerViet DOM elements
            job_title_el = await page.query_selector("h1.title")
            job_title = await job_title_el.inner_text() if job_title_el else "Unknown Title"
            
            company_el = await page.query_selector(".employer-info .name")
            company_name = await company_el.inner_text() if company_el else "Unknown Company"

            desc_el = await page.query_selector(".detail-row")
            description_raw = await desc_el.inner_text() if desc_el else ""

            return JobPosting(
                job_title=job_title,
                company_name=company_name,
                source="careerviet",
                source_url=url,
                description_raw=description_raw
            )
        except Exception as e:
            logger.error(f"Failed to parse CareerViet job {url}: {e}")
            return None
