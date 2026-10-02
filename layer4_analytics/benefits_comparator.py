import pandas as pd
from typing import List, Dict, Any

class BenefitsComparator:
    @staticmethod
    def compare(postings: List[Dict[str, Any]], dimension: str = "company_type") -> Dict[str, Any]:
        """
        Compare benefits across a specific dimension (e.g., 'company_type' or 'level').
        Returns a structure suitable for heatmap rendering.
        """
        if not postings:
            return {}
            
        df = pd.DataFrame(postings)
        if dimension not in df.columns:
            # If the dimension isn't there, create a dummy or handle error
            df[dimension] = "Unknown"
            
        # We assume postings have a 'benefits' dict mapping category -> boolean
        # Example: p['benefits'] = {'bonus': True, 'insurance': False, ...}
        
        # Flatten the benefits into the dataframe
        benefit_categories = ["bonus", "insurance", "leave_time", "training", "financial", "non_financial", "culture", "other"]
        
        for cat in benefit_categories:
            df[f'benefit_{cat}'] = df['benefits_structured'].apply(lambda x: x.get(cat, False) if isinstance(x, dict) else False)
            
        # Group by dimension and calculate the mean (percentage of true values)
        agg_dict = {f'benefit_{cat}': 'mean' for cat in benefit_categories}
        
        grouped = df.groupby(dimension).agg(agg_dict).reset_index()
        
        # Convert back to dict for API response
        result = {}
        for index, row in grouped.iterrows():
            dim_val = row[dimension]
            if pd.isna(dim_val):
                dim_val = "Unknown"
            result[dim_val] = {cat: round(row[f'benefit_{cat}'] * 100, 2) for cat in benefit_categories}
            
        return result
