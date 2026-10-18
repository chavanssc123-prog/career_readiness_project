def calculate_profile_completion(profile: dict) -> int:
    if not profile:
        return 0

    cgpa = float(profile.get("cgpa", 0) or 0)
    communication = float(profile.get("communication", 0) or 0)
    logical = float(profile.get("logical_reasoning", 0) or 0)
    projects_count = float(profile.get("projects_count", 0) or 0)
    certifications_count = float(profile.get("certifications_count", 0) or 0)
    internship_count = float(profile.get("internship_count", 0) or 0)

    cgpa_score = min(max(cgpa / 10.0, 0.0), 1.0) * 15
    communication_score = min(max(communication / 10.0, 0.0), 1.0) * 15
    logical_score = min(max(logical / 10.0, 0.0), 1.0) * 15
    projects_score = min(projects_count, 5.0) / 5.0 * 15
    certification_score = min(certifications_count, 5.0) / 5.0 * 15
    internship_score = min(internship_count, 2.0) / 2.0 * 15
    interest_score = 10 if profile.get("interest_domain") else 0

    total = (
        cgpa_score
        + communication_score
        + logical_score
        + projects_score
        + certification_score
        + internship_score
        + interest_score
    )
    return min(int(round(total)), 100)
