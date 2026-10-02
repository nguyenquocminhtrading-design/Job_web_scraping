import asyncio
from playwright.async_api import async_playwright
import os

async def dump_html():
    url = "https://www.vietnamworks.com/nhan-vien-ke-toan-tong-hop-1790331128183091809-2111927-jv"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        from playwright_stealth import stealth
        await stealth(page)
        
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/vietnamworks_sample.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("HTML dumped to scratch/vietnamworks_sample.html")
        await browser.close()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(dump_html())
