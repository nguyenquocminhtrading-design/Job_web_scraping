"""
Chuyển lương về chuẩn VND/tháng.

Ưu tiên dữ liệu có cấu trúc từ scraper ({min, max, currency, raw}):
quy đổi USD -> VND theo tỷ giá cấu hình. Chỉ fallback parse text
khi thiếu min/max. Không bao giờ đoán USD khi text không có ký hiệu
tiền tệ ($ hoặc "usd").
"""
import os
import re
from typing import Any, Dict, Optional
from loguru import logger


class SalaryParser:
    DEFAULT_USD_VND = 26000

    NEGOTIABLE_WORDS = [
        "thỏa thuận", "thoa thuan", "thương lượng", "thuong luong",
        "negotiable", "cạnh tranh", "canh tranh", "competitive",
    ]
    # đơn vị triệu VND — thứ tự quan trọng: chuỗi dài hơn đứng trước
    UNIT = r"(?:trieu|triệu|million|tr|m)"

    def __init__(self, usd_to_vnd: Optional[int] = None):
        if usd_to_vnd is None:
            usd_to_vnd = int(os.getenv("USD_VND_RATE", self.DEFAULT_USD_VND))
        self.usd_to_vnd = usd_to_vnd

    # ---------------------------------------------------------------- #
    # API chính
    # ---------------------------------------------------------------- #
    def parse_salary(self, salary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Input: dict có cấu trúc từ scraper {raw, min, max, currency, negotiable}."""
        if not salary:
            return self._empty()
        mn, mx = salary.get("min"), salary.get("max")
        currency = (salary.get("currency") or "VND").strip().upper()
        negotiable = bool(salary.get("negotiable"))

        if currency in ("USD", "$") and (mn or mx):
            # Sanity check: nguồn (VietnamWorks) đôi khi gắn nhãn USD cho giá trị
            # vốn là VND (35tr-45tr). Lương USD/tháng thực tế < 100.000đ đơn vị.
            if max(mn or 0, mx or 0) >= 1_000_000:
                logger.debug(f"currency={currency} nhưng giá trị {mn}-{mx} là VND — bỏ quy đổi")
            else:
                return {
                    "min": int(mn * self.usd_to_vnd) if mn else None,
                    "max": int(mx * self.usd_to_vnd) if mx else None,
                    "currency": "VND",
                    "negotiable": False,
                    "source_currency": "USD",
                    "usd_rate": self.usd_to_vnd,
                }

        # VND (hoặc nguồn khác) đã có min/max tin cậy
        if mn or mx:
            return {"min": mn, "max": mx, "currency": "VND", "negotiable": negotiable}

        return self.parse_text(salary.get("raw") or "")

    # ---------------------------------------------------------------- #
    # Fallback: parse text hiển thị
    # ---------------------------------------------------------------- #
    def parse_text(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text:
            return self._empty()

        # Gộp số dạng ngăn cách nghìn: "15,000,000" / "15.000.000" -> "15000000"
        # (an toàn với số thập phân kiểu "18.5tr" vì lookahead cần đúng 3 chữ số)
        text = re.sub(r"(?<=\d)[.,](?=\d{3}(?!\d))", "", raw_text.lower())

        if any(w in text for w in self.NEGOTIABLE_WORDS):
            return self._empty()

        has_usd = "$" in text or "usd" in text
        num = r"(\d+(?:\.\d+)?)"

        # ---- USD: bắt buộc có $ hoặc "usd" trong text ----
        if has_usd:
            m = re.search(rf"{num}\s*(?:usd)?\s*[-–—~]\s*\$?\s*(?:usd)?\s*{num}", text)
            if m:
                mn, mx = float(m.group(1)), float(m.group(2))
                mult = 1_000_000 if re.search(self.UNIT, text) else 1
                return self._vnd(int(mn * mult * self.usd_to_vnd), int(mx * mult * self.usd_to_vnd))
            m = re.search(rf"(?:\$|usd)\s*{num}", text)
            if m:
                return self._vnd(int(float(m.group(1)) * self.usd_to_vnd), None)
            return self._empty()

        # ---- Khoảng có đơn vị triệu ở 1 trong 2 phía ----
        # 18tr-22tr | 15-25 triệu | 15tr - 25tr | 18tr-22
        m = re.search(
            rf"{num}\s*(?:{self.UNIT})?\s*[-–—~]\s*{num}\s*(?:{self.UNIT})?", text
        )
        if m and (re.search(rf"{num}\s*(?:{self.UNIT})", text) or re.search(rf"(?:{self.UNIT})\s*{num}", text)):
            mn, mx = float(m.group(1)), float(m.group(2))
            return self._vnd(int(mn * 1_000_000), int(mx * 1_000_000))

        # ---- Khoảng VND đầy đủ: 15000000 - 20000000 ----
        m = re.search(rf"{num}\s*[-–—~]\s*{num}", text)
        if m:
            mn, mx = float(m.group(1)), float(m.group(2))
            if mn >= 1_000_000:
                return self._vnd(int(mn), int(mx))
            # Số nhỏ không đơn vị ("15-20") — quy ước thị trường VN: đơn vị triệu
            if mn < 1_000:
                return self._vnd(int(mn * 1_000_000), int(mx * 1_000_000))

        # ---- "Trên 30 triệu" / "từ 18tr" / ">= 30tr" ----
        m = re.search(rf"(?:trên|từ|over|>=|>\s*)\s*{num}\s*(?:{self.UNIT})?", text)
        if m:
            val = float(m.group(1))
            mult = 1_000_000 if (val < 1_000 or re.search(rf"{num}\s*(?:{self.UNIT})", text)) else 1
            return self._vnd(int(val * mult), None)

        # ---- "Lên tới 22 triệu" / "tối đa 30tr" / "up to 2,000" ----
        m = re.search(rf"(?:lên tới|len toi|tối đa|toi da|up to|<=|<\s*)\s*{num}\s*(?:{self.UNIT})?", text)
        if m:
            val = float(m.group(1))
            mult = 1_000_000 if (val < 1_000 or re.search(rf"{num}\s*(?:{self.UNIT})", text)) else 1
            return self._vnd(None, int(val * mult))

        logger.debug(f"Could not parse salary: {raw_text!r}")
        return self._empty()

    # ---------------------------------------------------------------- #
    @staticmethod
    def _vnd(mn: Optional[int], mx: Optional[int]) -> Dict[str, Any]:
        return {"min": mn, "max": mx, "currency": "VND", "negotiable": False}

    @staticmethod
    def _empty(negotiable: bool = True) -> Dict[str, Any]:
        return {"min": None, "max": None, "currency": "VND", "negotiable": negotiable}

    def normalize_salary_vnd(self, raw_text: str) -> Dict[str, Any]:
        """Giữ tương thích API cũ."""
        return self.parse_text(raw_text)
