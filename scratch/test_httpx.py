import httpx
import asyncio
from bs4 import BeautifulSoup

async def fetch():
    url = "https://www.vietnamworks.com/nhan-vien-ke-toan-tong-hop-1790331128183091809-2111927-jv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        print("Status:", response.status_code)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        print("Title:", soup.title.string if soup.title else "No title")
        
if __name__ == "__main__":
    asyncio.run(fetch())
