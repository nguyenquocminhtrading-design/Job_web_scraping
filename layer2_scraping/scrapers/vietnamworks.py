"""
VietnamWorks sử dụng Next.js React Server Components (RSC) streaming.
Data được đẩy qua self.__next_f.push([1, "..."]) thay vì __NEXT_DATA__.
Ta dùng httpx để lấy HTML tĩnh (fast, no JS needed) rồi
dùng regex + json để bóc tách các cục data JSON nhúng trong đó.
"""
import re
import json
import urllib.parse
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from loguru import logger
import httpx

from layer2_scraping.base_scraper import BaseScraper, JobPosting


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class VietnamWorksScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = "https://www.vietnamworks.com"

    # ------------------------------------------------------------------ #
    # LAYER 1: Tìm URL các job từ trang kết quả tìm kiếm
    # ------------------------------------------------------------------ #
    async def search_jobs(self, page, keywords: List[str], filters: dict) -> List[str]:
        urls = []
        for keyword in keywords:
            encoded_kw = urllib.parse.quote(keyword)
            search_url = f"{self.base_url}/viec-lam?q={encoded_kw}"
            logger.info(f"Searching VietnamWorks: {keyword} → {search_url}")

            try:
                await page.goto(search_url, wait_until="networkidle")
                await page.wait_for_timeout(3000)

                # Lấy thẻ <a href="...jv"> — link dẫn tới trang chi tiết JD
                elements = await page.query_selector_all("a[href*='-jv']")
                for el in elements:
                    href = await el.get_attribute("href")
                    if href and "-jv" in href:
                        # Bỏ query string để tránh trùng
                        clean = href.split("?")[0]
                        full_url = clean if clean.startswith("http") else f"{self.base_url}{clean}"
                        if full_url not in urls:
                            urls.append(full_url)

                logger.info(f"Found {len(urls)} URLs so far after keyword '{keyword}'")
            except Exception as e:
                logger.error(f"Error searching '{keyword}': {e}")

        return urls

    # ------------------------------------------------------------------ #
    # LAYER 2: Parse 1 trang JD — dùng httpx (nhanh, không cần JS)
    # VietnamWorks nhúng data vào RSC streaming: self.__next_f.push([1,"..."])
    # ------------------------------------------------------------------ #
    async def parse_job(self, url: str, page) -> Optional[JobPosting]:
        logger.info(f"Parsing: {url}")
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                return None

            # Decode với encoding chuẩn (utf-8), fallback utf-8-sig
            try:
                html = resp.content.decode('utf-8')
            except UnicodeDecodeError:
                html = resp.content.decode('utf-8-sig', errors='replace')

            data = self._extract_from_rsc(html)

            if not data:
                logger.warning(f"RSC extraction failed for {url}, falling back to meta tags")
                data = self._extract_from_meta(html)

            if not data:
                return None

            return JobPosting(
                job_title       = data.get("job_title", "Unknown"),
                company_name    = data.get("company_name", "Unknown Company"),
                source          = "vietnamworks",
                source_url      = url,
                location        = data.get("location"),
                salary          = data.get("salary"),
                description_raw = data.get("description_raw", ""),
                benefits_raw    = data.get("benefits_raw", ""),
                skills_raw      = data.get("skills_raw", []),
                posted_date     = data.get("posted_date"),
                deadline        = data.get("deadline"),
                education       = data.get("education"),
                experience      = data.get("experience"),
            )

        except Exception as e:
            logger.error(f"parse_job failed for {url}: {e}")
            return None

    # ------------------------------------------------------------------ #
    # HELPER: Bóc tách từ RSC streaming JSON
    # ------------------------------------------------------------------ #
    def _extract_from_rsc(self, html: str) -> Optional[Dict[str, Any]]:
        """
        VietnamWorks dùng Next.js RSC. Data được push qua:
          self.__next_f.push([1, "..."])
        Ta nối tất cả các chuỗi đó lại và regex tìm các object JSON quan trọng.
        """
        # Gom toàn bộ payload RSC
        chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
        if not chunks:
            return None

        # Unescape từng chunk — dùng json.loads để handle \uXXXX đúng chuẩn
        rsc_payload = ""
        for c in chunks:
            try:
                rsc_payload += json.loads(f'"{c}"')
            except Exception:
                rsc_payload += c

        result: Dict[str, Any] = {}

        # ---- Tên job ----
        m_title = re.search(r'"jobTitle"\s*:\s*"([^"]+)"', rsc_payload)
        if m_title:
            result["job_title"] = m_title.group(1)

        # ---- Tên công ty ----
        m = re.search(r'"companyName"\s*:\s*"([^"]+)"', rsc_payload)
        if m:
            result["company_name"] = m.group(1)

        # ---- Địa điểm ----
        m_city = re.search(r'"cityNameVI"\s*:\s*"([^"]+)"', rsc_payload)
        m_addr = re.search(r'"address"\s*:\s*"([^"]+)"', rsc_payload)
        if m_city or m_addr:
            result["location"] = {
                "city": m_city.group(1) if m_city else "",
                "address": m_addr.group(1) if m_addr else "",
            }

        # ---- Mô tả công việc (HTML → plain text) ----
        # VietnamWorks encode HTML trong JSON string: \u003cp\u003e = <p>
        desc_match = re.search(r'"T\d+,(\\u003cp\\u003e.*?)"(?=\d+[:\{])', rsc_payload, re.DOTALL)
        if not desc_match:
            # Thử pattern khác: T632, hoặc T515, etc.
            desc_match = re.search(r'T\d+,((?:\\u003c|<)p(?:\\u003e|>).*?)(?=\d+[:\{T])', rsc_payload, re.DOTALL)
        if desc_match:
            raw_desc = desc_match.group(1)
            # Unescape unicode
            try:
                raw_desc = raw_desc.encode('utf-8').decode('unicode_escape')
            except Exception:
                pass
            soup = BeautifulSoup(raw_desc, "html.parser")
            result["description_raw"] = soup.get_text(separator="\n").strip()

        # ---- Kỹ năng (skills) ----
        skills_raw = re.findall(r'"skillName"\s*:\s*"([^"]+)"', rsc_payload)
        if skills_raw:
            result["skills_raw"] = skills_raw

        # ---- Quyền lợi (benefits) ----
        benefits_raw = re.findall(r'"benefitValue"\s*:\s*"([^"]+)"', rsc_payload)
        if benefits_raw:
            result["benefits_raw"] = " | ".join(benefits_raw)

        # ---- Ngày đăng / hết hạn ----
        posted_m = re.search(r'"startOn"\s*:\s*"([^"]+)"', rsc_payload)
        expired_m = re.search(r'"expiredOn"\s*:\s*"([^"]+)"', rsc_payload)
        if posted_m:
            result["posted_date"] = posted_m.group(1)
        if expired_m:
            result["deadline"] = expired_m.group(1)

        return result if result else None

    # ------------------------------------------------------------------ #
    # HELPER: Fallback — bóc tách từ thẻ <meta> nếu RSC thất bại
    # ------------------------------------------------------------------ #
    def _extract_from_meta(self, html: str) -> Optional[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        result: Dict[str, Any] = {}

        title_tag = soup.find("title")
        if title_tag:
            # "Tuyển Nhân Viên Kế Toán Tổng Hợp tại Công Ty XYZ T10/2026"
            raw_title = title_tag.string or ""
            # Tách tên job và tên công ty
            if " tại " in raw_title:
                parts = raw_title.split(" tại ", 1)
                result["job_title"] = parts[0].replace("Tuyển ", "").strip()
                # Bỏ phần " T10/2026" ở cuối
                company_part = re.sub(r'\s+T\d{1,2}/\d{4}$', '', parts[1]).strip()
                result["company_name"] = company_part
            else:
                result["job_title"] = raw_title.strip()

        desc_tag = soup.find("meta", {"name": "description"})
        if desc_tag:
            result["description_raw"] = desc_tag.get("content", "")

        return result if result else None
