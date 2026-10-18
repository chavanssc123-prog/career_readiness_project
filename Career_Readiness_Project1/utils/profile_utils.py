def calculate_profile_completion(profile: dict) -> int:
    if not profile:
        return 0

    cgpa_score = min(max(profile.get("cgpa", 0) / 10.0, 0.0), 1.0) * 15
    communication_score = min(max(profile.get("communication", 0) / 10.0, 0.0), 1.0) * 15
    logical_score = min(max(profile.get("logical_reasoning", 0) / 10.0, 0.0), 1.0) * 15
    projects_score = min(profile.get("projects_count", 0), 5) / 5.0 * 15
    certification_score = min(profile.get("certifications_count", 0), 5) / 5.0 * 15
    internship_score = min(profile.get("internship_count", 0), 2) / 2.0 * 15
    interest_score = 10 if profile.get("interest_domain") else 0

    total = cgpa_score + communication_score + logical_score + projects_score + certification_score + internship_score + interest_score
    return min(int(round(total)), 100)
