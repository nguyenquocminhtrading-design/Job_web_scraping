"""
VietnamWorks dùng Next.js React Server Components (RSC) streaming.
Data được đẩy qua self.__next_f.push([1, "..."]) thay vì __NEXT_DATA__.

Chiến lược parse (row-based):
  1. httpx lấy HTML tĩnh (nhanh, không cần JS).
  2. Nối các chunk RSC thành payload liền mạch.
  3. Scan tuần tự từng ROW của flight stream theo format `ID:<type><content>`:
     - JSON row ({...} / [...]) -> decode bằng json.JSONDecoder.raw_decode
     - Text row  (T<hexlen>,...) -> cắt tại marker row kế tiếp
  4. Resolve tham chiếu "$xx" từ DUY NHẤT một job object.
     Payload thường xuất hiện 2 lần trong stream; resolve từ 1 object
     giúp khử trùng lặp skills/benefits/description tự nhiên.
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

# Marker bắt đầu một row flight: `26:{`, `29:[`, `b:["`, `23:T...`
ROW_MARK = re.compile(r"[0-9a-f]{1,4}:(?=[{[\"T$])")
ROW_HEAD = re.compile(r"([0-9a-f]{1,4}):")
JSON_DECODER = json.JSONDecoder()
# Tham chiếu flight: "$29", "$L16", ...
REF_PAT = re.compile(r"^\$[0-9a-zA-Z]{1,6}$")


def _join_rsc_chunks(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
    payload = ""
    for c in chunks:
        try:
            payload += json.loads(f'"{c}"')
        except Exception:
            payload += c
    return payload


def _parse_rows(payload: str) -> Dict[str, Any]:
    """Scan tuần tự các row của flight stream.

    JSON row được raw_decode đúng ranh giới (kể cả khi các row dính liền
    nhau như `...</p>2a:{...}`). Text row (T) kết thúc tại marker kế tiếp.
    """
    rows: Dict[str, Any] = {}
    pos, n = 0, len(payload)
    while pos < n:
        while pos < n and payload[pos] in "\r\n\t ":
            pos += 1
        if pos >= n:
            break
        m = ROW_HEAD.match(payload, pos)
        if not m:
            nxt = ROW_MARK.search(payload, pos)
            if not nxt:
                break
            pos = nxt.start()
            continue
        row_id = m.group(1)
        p = m.end()

        # JSON row: { ... } hoặc [ ... ]
        if payload[p:p + 1] in "{[":
            try:
                obj, end = JSON_DECODER.raw_decode(payload, p)
                rows[row_id] = obj
                pos = end
                continue
            except json.JSONDecodeError:
                pass

        # Text row: T<hexlen>,<nội dung tự do tới row kế>
        if payload[p:p + 1] == "T":
            m2 = re.match(r"T[0-9a-f]+,", payload[p:p + 16])
            if m2:
                text_start = p + m2.end()
                nxt = ROW_MARK.search(payload, text_start)
                text_end = nxt.start() if nxt else n
                rows[row_id] = ("T", payload[text_start:text_end])
                pos = text_end
                continue

        # Row kiểu khác (H, I, L, X, S...): thử decode JSON sau prefix type
        m3 = re.match(r"(?:HL|H[0-9a-z]*|I[0-9a-z]*|X[0-9a-z]*|S[0-9a-z]*)", payload[p:p + 8])
        if m3:
            q = p + m3.end()
            if payload[q:q + 1] in "{[\"":
                try:
                    obj, end = JSON_DECODER.raw_decode(payload, q)
                    rows[row_id] = obj
                    pos = end
                    continue
                except json.JSONDecodeError:
                    pass

        # Không nhận dạng được: nhảy tới marker kế
        nxt = ROW_MARK.search(payload, p)
        pos = nxt.start() if nxt else n
    return rows


def _resolve_ref(rows: Dict[str, Any], ref: Any, depth: int = 0) -> Any:
    """Resolve tham chiếu flight '$xx' / '$Lxx' và các mảng/dict chứa ref."""
    if depth > 6:
        return ref
    if isinstance(ref, str) and REF_PAT.match(ref):
        val = rows.get(ref[1:].lstrip("L"))
        if val is None:
            return None
        if isinstance(val, tuple):  # text row
            return val[1]
        return _resolve_ref(rows, val, depth + 1)
    if isinstance(ref, list):
        return [_resolve_ref(rows, x, depth + 1) for x in ref]
    if isinstance(ref, dict):
        return {k: _resolve_ref(rows, v, depth + 1) for k, v in ref.items()}
    return ref


def _html_to_text(fragment: str) -> str:
    return BeautifulSoup(fragment, "html.parser").get_text(separator="\n").strip()


class VietnamWorksScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = "https://www.vietnamworks.com"

    # ------------------------------------------------------------------ #
    # LAYER 1: Tìm URL các job từ trang kết quả tìm kiếm
    # ------------------------------------------------------------------ #
    async def search_jobs(self, page, keywords: List[str], filters: dict) -> List[str]:
        urls: List[str] = []
        max_pages = int(self.config.get("scraping", {}).get("max_pages", 1))
        for keyword in keywords:
            encoded_kw = urllib.parse.quote(keyword)
            seen_before = len(urls)
            for page_num in range(1, max_pages + 1):
                search_url = f"{self.base_url}/viec-lam?q={encoded_kw}"
                if page_num > 1:
                    search_url += f"&page={page_num}"
                logger.info(f"Searching VietnamWorks: {keyword} (page {page_num}/{max_pages})")

                try:
                    await page.goto(search_url, wait_until="networkidle")
                    await page.wait_for_timeout(3000)

                    # Lấy thẻ <a href="...jv"> — link dẫn tới trang chi tiết JD
                    elements = await page.query_selector_all("a[href*='-jv']")
                    new_links = 0
                    for el in elements:
                        href = await el.get_attribute("href")
                        if href and "-jv" in href:
                            # Bỏ query string để tránh trùng
                            clean = href.split("?")[0]
                            full_url = clean if clean.startswith("http") else f"{self.base_url}{clean}"
                            if full_url not in urls:
                                urls.append(full_url)
                                new_links += 1

                    logger.info(f"Keyword '{keyword}' page {page_num}: +{new_links} URLs (total {len(urls)})")
                    # Hết kết quả trang này -> đừng thử các trang sau
                    if new_links == 0:
                        break
                except Exception as e:
                    logger.error(f"Error searching '{keyword}' page {page_num}: {e}")
                    break

            logger.info(f"Keyword '{keyword}': tổng cộng {len(urls) - seen_before} URLs")
        return urls

    # ------------------------------------------------------------------ #
    # LAYER 2: Parse 1 trang JD — httpx (nhanh, không cần JS)
    # ------------------------------------------------------------------ #
    async def parse_job(self, url: str, page) -> Optional[JobPosting]:
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                return None

            try:
                html = resp.content.decode("utf-8")
            except UnicodeDecodeError:
                html = resp.content.decode("utf-8-sig", errors="replace")

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
                experience      = data.get("experience"),
                level           = data.get("level"),
                industry        = data.get("industry"),
                description_raw = data.get("description_raw", ""),
                benefits_raw    = data.get("benefits_raw", ""),
                skills_raw      = data.get("skills_raw", []),
                posted_date     = data.get("posted_date"),
                deadline        = data.get("deadline"),
            )

        except Exception as e:
            logger.error(f"parse_job failed for {url}: {e}")
            return None

    # ------------------------------------------------------------------ #
    # HELPER: Bóc tách từ RSC streaming (row-based)
    # ------------------------------------------------------------------ #
    def _extract_from_rsc(self, html: str) -> Optional[Dict[str, Any]]:
        payload = _join_rsc_chunks(html)
        if not payload:
            return None

        rows = _parse_rows(payload)

        # Job object chính: dict có jobId + jobTitle. Stream có thể chứa
        # 2 bản copy — lấy bản nhiều field nhất (bản đầy đủ).
        job_obj = None
        for val in rows.values():
            if isinstance(val, dict) and val.get("jobId") and val.get("jobTitle"):
                if job_obj is None or len(val) > len(job_obj):
                    job_obj = val
        if job_obj is None:
            return None

        result: Dict[str, Any] = {
            "job_title": job_obj.get("jobTitle"),
            "company_name": job_obj.get("companyName"),
        }

        # ---- Địa điểm (có thể nhiều working location) ----
        locs = _resolve_ref(rows, job_obj.get("workingLocations"))
        if isinstance(locs, list):
            cities, addresses = [], []
            for loc in locs:
                if isinstance(loc, dict):
                    city = loc.get("cityNameVI") or loc.get("cityName") or ""
                    addr = loc.get("address") or ""
                    if city and city not in cities:
                        cities.append(city)
                    if addr and addr not in addresses:
                        addresses.append(addr)
            if cities or addresses:
                result["location"] = {"city": ", ".join(cities), "address": "; ".join(addresses)}

        # ---- Lương: min/max theo currency của nguồn + text hiển thị ----
        pretty = job_obj.get("prettySalaryVI") or job_obj.get("prettySalary") or ""
        smin, smax = job_obj.get("salaryMin"), job_obj.get("salaryMax")
        currency = job_obj.get("salaryCurrency") or "VND"
        result["salary"] = {
            "raw": pretty,
            "min": smin if isinstance(smin, int) and smin > 0 else None,
            "max": smax if isinstance(smax, int) and smax > 0 else None,
            "currency": currency,
            "negotiable": smin in (0, None) and smax in (0, None),
        }

        # ---- Cấp bậc / kinh nghiệm / ngành ----
        result["level"] = job_obj.get("jobLevelVI") or job_obj.get("jobLevel")
        yoe = job_obj.get("yearsOfExperience")
        if isinstance(yoe, int) and yoe > 0:
            result["experience"] = {"min": yoe}

        industries = _resolve_ref(rows, job_obj.get("industriesV3")) or _resolve_ref(
            rows, job_obj.get("industries")
        )
        if isinstance(industries, list):
            names = [
                i.get("industryNameVI") or i.get("industryName")
                for i in industries
                if isinstance(i, dict) and (i.get("industryNameVI") or i.get("industryName"))
            ]
            if names:
                result["industry"] = ", ".join(names)

        # ---- Mô tả + yêu cầu (text rows, HTML -> plain text) ----
        parts = []
        for ref_key in ("jobDescription", "jobRequirement"):
            fragment = _resolve_ref(rows, job_obj.get(ref_key))
            if isinstance(fragment, str) and fragment.strip():
                parts.append(_html_to_text(fragment) if "<" in fragment else fragment.strip())
        if parts:
            result["description_raw"] = "\n\n".join(parts)

        # ---- Kỹ năng ----
        skills = _resolve_ref(rows, job_obj.get("skills"))
        if isinstance(skills, list):
            names = []
            for s in skills:
                name = s.get("skillName") if isinstance(s, dict) else None
                if name and name not in names:
                    names.append(name)
            if names:
                result["skills_raw"] = names

        # ---- Quyền lợi: "Tên phúc lợi: giá trị" (giữ nguyên thứ tự, khử trùng) ----
        benefits = _resolve_ref(rows, job_obj.get("benefits"))
        if isinstance(benefits, list):
            chunks = []
            for b in benefits:
                if not isinstance(b, dict) or not b.get("benefitValue"):
                    continue
                name = b.get("benefitNameVI") or b.get("benefitName") or ""
                value = _html_to_text(b["benefitValue"]) if "<" in b["benefitValue"] else b["benefitValue"]
                chunk = f"{name}: {value}".strip()
                if chunk and chunk not in chunks:
                    chunks.append(chunk)
            if chunks:
                result["benefits_raw"] = " | ".join(chunks)

        # ---- Ngày đăng / hết hạn ----
        posted = job_obj.get("createdOn") or job_obj.get("approvedOn")
        if posted:
            result["posted_date"] = posted
        if job_obj.get("expiredOn"):
            result["deadline"] = job_obj["expiredOn"]

        return result if result else None

    # ------------------------------------------------------------------ #
    # HELPER: Fallback — bóc tách từ thẻ meta/og nếu RSC thất bại
    # ------------------------------------------------------------------ #
    def _extract_from_meta(self, html: str) -> Optional[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        result: Dict[str, Any] = {}

        og_title = soup.find("meta", property="og:title")
        raw_title = (og_title.get("content", "") if og_title else "") or (
            soup.title.string if soup.title else ""
        )
        if raw_title:
            # "Tuyển Nhân Viên Kế Toán Tổng Hợp tại Công Ty XYZ T10/2026"
            if " tại " in raw_title:
                parts = raw_title.split(" tại ", 1)
                result["job_title"] = parts[0].replace("Tuyển ", "").strip()
                result["company_name"] = re.sub(r"\s+T\d{1,2}/\d{4}$", "", parts[1]).strip()
            else:
                result["job_title"] = raw_title.strip()

        og_desc = soup.find("meta", property="og:description")
        desc_tag = og_desc or soup.find("meta", {"name": "description"})
        if desc_tag:
            result["description_raw"] = desc_tag.get("content", "")

        return result if result else None
