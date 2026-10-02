"""
Pipeline end-to-end: Scrape (L2) -> Dedup + Enrich (L3) -> MVJD (L4) -> Storage (JSON + MongoDB).

Enrichment gắn đúng tên field mà Layer 4 mong đợi:
  - extracted_hard_skills / extracted_soft_skills / extracted_certs  (mvjd_builder, trend_analyzer)
  - benefits_structured                                              (benefits_comparator)
  - salary (đã chuẩn VND)                                            (salary_parser)

Cách chạy (từ thư mục gốc project):
    python run_pipeline.py                                   # nhóm keyword mặc định
    python run_pipeline.py --group finance_accounting.tax_compliance.primary
    python run_pipeline.py --keyword-limit 2 --max-pages 2   # chạy nhanh để test
    python run_pipeline.py --no-mongo                        # chỉ lưu JSON
"""
import argparse
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List

import yaml
from dotenv import load_dotenv
from loguru import logger

from layer2_scraping.base_scraper import JobPosting
from layer2_scraping.scrapers.vietnamworks import VietnamWorksScraper
from layer3_nlp.benefits_classifier import BenefitsClassifier
from layer3_nlp.deduplicator import Deduplicator
from layer3_nlp.salary_parser import SalaryParser
from layer3_nlp.skill_extractor import SkillExtractor
from layer4_analytics.mvjd_builder import MinimumViableJDBuilder

load_dotenv()

# Chỉ những scraper đã implement thật; source khác trong config sẽ bị bỏ qua với cảnh báo
SCRAPERS = {"vietnamworks": VietnamWorksScraper}


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_keywords(keywords_data: dict, group_path: str) -> List[str]:
    """Đi theo đường dẫn chấm, vd 'finance_accounting.general_accounting.primary'."""
    node = keywords_data
    for part in group_path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise SystemExit(
                f"Không tìm thấy nhóm keyword '{group_path}' (lỗi tại '{part}'). "
                f"Các nhánh khả dụng: {list(node.keys()) if isinstance(node, dict) else '—'}"
            )
        node = node[part]
    if isinstance(node, dict) and "primary" in node:
        node = node["primary"]
    if not isinstance(node, list) or not node:
        raise SystemExit(f"Nhóm '{group_path}' không chứa danh sách từ khóa.")
    return node


