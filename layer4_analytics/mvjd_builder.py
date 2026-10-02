from collections import Counter
from typing import List, Dict, Any

class MinimumViableJDBuilder:
    def __init__(self, threshold_mandatory: float = 0.60, threshold_preferred: float = 0.30):
        self.threshold_mandatory = threshold_mandatory
        self.threshold_preferred = threshold_preferred

    def build_minimum_jd(self, role: str, postings: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not postings:
            return {"role": role, "sample_size": 0, "error": "No data"}
            
        n = len(postings)
        
        hard_skill_counts = Counter()
        soft_skill_counts = Counter()
        cert_counts = Counter()
        
        for p in postings:
            # Assuming skills and certs have been extracted and are present as lists
            for s in p.get("extracted_hard_skills", []):
                hard_skill_counts[s] += 1
            for s in p.get("extracted_soft_skills", []):
                soft_skill_counts[s] += 1
            for c in p.get("extracted_certs", []):
                cert_counts[c] += 1
                
        def categorize(counts: Counter) -> Dict[str, List[Dict]]:
            res = {"mandatory": [], "preferred": [], "optional": []}
            for item, count in counts.items():
                rate = count / n
                obj = {"name": item, "rate": round(rate, 2)}
                if rate >= self.threshold_mandatory:
                    res["mandatory"].append(obj)
                elif rate >= self.threshold_preferred:
                    res["preferred"].append(obj)
                else:
                    res["optional"].append(obj)
            
            # Sort by rate descending
            for k in res:
                res[k] = sorted(res[k], key=lambda x: x["rate"], reverse=True)
            return res

        return {
            "role": role,
            "sample_size": n,
            "hard_skills": categorize(hard_skill_counts),
            "soft_skills": categorize(soft_skill_counts),
            "certifications": categorize(cert_counts)
        }
