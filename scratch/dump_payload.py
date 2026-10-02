import asyncio
import httpx
import re
import json

async def main():
    url = 'https://www.vietnamworks.com/accountant-ke-toan-vien-co-xe-dua-don-tu-tp-hcm-1789694959463562696-2108642-jv'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
    
    html = resp.content.decode('utf-8', errors='replace')
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
    rsc_payload = ''
    for c in chunks:
        try:
            rsc_payload += json.loads(f'"{c}"')
        except:
            rsc_payload += c
            
    with open('scratch/payload_test.txt', 'w', encoding='utf-8') as f:
        f.write(rsc_payload)

if __name__ == '__main__':
    asyncio.run(main())
