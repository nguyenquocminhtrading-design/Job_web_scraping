"""Test parser trên nhiều URL VietnamWorks để kiểm chứng độ bền."""
import asyncio
import sys

sys.path.insert(0, "scratch")
import httpx
import test_row_parser as tp

URLS = [
    # lương thương lượng (đã test)
    "https://www.vietnamworks.com/accountant-ke-toan-vien-co-xe-dua-don-tu-tp-hcm-1789694959463562696-2108642-jv",
    # title có chữ "Lương Lên Tới 22 Triệu" trong JSON cũ
    "https://www.vietnamworks.com/ke-toan-tong-hop-luong-len-toi-22-trieu-thang-1790416192173544593-2116580-jv",
    # treasury (JSON cũ job 0)
    "https://www.vietnamworks.com/treasury-specialist-chinese-speaking-1790908115256801222-2114906-jv",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
}


async def main():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        for url in URLS:
            try:
                resp = await client.get(url)
            except Exception as e:
                print(f"!!! FETCH FAIL {url}: {e}")
                continue
            print("=" * 80)
            print("HTTP", resp.status_code, url.rsplit('/', 1)[-1][:60])
            if resp.status_code != 200:
                continue
            html = resp.content.decode("utf-8", errors="replace")
            payload = tp.join_rsc_chunks(html)
            data = tp.extract_job(payload)
            if not data:
                print("!!! EXTRACT FAIL")
                continue
            for k, v in data.items():
                s = str(v).replace("\n", " ⏎ ")
                print(f"  {k:16}: {s[:180]}")
            desc = data.get("description_raw", "")
            print(f"  [desc len={len(desc)}] tail: ...{desc[-160:]!r}")


asyncio.run(main())
