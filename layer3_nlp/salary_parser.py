import re
from typing import Dict, Any, Optional
from loguru import logger

class SalaryParser:
    @staticmethod
    def normalize_salary_vnd(raw_text: str) -> Dict[str, Any]:
        """
        Handles:
        - "15-25 triệu" -> {min: 15_000_000, max: 25_000_000}
        - "Thỏa thuận" -> {min: None, max: None, negotiable: True}
        - "$1000-1500" -> {min: 25_000_000, max: 37_500_000}
        - "Trên 30 triệu" -> {min: 30_000_000, max: None}
        """
        if not raw_text:
            return {"min": None, "max": None, "currency": "VND", "negotiable": True}
            
        raw_text = raw_text.lower()
        
        # Negotiable
        if any(w in raw_text for w in ["thỏa thuận", "thoa thuan", "negotiable", "cạnh tranh", "competitive"]):
            return {"min": None, "max": None, "currency": "VND", "negotiable": True}

        # Range VND millions: 15 - 25 triệu, 15-25 tr
        m_vnd = re.search(r'(\d+)\s*-\s*(\d+)\s*(triệu|tr|m|million)', raw_text)
        if m_vnd:
            min_val = int(m_vnd.group(1)) * 1_000_000
            max_val = int(m_vnd.group(2)) * 1_000_000
            return {"min": min_val, "max": max_val, "currency": "VND", "negotiable": False}

        # Range USD: $1000 - $1500
        m_usd = re.search(r'\$?\s*(\d+)\s*(usd)?\s*-\s*\$?\s*(\d+)\s*(usd)?', raw_text)
        if m_usd:
            min_val = int(m_usd.group(1)) * 25_000
            max_val = int(m_usd.group(3)) * 25_000
            return {"min": min_val, "max": max_val, "currency": "VND", "negotiable": False}
            
        # Above VND: trên 30 triệu, >30 tr
        m_above = re.search(r'(trên|over|>)\s*(\d+)\s*(triệu|tr)', raw_text)
        if m_above:
            min_val = int(m_above.group(2)) * 1_000_000
            return {"min": min_val, "max": None, "currency": "VND", "negotiable": False}
            
        # Lương tính đến ngàn/VND cụ thể: 15,000,000 - 20,000,000
        m_full = re.search(r'(\d{1,3}(?:[.,]\d{3})+)\s*-\s*(\d{1,3}(?:[.,]\d{3})+)', raw_text)
        if m_full:
            min_val = int(re.sub(r'[.,]', '', m_full.group(1)))
            max_val = int(re.sub(r'[.,]', '', m_full.group(2)))
            return {"min": min_val, "max": max_val, "currency": "VND", "negotiable": False}
            
        logger.debug(f"Could not parse salary: {raw_text}")
        return {"min": None, "max": None, "currency": "VND", "negotiable": True}
