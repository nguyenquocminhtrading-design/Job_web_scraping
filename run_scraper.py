import asyncio
import yaml
import json
from datetime import datetime
from loguru import logger
import os

from layer2_scraping.scrapers.vietnamworks import VietnamWorksScraper
from layer2_scraping.scrapers.topcv import TopCVScraper
from layer2_scraping.scrapers.careerviet import CareerVietScraper

def load_config():
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_keywords():
    with open("config/keywords.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

async def main():
    logger.info("Khởi động quá trình Web Scraping...")
    
    # 1. Load cấu hình và từ khóa
    config = load_config()
    keywords_data = load_keywords()
    
    # Lấy danh sách từ khóa chính ngành Tài chính (ví dụ từ general_accounting)
    # File cấu hình đã thay đổi cấu trúc: finance_accounting -> general_accounting -> primary
    keywords = keywords_data.get("finance_accounting", {}).get("general_accounting", {}).get("primary", [])
    
    # Ở phiên bản test, ta chỉ lấy 1-2 từ khóa đầu tiên để chạy nhanh
    test_keywords = keywords[:2] 
    logger.info(f"Sẽ scrape cho các từ khóa: {test_keywords}")

    # 2. Khởi tạo Scraper (Ví dụ dùng VietnamWorks)
    vw_scraper = VietnamWorksScraper(config)
    
    # 3. Chạy scraper
    # Tham số filters có thể truyền để lọc thêm (địa điểm, cấp bậc...)
    results = await vw_scraper.scrape(keywords=test_keywords, filters={})
    
    logger.info(f"Đã thu thập được {len(results)} JDs.")
    
    # 4. Lưu dữ liệu thô ra file JSON để kiểm tra
    if results:
        # Đảm bảo thư mục tồn tại
        os.makedirs("data/raw", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/vietnamworks_{timestamp}.json"

        # Bỏ các field None/rỗng để JSON đầu ra gọn, dễ đọc
        results_dict = [
            {k: v for k, v in job.__dict__.items() if v not in (None, "", [], {})}
            for job in results
        ]

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=4)
            
        logger.success(f"Đã lưu kết quả tại: {filename}")
    else:
        logger.warning("Không có dữ liệu nào được scrape.")

if __name__ == "__main__":
    # Để tránh lỗi Event Loop trên Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(main())
