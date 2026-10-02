import pandas as pd
from typing import List, Dict, Any

class TrendAnalyzer:
    @staticmethod
    def analyze_skill_trends(postings: List[Dict[str, Any]], skill: str) -> Dict[str, Any]:
        """
        Analyze the trend of a specific skill over time based on posted dates.
        """
        if not postings:
            return {}
            
        df = pd.DataFrame(postings)
        if 'posted_date' not in df.columns:
            return {"error": "No posted_date found"}
            
        df['posted_date'] = pd.to_datetime(df['posted_date'], errors='coerce')
        df = df.dropna(subset=['posted_date'])
        
        # Determine if the skill is present in each posting
        def has_skill(skills_list):
            if not isinstance(skills_list, list):
                return False
            return skill.lower() in [s.lower() for s in skills_list]
            
        df['has_skill'] = df['extracted_hard_skills'].apply(has_skill) | df['extracted_soft_skills'].apply(has_skill)
        
        # Group by month
        df['month'] = df['posted_date'].dt.to_period('M')
        monthly_stats = df.groupby('month').agg(
            total_jobs=('job_title', 'count'),
            skill_mentions=('has_skill', 'sum')
        ).reset_index()
        
        monthly_stats['month'] = monthly_stats['month'].astype(str)
        monthly_stats['percentage'] = (monthly_stats['skill_mentions'] / monthly_stats['total_jobs'] * 100).round(2)
        
        return {
            "skill": skill,
            "trend": monthly_stats.to_dict('records')
        }
