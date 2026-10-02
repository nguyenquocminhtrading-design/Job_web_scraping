import re
from typing import Dict, Any

class BenefitsClassifier:
    BENEFITS_PATTERNS = {
        "bonus": ["thưởng", "bonus", "13 tháng", "14 tháng", "commission", "kpi", "tháng 13"],
        "insurance": ["bhxh", "bhyt", "bảo hiểm sức khỏe", "pti", "bảo việt", "manulife", "bảo hiểm"],
        "leave_time": ["nghỉ phép", "annual leave", "remote", "hybrid", "work from home", "flexible working", "linh hoạt"],
        "training": ["đào tạo", "training", "tài trợ chứng chỉ", "sponsor", "học bổng"],
        "financial": ["esop", "cổ phần", "stock option", "vay ưu đãi", "nhà ở"],
        "non_financial": ["du lịch", "teambuilding", "gym", "yoga", "happy hour", "khám sức khỏe"],
        "culture": ["startup", "agile", "môi trường", "năng động", "quốc tế"],
        "other": ["cơm trưa", "xe đưa đón", "laptop", "điện thoại", "gửi xe"]
    }

    @staticmethod
    def classify_benefits(text: str) -> Dict[str, bool]:
        if not text:
            return {k: False for k in BenefitsClassifier.BENEFITS_PATTERNS.keys()}
            
        text_lower = text.lower()
        results = {}
        for category, keywords in BenefitsClassifier.BENEFITS_PATTERNS.items():
            found = any(kw in text_lower for kw in keywords)
            results[category] = found
            
        return results
