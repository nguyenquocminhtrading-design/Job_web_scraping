from typing import List, Dict, Any

class GapAnalyzer:
    @staticmethod
    def analyze_gap(market_requirements: Dict[str, Any], candidate_skills: List[str]) -> Dict[str, Any]:
        """
        Compares candidate skills against Market Minimum Viable JD.
        """
        candidate_skills_lower = [s.lower() for s in candidate_skills]
        
        missing_mandatory = []
        for req in market_requirements.get("hard_skills", {}).get("mandatory", []):
            if req['name'].lower() not in candidate_skills_lower:
                missing_mandatory.append(req['name'])
                
        missing_preferred = []
        for req in market_requirements.get("hard_skills", {}).get("preferred", []):
            if req['name'].lower() not in candidate_skills_lower:
                missing_preferred.append(req['name'])
                
        return {
            "candidate_skills": candidate_skills,
            "missing_mandatory": missing_mandatory,
            "missing_preferred": missing_preferred,
            "recommendation": "Focus on acquiring missing mandatory skills first." if missing_mandatory else "You meet the mandatory requirements. Consider adding preferred skills."
        }