def enrich_posting(job: JobPosting, salary_parser: SalaryParser,
                   skill_extractor: SkillExtractor, benefits_classifier: BenefitsClassifier) -> dict:
    """JobPosting -> dict giàu dữ liệu L3: salary chuẩn VND, skills/benefits đã rút trích."""
    doc = {k: v for k, v in job.__dict__.items() if v not in (None, "", [], {})}

    doc["salary"] = salary_parser.parse_salary(job.salary)

    text = "\n".join([job.description_raw or "", " ".join(job.skills_raw or [])])
    extracted = skill_extractor.extract_skills(text)
    doc["extracted_hard_skills"] = extracted["hard"]
    doc["extracted_soft_skills"] = extracted["soft"]
    doc["extracted_certs"] = extracted["certs"]

    doc["benefits_structured"] = benefits_classifier.classify_benefits(job.benefits_raw or "")

    city = job.location.get("city", "") if isinstance(job.location, dict) else ""
    doc["dedup_hash"] = Deduplicator.generate_hash(job.job_title, job.company_name, city)
    doc["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    return doc


def save_to_mongo(docs: List[dict], config: dict) -> bool:
    """Upsert theo dedup_hash. Trả về True nếu lưu thành công."""
    try:
        from pymongo import MongoClient
    except ImportError:
        logger.warning("Chưa cài pymongo (pip install pymongo) — bỏ qua MongoDB.")
        return False

    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = config.get("database", {}).get("db_name", "labor_market_vn")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except Exception as e:
        logger.warning(
            f"MongoDB không truy cập được ({e.__class__.__name__}) — chỉ lưu JSON. "
            f"Bật bằng: docker compose up -d mongodb"
        )
        return False

    coll = client[db_name]["job_postings"]
    coll.create_index("dedup_hash")
    inserted = 0
    for doc in docs:
        res = coll.update_one({"dedup_hash": doc["dedup_hash"]}, {"$set": doc}, upsert=True)
        if res.upserted_id is not None:
            inserted += 1
    logger.success(f"MongoDB [{db_name}.job_postings]: {inserted} mới / {len(docs)} upsert")
    client.close()
    return True


async def run_pipeline(args) -> None:
    config = load_yaml("config/settings.yaml")
    keywords_data = load_yaml("config/keywords.yaml")

    keywords = resolve_keywords(keywords_data, args.group)
    if args.keyword_limit:
        keywords = keywords[: args.keyword_limit]
    if args.max_pages:
        config.setdefault("scraping", {})["max_pages"] = args.max_pages

    sources = config.get("pipeline", {}).get("sources", ["vietnamworks"])
    usd_rate = config.get("pipeline", {}).get("usd_to_vnd")

    logger.info(f"Pipeline: {len(keywords)} từ khóa | nguồn={sources} | max_pages={config['scraping'].get('max_pages')}")
    logger.info(f"Từ khóa: {keywords}")

    # ---------- LAYER 2: Scrape ----------
    postings: List[JobPosting] = []
    for source in sources:
        scraper_cls = SCRAPERS.get(source)
        if scraper_cls is None:
            logger.warning(f"Nguồn '{source}' chưa implement — bỏ qua.")
            continue
        scraper = scraper_cls(config)
        results = await scraper.scrape(keywords=keywords, filters={})
        logger.info(f"[{source}] scrape được {len(results)} JDs")
        postings.extend(results)

    if not postings:
        logger.warning("Không scrape được JD nào.")
        return

    # ---------- LAYER 3: Dedup + Enrich ----------
    salary_parser = SalaryParser(usd_to_vnd=usd_rate)
    skill_extractor = SkillExtractor()
    benefits_classifier = BenefitsClassifier()

    docs = [enrich_posting(j, salary_parser, skill_extractor, benefits_classifier) for j in postings]
    total_raw = len(docs)
    unique_docs = Deduplicator.deduplicate(docs)
    logger.info(f"Dedup: {total_raw} -> {len(unique_docs)} JDs duy nhất (bỏ {total_raw - len(unique_docs)})")

    # ---------- LAYER 4: MVJD ----------
    mvjd = MinimumViableJDBuilder().build_minimum_jd(role=args.group, postings=unique_docs)

    # ---------- LAYER 5: Storage ----------
    os.makedirs("data/processed", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    group_slug = args.group.replace(".", "_")

    jobs_file = f"data/processed/jobs_{group_slug}_{ts}.json"
    with open(jobs_file, "w", encoding="utf-8") as f:
        json.dump(unique_docs, f, ensure_ascii=False, indent=2)

    mvjd_file = f"data/processed/mvjd_{group_slug}_{ts}.json"
    with open(mvjd_file, "w", encoding="utf-8") as f:
        json.dump(mvjd, f, ensure_ascii=False, indent=2)

    mongo_ok = False
    if not args.no_mongo:
        mongo_ok = save_to_mongo(unique_docs, config)

    # ---------- Tóm tắt ----------
    with_salary = sum(1 for d in unique_docs if d["salary"].get("min") or d["salary"].get("max"))
    top_skills = [s["name"] for s in mvjd.get("hard_skills", {}).get("mandatory", [])][:10] or \
                 [s["name"] for s in mvjd.get("hard_skills", {}).get("preferred", [])][:10]
    logger.success(f"XONG: {len(unique_docs)} JDs | {with_salary} có lương cụ thể")
    logger.info(f"Kỹ năng nổi bật: {top_skills}")
    logger.info(f"Đã lưu: {jobs_file}")
    logger.info(f"MVJD:   {mvjd_file}")
    if not mongo_ok and not args.no_mongo:
        logger.info("Dữ liệu lần này chưa vào MongoDB — bật 'docker compose up -d mongodb' rồi chạy lại để upsert.")


def main():
    parser = argparse.ArgumentParser(description="Pipeline thu thập + phân tích thị trường lao động")
    parser.add_argument("--group", default="finance_accounting.general_accounting.primary",
                        help="Đường dẫn nhóm từ khóa trong keywords.yaml (dấu chấm)")
    parser.add_argument("--keyword-limit", type=int, default=None, help="Chỉ dùng N từ khóa đầu")
    parser.add_argument("--max-pages", type=int, default=None, help="Override số trang search mỗi từ khóa")
    parser.add_argument("--no-mongo", action="store_true", help="Không lưu vào MongoDB")
    args = parser.parse_args()

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
