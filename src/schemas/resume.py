# File: src/schemas/resume.py
"""Resume schema validation helper functions."""

from typing import Tuple, Any

def validate_resume_info_density(parsed_text: dict) -> Tuple[bool, list[str]]:
    """Validate that the parsed resume dictionary has sufficient information density."""
    missing_fields = []
    
    # 1. Check work experience bullet count
    exp_list = parsed_text.get("work_experience") or parsed_text.get("experience") or []
    bullet_count = 0
    for exp in exp_list:
        bullets = exp.get("bullets") or []
        desc = exp.get("description") or exp.get("responsibilities_achievements") or ""
        if bullets:
            bullet_count += len(bullets)
        elif desc:
            lines = [b.strip() for b in desc.split("\n") if b.strip()]
            bullet_count += len(lines)
            
    if bullet_count < 3:
        missing_fields.append("Work Experience bullets count is less than 3")
        
    # 2. Check education degree and institution
    edu_list = parsed_text.get("education") or []
    if not edu_list:
        missing_fields.append("Education section is missing")
    else:
        for i, edu in enumerate(edu_list):
            degree = edu.get("degree") or edu.get("specialization") or ""
            institution = edu.get("institution") or edu.get("school") or ""
            if not degree.strip():
                missing_fields.append(f"Education degree is missing in entry {i+1}")
            if not institution.strip():
                missing_fields.append(f"Education institution is missing in entry {i+1}")
                
    # 3. Check skills
    skills = parsed_text.get("technical_skills") or parsed_text.get("skills") or {}
    has_skills = False
    if isinstance(skills, dict):
        has_skills = any(v for v in skills.values())
    elif isinstance(skills, list):
        has_skills = len(skills) > 0
    else:
        has_skills = bool(skills)
        
    if not has_skills:
        missing_fields.append("Skills section is empty or missing")
        
    # 4. Check word count of the dictionary
    def count_words(obj: Any) -> int:
        if isinstance(obj, str):
            return len(obj.split())
        elif isinstance(obj, list):
            return sum(count_words(x) for x in obj)
        elif isinstance(obj, dict):
            return sum(count_words(v) for v in obj.values())
        return 0
        
    word_count = count_words(parsed_text)
    if word_count < 150:
        missing_fields.append(f"Total word count is {word_count} (minimum required: 150)")
        
    has_sufficient_info = len(missing_fields) == 0
    return has_sufficient_info, missing_fields
