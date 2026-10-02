"""
Prototype: row-based RSC flight parser cho VietnamWorks.
Test offline trên scratch/vw_raw.html trước khi tích hợp vào scraper.

React Flight wire format: các row `ID:<type><content>` nối tiếp nhau
(cách nhau bằng newline HOẶC dính liền, ví dụ: `...</p>2a:{"skillName"...`).
Bản copy payload có thể xuất hiện 2 lần trong stream -> phải resolve ref
từ DUY NHẤT 1 job object thay vì regex toàn bộ payload.
"""
import re
import json
from typing import Any, Dict, Optional, Tuple

ROW_MARK = re.compile(r"[0-9a-f]{1,4}:(?=[{[\"T$])")
ROW_HEAD = re.compile(r"([0-9a-f]{1,4}):")
TYPE_HEAD = re.compile(r"(T[0-9a-f]+,|HL|H[0-9a-z]*|I[0-9a-z]*|X[0-9a-z]*|S[0-9a-z]*)")
JSON_DECODER = json.JSONDecoder()


def join_rsc_chunks(html: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL)
    payload = ""
    for c in chunks:
        try:
            payload += json.loads(f'"{c}"')
        except Exception:
            payload += c
    return payload


def parse_rows(payload: str) -> Dict[str, Any]:
    """Scan tuần tự các row của flight stream. JSON row decode thật; T row cắt tại marker kế tiếp."""
    rows: Dict[str, Any] = {}
    pos, n = 0, len(payload)
    while pos < n:
        # bỏ whitespace giữa các row
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
        if payload[p : p + 1] in "{[":
            try:
                obj, end = JSON_DECODER.raw_decode(payload, p)
                rows[row_id] = obj
                pos = end
                continue
            except json.JSONDecodeError:
                pass

        # Text row: T<hexlen>,<nội dung tự do tới row kế>
        if payload[p : p + 1] == "T":
            m2 = re.match(r"T[0-9a-f]+,", payload[p : p + 16])
            if m2:
                text_start = p + m2.end()
                nxt = ROW_MARK.search(payload, text_start)
                text_end = nxt.start() if nxt else n
                rows[row_id] = ("T", payload[text_start:text_end])
                pos = text_end
                continue

        # Row kiểu khác (H, I, L, X, S...): thử decode JSON sau prefix type
        m3 = TYPE_HEAD.match(payload, p)
        if m3:
            q = m3.end()
            if payload[q : q + 1] in "{[":
                try:
                    obj, end = JSON_DECODER.raw_decode(payload, q)
                    rows[row_id] = obj
                    pos = end
                    continue
                except json.JSONDecodeError:
                    pass
            if payload[q : q + 1] == '"':
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


REF_PAT = re.compile(r"^\$[0-9a-zA-Z]{1,6}$")


def resolve_ref(rows: Dict[str, Any], ref: Any, depth: int = 0) -> Any:
    """Resolve tham chiếu flight '$xx' / '$Lxx' / mảng chứa ref."""
    if depth > 6:
        return ref
    if isinstance(ref, str) and REF_PAT.match(ref):
        rid = ref[1:].lstrip("L")
        val = rows.get(rid)
        if val is None:
            return None
        if isinstance(val, tuple):  # T row
            return val[1]
        # val lại có thể là list/dict chứa ref con -> resolve tiếp
        return resolve_ref(rows, val, depth + 1)
    if isinstance(ref, list):
        return [resolve_ref(rows, x, depth + 1) for x in ref]
    if isinstance(ref, dict):
        return {k: resolve_ref(rows, v, depth + 1) for k, v in ref.items()}
    return ref


def html_to_text(html_fragment: str) -> str:
    from bs4 import BeautifulSoup
    return BeautifulSoup(html_fragment, "html.parser").get_text(separator="\n").strip()


def extract_job(payload: str) -> Optional[Dict[str, Any]]:
    rows = parse_rows(payload)

    # Tìm job object chính: dict có jobId + jobTitle, ưu tiên object nhiều field nhất
    job_obj = None
    for rid, val in rows.items():
        if isinstance(val, dict) and val.get("jobId") and val.get("jobTitle"):
            if job_obj is None or len(val) > len(job_obj):
                job_obj = val
    if job_obj is None:
        return None

    result: Dict[str, Any] = {
        "job_title": job_obj.get("jobTitle"),
        "company_name": job_obj.get("companyName"),
    }

    # Location: workingLocations -> [obj]
    locs = resolve_ref(rows, job_obj.get("workingLocations"))
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

    # Salary
    pretty = job_obj.get("prettySalaryVI") or job_obj.get("prettySalary") or ""
    smin, smax = job_obj.get("salaryMin"), job_obj.get("salaryMax")
    currency = job_obj.get("salaryCurrency") or "VND"
    result["salary"] = {
        "raw": pretty,
        "min": smin if isinstance(smin, int) and smin > 0 else None,
        "max": smax if isinstance(smax, int) and smax > 0 else None,
        "currency": currency if currency else "VND",
        "negotiable": (smin in (0, None) and smax in (0, None)),
    }

    # Level / kinh nghiệm / ngành
    result["level"] = job_obj.get("jobLevelVI") or job_obj.get("jobLevel")
    yoe = job_obj.get("yearsOfExperience")
    if isinstance(yoe, int) and yoe > 0:
        result["experience"] = {"min": yoe}
    industries = resolve_ref(rows, job_obj.get("industriesV3")) or resolve_ref(
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

    # Description + requirement (T rows)
    desc = resolve_ref(rows, job_obj.get("jobDescription"))
    req = resolve_ref(rows, job_obj.get("jobRequirement"))
    parts = [html_to_text(x) for x in (desc, req) if isinstance(x, str) and "<" in x]
    parts += [x.strip() for x in (desc, req) if isinstance(x, str) and "<" not in x and x.strip()]
    if parts:
        result["description_raw"] = "\n\n".join(parts)

    # Skills: skills -> [ref] -> [{skillName}]
    skills = resolve_ref(rows, job_obj.get("skills"))
    if isinstance(skills, list):
        names = []
        for s in skills:
            if isinstance(s, dict) and s.get("skillName") and s["skillName"] not in names:
                names.append(s["skillName"])
        if names:
            result["skills_raw"] = names

    # Benefits: benefits -> [ref] -> [{benefitNameVI, benefitValue}]
    benefits = resolve_ref(rows, job_obj.get("benefits"))
    if isinstance(benefits, list):
        chunks = []
        for b in benefits:
            if isinstance(b, dict) and b.get("benefitValue"):
                name = b.get("benefitNameVI") or b.get("benefitName") or ""
                chunks.append(f"{name}: {b['benefitValue']}")
        if chunks:
            result["benefits_raw"] = " | ".join(chunks)

    # Dates
    if job_obj.get("createdOn"):
        result["posted_date"] = job_obj["createdOn"]
    if job_obj.get("expiredOn"):
        result["deadline"] = job_obj["expiredOn"]

    return result


if __name__ == "__main__":
    html = open("scratch/vw_raw.html", encoding="utf-8").read()
    payload = join_rsc_chunks(html)
    print("payload size:", len(payload))
    print("so lan xuat hien job object:", payload.count('{"jobId"'))
    rows = parse_rows(payload)
    print("tong so rows:", len(rows))
    data = extract_job(payload)
    if data:
        for k, v in data.items():
            s = str(v)
            print(f"\n### {k}:")
            print(s[:600] + ("..." if len(s) > 600 else ""))
    else:
        print("KHONG extract duoc job!")
