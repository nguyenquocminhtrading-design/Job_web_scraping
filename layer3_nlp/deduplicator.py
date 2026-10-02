from typing import List
import hashlib

class Deduplicator:
    @staticmethod
    def generate_hash(job_title: str, company: str, location: str) -> str:
        """
        Generate a unique hash for a job posting based on title, company, and location.
        Used to identify exact duplicates across different platforms.
        """
        job_title = job_title.lower().strip() if job_title else ""
        company = company.lower().strip() if company else ""
        location = location.lower().strip() if location else ""
        
        raw_str = f"{job_title}|{company}|{location}"
        return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

    @staticmethod
    def deduplicate(postings: List[dict]) -> List[dict]:
        seen_hashes = set()
        unique_postings = []
        
        for p in postings:
            title = p.get('job_title', '')
            company = p.get('company_name', '')
            # For simplicity, location is treated as empty string here if not provided in simple dict
            loc = p.get('location', {}).get('city', '') if isinstance(p.get('location'), dict) else ''
            
            p_hash = Deduplicator.generate_hash(title, company, loc)
            if p_hash not in seen_hashes:
                seen_hashes.add(p_hash)
                unique_postings.append(p)
                
        return unique_postings
