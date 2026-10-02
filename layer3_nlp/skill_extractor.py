import json
import re
from typing import List, Dict, Any
from layer3_nlp.text_normalizer import TextNormalizer
import os

class SkillExtractor:
    def __init__(self, taxonomy_path: str = "layer3_nlp/taxonomies/skills_taxonomy.json"):
        with open(taxonomy_path, "r", encoding="utf-8") as f:
            self.taxonomy = json.load(f)
            
        self.hard_skills = []
        for category in self.taxonomy.get("hard_skills", {}).values():
            self.hard_skills.extend(category)
            
        self.soft_skills = self.taxonomy.get("soft_skills", [])
        
        self.certs = []
        for category in self.taxonomy.get("certifications", {}).values():
            self.certs.extend(category)

        # Precompute normalized versions
        self.norm_hard_skills = [TextNormalizer.normalize_text(s) for s in self.hard_skills]
        self.norm_soft_skills = [TextNormalizer.normalize_text(s) for s in self.soft_skills]
        self.norm_certs = [TextNormalizer.normalize_text(c) for c in self.certs]

    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        if not text:
            return {"hard": [], "soft": [], "certs": []}
            
        norm_text = TextNormalizer.normalize_text(text)
        
        extracted_hard = [skill for i, skill in enumerate(self.hard_skills) if f" {self.norm_hard_skills[i]} " in f" {norm_text} "]
        extracted_soft = [skill for i, skill in enumerate(self.soft_skills) if f" {self.norm_soft_skills[i]} " in f" {norm_text} "]
        extracted_certs = [cert for i, cert in enumerate(self.certs) if f" {self.norm_certs[i]} " in f" {norm_text} "]
        
        return {
            "hard": list(set(extracted_hard)),
            "soft": list(set(extracted_soft)),
            "certs": list(set(extracted_certs))
        }
