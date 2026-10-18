from collections import Counter
from typing import Dict, List, Optional, Tuple

from mysql.connector import Error

from database.db_connection import create_connection
from utils.analytics_utils import calculate_resume_ats_score, infer_career_category, normalize_comma_separated_list


def _execute_query(query: str, params: Tuple = ()):
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        return cursor.fetchall()
    except Error as error:
        raise RuntimeError(f"Unable to execute admin query: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def _execute_scalar(query: str, params: Tuple = ()) -> int:
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except Error as error:
        raise RuntimeError(f"Unable to execute admin scalar query: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_system_overview() -> Dict[str, int]:
    return {
        "total_users": _execute_scalar("SELECT COUNT(*) FROM users"),
        "total_profiles": _execute_scalar("SELECT COUNT(*) FROM profiles"),
        "total_resumes": _execute_scalar("SELECT COUNT(*) FROM resume_data"),
        "total_career_predictions": _execute_scalar("SELECT COUNT(*) FROM career_predictions"),
        "total_skill_gap_analyses": _execute_scalar("SELECT COUNT(*) FROM skill_gap"),
        "total_roadmaps": _execute_scalar("SELECT COUNT(*) FROM roadmaps"),
    }


def get_latest_registered_users(limit: int = 5) -> List[Dict]:
    query = (
        "SELECT id, name, email, created_at FROM users "
        "ORDER BY created_at DESC LIMIT %s"
    )
    return _execute_query(query, (limit,))


def get_user_activity_scores(limit: int = 5) -> List[Dict]:
    query = (
        "SELECT u.id, u.name, u.email, "
        "IF(p.id IS NOT NULL, 1, 0) AS has_profile, "
        "IF(r.id IS NOT NULL, 1, 0) AS has_resume, "
        "IF(cp.id IS NOT NULL, 1, 0) AS has_prediction, "
        "IF(sg.id IS NOT NULL, 1, 0) AS has_skill_gap, "
        "IF(rm.id IS NOT NULL, 1, 0) AS has_roadmap "
        "FROM users u "
        "LEFT JOIN profiles p ON p.user_id = u.id "
        "LEFT JOIN resume_data r ON r.user_id = u.id "
        "LEFT JOIN career_predictions cp ON cp.user_id = u.id "
        "LEFT JOIN skill_gap sg ON sg.user_id = u.id "
        "LEFT JOIN roadmaps rm ON rm.user_id = u.id "
        "GROUP BY u.id"
    )
    results = _execute_query(query)
    for record in results:
        record["activity_score"] = (
            record["has_profile"]
            + record["has_resume"]
            + record["has_prediction"]
            + record["has_skill_gap"]
            + record["has_roadmap"]
        )
    results.sort(key=lambda row: row["activity_score"], reverse=True)
    return results[:limit]


def get_user_readiness_scores(limit: int = 5, highest: bool = True) -> List[Dict]:
    query = (
        "SELECT u.id, u.name, u.email, sg.readiness_score, sg.skill_match_score, sg.career_role "
        "FROM users u "
        "JOIN skill_gap sg ON sg.user_id = u.id "
        "JOIN (SELECT user_id, MAX(created_at) AS max_created_at FROM skill_gap GROUP BY user_id) latest "
        "ON latest.user_id = sg.user_id AND latest.max_created_at = sg.created_at "
        "ORDER BY sg.readiness_score %s LIMIT %s"
    )
    order = "DESC" if highest else "ASC"
    query = query % order
    return _execute_query(query, (limit,))


def get_career_recommendation_summary() -> List[Dict]:
    query = (
        "SELECT recommended_role, COUNT(*) AS count "
        "FROM career_predictions "
        "GROUP BY recommended_role "
        "ORDER BY count DESC"
    )
    return _execute_query(query)


def get_most_selected_careers() -> List[Dict]:
    query = (
        "SELECT selected_role AS career_role, COUNT(*) AS count "
        "FROM career_predictions "
        "GROUP BY selected_role "
        "ORDER BY count DESC"
    )
    return _execute_query(query)


def get_career_selection_counts() -> Dict[str, int]:
    query = (
        "SELECT "
        "SUM(CASE WHEN selected_role = predicted_role THEN 1 ELSE 0 END) AS ai_recommendations, "
        "SUM(CASE WHEN selected_role <> predicted_role THEN 1 ELSE 0 END) AS user_overrides "
        "FROM career_predictions"
    )
    rows = _execute_query(query)
    if rows:
        row = rows[0]
        return {
            "total_ai_recommendations": int(row.get("ai_recommendations") or 0),
            "total_user_overrides": int(row.get("user_overrides") or 0),
        }
    return {"total_ai_recommendations": 0, "total_user_overrides": 0}


def get_career_override_statistics() -> List[Dict]:
    query = (
        "SELECT selected_role AS career_role, COUNT(*) AS override_count "
        "FROM career_predictions "
        "WHERE selected_role <> predicted_role "
        "GROUP BY selected_role "
        "ORDER BY override_count DESC"
    )
    return _execute_query(query)


def get_career_domain_distribution() -> Dict[str, int]:
    query = "SELECT recommended_role FROM career_predictions"
    rows = _execute_query(query)
    category_counter = Counter()
    for row in rows:
        category_counter[infer_career_category(row["recommended_role"])] += 1
    return dict(category_counter)


def get_skill_gap_summary() -> Dict[str, object]:
    query = "SELECT missing_skills, matched_skills, skill_match_score, readiness_score FROM skill_gap"
    rows = _execute_query(query)
    missing_counter = Counter()
    matched_counter = Counter()
    total_skill_match = 0.0
    total_readiness = 0.0
    count = 0
    for row in rows:
        missing_skills = normalize_comma_separated_list(row.get("missing_skills"))
        matched_skills = normalize_comma_separated_list(row.get("matched_skills"))
        missing_counter.update(missing_skills)
        matched_counter.update(matched_skills)
        total_skill_match += float(row.get("skill_match_score") or 0.0)
        total_readiness += float(row.get("readiness_score") or 0.0)
        count += 1
    return {
        "most_missing_skills": missing_counter.most_common(5),
        "most_common_skills": matched_counter.most_common(5),
        "average_skill_match_score": round(total_skill_match / count, 2) if count else 0.0,
        "average_readiness_score": round(total_readiness / count, 2) if count else 0.0,
    }


def get_resume_analytics() -> Dict[str, object]:
    query = "SELECT skills FROM resume_data"
    rows = _execute_query(query)
    skill_counter = Counter()
    ats_scores = []
    for row in rows:
        skills = normalize_comma_separated_list(row.get("skills"))
        skill_counter.update(skills)
        resume_data = {"skills": ", ".join(skills), "projects": "", "certifications": "", "education": ""}
        ats_scores.append(calculate_resume_ats_score(row))
    return {
        "average_ats_score": round(sum(ats_scores) / len(ats_scores), 2) if ats_scores else 0.0,
        "total_resumes": len(rows),
        "most_common_skills": skill_counter.most_common(5),
    }


def get_roadmap_analytics() -> Dict[str, object]:
    query = (
        "SELECT career_role, COUNT(*) AS count, AVG(duration_months) AS average_duration "
        "FROM roadmaps "
        "GROUP BY career_role "
        "ORDER BY count DESC"
    )
    rows = _execute_query(query)
    return {
        "most_generated_roadmaps": [(row["career_role"], int(row["count"])) for row in rows[:5]],
        "average_roadmap_duration": round(sum(row["average_duration"] for row in rows) / len(rows), 2) if rows else 0.0,
    }


def get_database_health() -> Dict[str, object]:
    health = {"connected": False, "tables_found": [], "total_records": {}}
    connection = None
    try:
        connection = create_connection()
        health["connected"] = True
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        health["database"] = cursor.fetchone()[0]
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        health["tables_found"] = tables
        for table in ["users", "profiles", "resume_data", "career_predictions", "skill_gap", "roadmaps"]:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                health["total_records"][table] = int(cursor.fetchone()[0])
            else:
                health["total_records"][table] = 0
    except Error as error:
        raise RuntimeError(f"Unable to fetch database health: {error}")
    finally:
        if connection and connection.is_connected():
            connection.close()
    return health


def search_users(name: Optional[str] = None, email: Optional[str] = None, career_role: Optional[str] = None) -> List[Dict]:
    query = (
        "SELECT u.id, u.name, u.email, u.created_at, p.interest_domain, cp.recommended_role, cp.confidence_score "
        "FROM users u "
        "LEFT JOIN profiles p ON p.user_id = u.id "
        "LEFT JOIN (" 
        "  SELECT user_id, recommended_role, confidence_score, prediction_date "
        "  FROM career_predictions cp1 "
        "  JOIN (SELECT user_id, MAX(prediction_date) AS latest_prediction FROM career_predictions GROUP BY user_id) cp2 "
        "  ON cp1.user_id = cp2.user_id AND cp1.prediction_date = cp2.latest_prediction "
        ") cp ON cp.user_id = u.id "
        "WHERE 1=1 "
    )
    params: List = []
    if name:
        query += " AND u.name LIKE %s"
        params.append(f"%{name}%")
    if email:
        query += " AND u.email LIKE %s"
        params.append(f"%{email}%")
    if career_role:
        query += " AND cp.recommended_role LIKE %s"
        params.append(f"%{career_role}%")
    query += " ORDER BY u.created_at DESC"
    return _execute_query(query, tuple(params))
