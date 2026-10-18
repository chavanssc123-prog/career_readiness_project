import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from database.db_utils import (
    create_profile,
    create_user,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    update_profile,
)
from database.admin_db import (
    get_system_overview,
    get_latest_registered_users,
    get_user_activity_scores,
    get_user_readiness_scores,
    get_career_recommendation_summary,
    get_career_domain_distribution,
    get_skill_gap_summary,
    get_resume_analytics,
    get_roadmap_analytics,
    get_database_health,
    search_users,
    get_most_selected_careers,
    get_career_selection_counts,
    get_career_override_statistics,
)
from database.roadmap_db import (
    create_roadmap_table_if_missing,
    get_latest_roadmap,
    save_roadmap,
)
from database.resume_db import create_resume_data, get_resume_data_by_user, update_resume_data
from database.career_db import create_career_predictions_table_if_missing, get_latest_career_prediction, save_career_prediction, update_latest_career_prediction
from database.skill_gap_db import create_skill_gap_table_if_missing, get_latest_skill_gap_analysis, save_skill_gap_analysis
from models.predict import predict_career
from resume_parser.parser import parse_resume
from utils.analytics_utils import (
    build_skill_gap_counts,
    calculate_resume_ats_score,
    compute_overall_readiness,
    generate_analytics_insights,
    infer_career_category,
    normalize_comma_separated_list,
)
from utils.auth import hash_password, verify_password
from utils.career_utils import build_profile_features, build_resume_features
from utils.profile_utils import calculate_profile_completion
from utils.resume_utils import (
    ALLOWED_RESUME_EXTENSIONS,
    MAX_RESUME_SIZE_BYTES,
    ensure_resume_upload_dir,
    save_uploaded_resume,
    calculate_resume_completeness,
)
from utils.skill_gap_utils import (
    build_current_skills,
    calculate_readiness_score,
    calculate_skill_match_score,
    categorize_skills_by_priority,
    compute_skill_gap,
    format_skill_list,
    get_required_skills_for_career,
)
from utils.pdf_report_utils import generate_career_report_pdf
from utils.roadmap_utils import (
    build_monthly_roadmap,
    build_roadmap_summary,
    get_certification_recommendations,
    get_project_recommendations,
)
from utils.session_manager import init_session, is_authenticated, is_admin, login_user, logout_user
from utils.validators import validate_registration


def set_page_config():
    st.set_page_config(
        page_title="AI Career Readiness & Skill Gap Analyzer",
        page_icon="ðŸš€",
        layout="wide",
    )


def load_css():
    css_path = Path(__file__).resolve().parent / "static" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = "", icon: str = "âœ¨"):
    subtitle_html = f"<p class='section-subtitle'>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class='section-header'>
            <div class='section-title'>
                <span class='section-icon'>{icon}</span>
                <div>
                    <h2>{title}</h2>
                    {subtitle_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, delta: str = None, icon: str = ""):
    delta_html = f"<span class='metric-delta'>{delta}</span>" if delta else ""
    icon_html = f"<span class='metric-icon'>{icon}</span>" if icon else ""
    st.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-card-header'>{icon_html}<span>{title}</span></div>
            <div class='metric-card-value'>{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title: str, content: str, icon: str = ""):
    icon_html = f"<span class='info-card-icon'>{icon}</span>" if icon else ""
    st.markdown(
        f"""
        <div class='info-card'>
            <div class='info-card-title'>{icon_html}<span>{title}</span></div>
            <div class='info-card-content'>{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_badge(text: str, variant: str = "info"):
    st.markdown(
        f"<span class='status-badge status-{variant}'>{text}</span>",
        unsafe_allow_html=True,
    )


def _build_recommendation_reason(career: str, resume_skills: list) -> str:
    if not resume_skills:
        return "Recommendation based on your profile and resume skills."

    normalized = [skill.strip() for skill in resume_skills if skill]
    key_skills = [skill for skill in normalized if skill.lower() in [
        "aws", "docker", "linux", "kubernetes", "cloud", "python", "sql", "machine learning", "data analysis"
    ]]
    if not key_skills:
        key_skills = normalized[:4]

    reason_skills = ", ".join(key_skills[:4])
    return f"Strong {reason_skills} skills supporting this career recommendation."


def _render_recommendation_card(career: str, confidence: float, reason: str, selection_type: str):
    badge_label = "AI Recommended" if selection_type == "AI Recommended" else "User Selected"
    st.markdown(
        f"""
        <div class='card-box'>
            <h3>AI Recommended Career</h3>
            <p><strong>{career}</strong></p>
            <p><strong>Confidence Score:</strong> {confidence:.1f}%</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p><span class='badge admin-badge'>{badge_label}</span></p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_theme(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(family="Inter, sans-serif", color="#102a43"),
        title_font=dict(size=18, family="Inter, sans-serif", color="#082032"),
        legend=dict(bgcolor="rgba(255,255,255,0.80)", bordercolor="#dfe2ec", borderwidth=1),
        margin=dict(t=40, r=20, l=20, b=20),
    )
    return fig


def render_gauge_card(title: str, value: float, suffix: str = "%", color: str = "#0b3d91"):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix},
            title={"text": title, "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#102a43"},
                "bar": {"color": color},
                "bgcolor": "#f5f7ff",
                "borderwidth": 1,
                "bordercolor": "#dfe2ec",
            },
        )
    )
    apply_plotly_theme(fig)
    fig.update_layout(height=280)
    st.plotly_chart(fig, use_container_width=True)


def render_sidebar():
    # Sidebar Brand
    st.sidebar.markdown(
        """
        <div class='sidebar-brand'>
            <h1>CareerAI</h1>
            <p>Intelligent Career Platform</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    nav_labels = {
        "Home": "ðŸ ",
        "Login": "ðŸ”",
        "Register": "ðŸ“",
        "Profile": "ðŸ‘¤",
        "Resume Upload": "ðŸ“„",
        "Dashboard": "ðŸ“Š",
        "Admin Dashboard": "ðŸ› ï¸",
        "Analytics Dashboard": "ðŸ“ˆ",
        "PDF Career Report": "ðŸ“‘",
        "Career Recommendation": "ðŸŽ¯",
        "Skill Gap Analysis": "âš¡",
        "Roadmap Generator": "ðŸ—ºï¸",
    }
    
    menu_items = ["Home", "Login", "Register", "Profile", "Resume Upload"]

    if is_authenticated():
        menu_items = ["Home", "Dashboard", "Profile", "Resume Upload"]
        if is_admin():
            menu_items.append("Admin Dashboard")
        menu_items.extend([
            "Analytics Dashboard",
            "PDF Career Report",
            "Career Recommendation",
            "Skill Gap Analysis",
            "Roadmap Generator",
        ])

        # User Profile Card
        user_badge_class = "badge-success" if is_admin() else "badge-info"
        st.sidebar.markdown(
            f"""
            <div class='sidebar-profile-card'>
                <h3>ðŸ‘¤ {st.session_state.user_name or 'Guest User'}</h3>
                <p>{st.session_state.get('user_role', 'user').title()}</p>
                <span class='badge {user_badge_class}'>{st.session_state.get('user_role', 'user').upper()}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Navigation with buttons for better styling
    selection = None
    for item in menu_items:
        icon = nav_labels.get(item, '')
        label = f"{icon}  {item}"
        
        # Check if this is the current page (we'll determine this from session state or default to Home)
        is_active = False
        if 'current_page' in st.session_state and st.session_state.current_page == item:
            is_active = True
        
        button_type = "primary" if is_active else "secondary"
        
        if st.sidebar.button(label, key=f"nav_{item}", type=button_type, use_container_width=True):
            selection = item
            st.session_state.current_page = item
    
    # Default selection
    if selection is None:
        selection = st.session_state.get("current_page", menu_items[0])
        if selection not in menu_items:
            selection = menu_items[0]
            st.session_state.current_page = selection
    
    st.sidebar.markdown("---")
    
    # Logout Button
    if is_authenticated():
        if st.sidebar.button("ðŸšª Logout", use_container_width=True, type="secondary"):
            logout_user()
            st.rerun()
    
    return selection


def analytics_dashboard_page():
    render_section_header(
        "Advanced Analytics Dashboard",
        "A consolidated analytics view built from your stored profile, resume, career recommendation, skill gap analysis, and roadmap data.",
        icon="ðŸ“ˆ",
    )

    user_id = st.session_state.user_id
    profile = get_profile_by_user_id(user_id)
    resume_data = get_resume_data_by_user(user_id)
    latest_prediction = get_latest_career_prediction(user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(user_id)
    latest_roadmap = get_latest_roadmap(user_id)

    profile_completion = calculate_profile_completion(profile)
    ats_score = calculate_resume_ats_score(resume_data) if resume_data else 0.0
    skill_match_score = float(latest_skill_gap.get("skill_match_score") or 0.0) if latest_skill_gap else 0.0
    roadmap_progress = float(latest_roadmap.get("readiness_score") or 0.0) if latest_roadmap else 0.0
    overall_readiness = compute_overall_readiness(profile_completion, ats_score, skill_match_score, roadmap_progress)
    selected_career = None
    if latest_prediction:
        selected_career = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
    career_category = infer_career_category(selected_career)
    insights = generate_analytics_insights(
        profile,
        resume_data,
        latest_prediction,
        latest_skill_gap,
        latest_roadmap,
        profile_completion,
        ats_score,
        skill_match_score,
        roadmap_progress,
    )

    top_cols = st.columns(3)
    with top_cols[0]:
        render_metric_card("Profile Completion", f"{profile_completion}%", icon="ðŸ§­")
    with top_cols[1]:
        render_metric_card("Resume ATS Score", f"{ats_score:.1f}%", icon="ðŸ“„")
    with top_cols[2]:
        render_metric_card("Readiness Score", f"{overall_readiness}%", icon="ðŸš€")

    gauge_cols = st.columns(2)
    with gauge_cols[0]:
        render_gauge_card("ATS Score", ats_score, suffix="%", color="#3960ff")
    with gauge_cols[1]:
        render_gauge_card("Overall Readiness", overall_readiness, suffix="%", color="#0b3d91")

    st.markdown("---")

    st.markdown("---")
    st.subheader("Section 1: Profile Analytics")
    if not profile:
        st.warning("Complete your profile first to enable profile analytics.")
    profile_cols = st.columns(5)
    profile_cols[0].metric("Profile Completion", f"{profile_completion}%")
    profile_cols[1].metric("CGPA", f"{profile.get('cgpa', 'N/A'):.2f}" if profile and profile.get('cgpa') is not None else "N/A")
    profile_cols[2].metric("Projects", profile.get('projects_count', 0) if profile else 0)
    profile_cols[3].metric("Internships", profile.get('internship_count', 0) if profile else 0)
    profile_cols[4].metric("Certifications", profile.get('certifications_count', 0) if profile else 0)
    st.write(f"**Interest Domain:** {profile.get('interest_domain', 'N/A') if profile else 'N/A'}")
    st.progress(profile_completion / 100)

    st.markdown("---")
    st.subheader("Section 2: Resume Analytics")
    resume_uploaded = bool(resume_data)
    resume_cols = st.columns(4)
    resume_cols[0].metric("Resume Uploaded", "Yes" if resume_uploaded else "No")
    resume_cols[1].metric("Resume ATS Score", f"{ats_score:.1f}%")
    skills = normalize_comma_separated_list(resume_data.get('skills')) if resume_data else []
    projects = normalize_comma_separated_list(resume_data.get('projects')) if resume_data else []
    certifications = normalize_comma_separated_list(resume_data.get('certifications')) if resume_data else []
    education = normalize_comma_separated_list(resume_data.get('education')) if resume_data else []
    resume_cols[2].metric("Skills Extracted", len(skills))
    resume_cols[3].metric("Projects Extracted", len(projects))
    st.write(f"**Certifications Extracted:** {len(certifications)}")
    st.write(f"**Education Extracted:** {len(education)}")
    st.progress(ats_score / 100)

    st.markdown("---")
    st.subheader("Section 3: Career Analytics")
    if not latest_prediction:
        st.warning("Generate a career recommendation first to view career analytics.")
    else:
        selected_career = latest_prediction.get('selected_role') or latest_prediction.get('recommended_role')
        selection_type = "AI Recommended" if latest_prediction.get('selected_role') == latest_prediction.get('predicted_role') else "User Selected"
        career_card_cols = st.columns(3)
        career_card_cols[0].metric("Final Selected Career", selected_career)
        career_card_cols[1].metric("Confidence", f"{latest_prediction.get('confidence_score', 0.0):.1f}%")
        career_card_cols[2].metric("Career Category", career_category)
        st.write(f"**Prediction Date:** {latest_prediction.get('prediction_date')}")
        st.write(f"**Selection Type:** {selection_type}")

    st.markdown("---")
    st.subheader("Section 4: Skill Gap Analytics")
    if not latest_skill_gap:
        st.warning("Complete skill gap analysis first to activate skill gap charts.")
    skill_counts = build_skill_gap_counts(latest_skill_gap)
    count_df = pd.DataFrame.from_dict(skill_counts, orient='index', columns=['Count'])
    chart_cols = st.columns([2, 1])
    with chart_cols[0]:
        st.bar_chart(count_df)
    with chart_cols[1]:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            list(skill_counts.values()),
            labels=list(skill_counts.keys()),
            autopct="%1.1f%%",
            colors=["#2ecc71", "#f39c12", "#e74c3c"],
            startangle=90,
        )
        ax.axis("equal")
        st.pyplot(fig)
    st.metric("Skill Match Score", f"{skill_match_score:.2f}%")
    st.progress(skill_match_score / 100)
    st.metric("Readiness Score", f"{roadmap_progress:.2f}%")
    st.progress(roadmap_progress / 100)

    if latest_skill_gap:
        st.write("**Matched Skills:**")
        st.write(format_skill_list(normalize_comma_separated_list(latest_skill_gap.get('matched_skills'))))
        st.write("**Missing Skills:**")
        st.write(format_skill_list(normalize_comma_separated_list(latest_skill_gap.get('missing_skills'))))
        st.write("**Extra Skills:**")
        st.write(format_skill_list(normalize_comma_separated_list(latest_skill_gap.get('extra_skills'))))

    st.markdown("---")
    st.subheader("Section 5: Roadmap Analytics")
    if not latest_roadmap:
        st.warning("Save a personalized roadmap first to view roadmap analytics.")
    else:
        roadmap_cols = st.columns(3)
        roadmap_cols[0].metric("Career Role", latest_roadmap.get('career_role', 'N/A'))
        roadmap_cols[1].metric("Duration", f"{latest_roadmap.get('duration_months', 0)} months")
        roadmap_cols[2].metric("Current Readiness", f"{latest_roadmap.get('readiness_score', 0.0):.2f}%")
        st.write("**Roadmap Summary**")
        st.write(latest_roadmap.get('roadmap_text', 'No roadmap details available.'))
        project_recommendations = get_project_recommendations(latest_roadmap.get('career_role', ''))
        certification_recommendations = get_certification_recommendations(latest_roadmap.get('career_role', ''))
        st.write("**Projects Recommended**")
        for project in project_recommendations:
            st.write(f"- {project}")
        st.write("**Certifications Recommended**")
        for cert in certification_recommendations:
            st.write(f"- {cert}")

    st.markdown("---")
    st.subheader("Section 6: Readiness Dashboard")
    st.metric("Final Career Readiness", f"{overall_readiness}%")
    st.progress(overall_readiness / 100)
    st.write("This score is calculated from profile completion, resume ATS strength, skill match performance, and roadmap readiness.")

    st.markdown("---")
    st.subheader("Section 7: Insights Engine")
    if not insights:
        st.info("No insights are available yet. Complete the missing analytics steps to generate dynamic insights.")
    else:
        for insight in insights:
            st.write(f"- {insight}")


def pdf_career_report_page():
    if not is_authenticated():
        st.warning("Please log in to access the PDF Career Report.")
        login_page()
        return

    st.title("PDF Career Report")
    st.write("Generate a professional PDF report based on your stored career readiness data.")

    user = get_user_by_id(st.session_state.user_id)
    profile = get_profile_by_user_id(st.session_state.user_id)
    resume_data = get_resume_data_by_user(st.session_state.user_id)
    career_prediction = get_latest_career_prediction(st.session_state.user_id)
    skill_gap = get_latest_skill_gap_analysis(st.session_state.user_id)
    roadmap = get_latest_roadmap(st.session_state.user_id)

    missing = []
    if not profile:
        missing.append("Profile data")
    if not resume_data:
        missing.append("Resume data")
    if not career_prediction:
        missing.append("Career recommendation")
    if not skill_gap:
        missing.append("Skill gap analysis")
    if not roadmap:
        missing.append("Personalized roadmap")

    if missing:
        st.warning("Cannot generate report until all sections are complete.")
        for section in missing:
            st.write(f"- {section}")
        return

    ats_score = calculate_resume_ats_score(resume_data)
    selected_career = career_prediction.get("selected_role") or career_prediction.get("recommended_role")
    career_category = infer_career_category(selected_career)
    overall_readiness = compute_overall_readiness(
        calculate_profile_completion(profile),
        ats_score,
        float(skill_gap.get("skill_match_score", 0.0) or 0.0),
        float(roadmap.get("readiness_score", 0.0) or 0.0),
    )
    selection_type = "AI Recommended" if career_prediction.get("selected_role") == career_prediction.get("predicted_role") else "User Selected"
    analytics_summary = {
        "career_category": career_category,
        "ats_score": ats_score,
        "profile_completion": calculate_profile_completion(profile),
        "skill_match_score": float(skill_gap.get("skill_match_score", 0.0) or 0.0),
        "roadmap_progress": float(roadmap.get("readiness_score", 0.0) or 0.0),
        "overall_readiness": overall_readiness,
        "projects": get_project_recommendations(selected_career),
        "certifications": get_certification_recommendations(selected_career),
        "selection_type": selection_type,
        "ai_recommended_career": career_prediction.get("recommended_role"),
        "final_selected_career": selected_career,
    }

    if st.button("Generate PDF Report"):
        try:
            report_bytes = generate_career_report_pdf(
                user,
                profile,
                resume_data,
                career_prediction,
                skill_gap,
                roadmap,
                analytics_summary,
            )

            st.success("PDF report generated successfully.")
            st.download_button(
                label="Download Career Report",
                data=report_bytes,
                file_name=f"career_report_{st.session_state.user_id}.pdf",
                mime="application/pdf",
            )
        except Exception as error:
            st.error(f"Unable to generate PDF report: {error}")


def home_page():
    # Hero Section - Matching Lovable Design
    st.markdown(
        """
        <div class='hero-section'>
            <div style='position: relative; z-index: 1; max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6);'>
                <div class='inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-white/90 mb-6'>
                    <span>âœ¨</span>
                    <span>Powered by AI Â· Scikit-Learn models trained on 50k+ careers</span>
                </div>
                <h1 class='hero-title'>Build Your <span class='text-gradient' style='background: linear-gradient(135deg, #fff 0%, #e0e7ff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Career Roadmap</span> with AI</h1>
                <p class='hero-subtitle'>
                    Analyze your resume. Identify skill gaps. Get personalized career recommendations and a month-by-month learning roadmap â€” built for the next generation of professionals.
                </p>
                <div class='hero-buttons'>
                    <button class='hero-button hero-button-primary' onclick="document.getElementById('get-started').click()">
                        Get Started
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M5 12h14"></path>
                            <path d="m12 5 7 7-7 7"></path>
                        </svg>
                    </button>
                    <button class='hero-button hero-button-secondary' onclick="document.getElementById('upload-resume').click()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 3v12"></path>
                            <path d="m17 8-5-5-5 5"></path>
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        </svg>
                        Upload Resume
                    </button>
                    <button class='hero-button hero-button-secondary' onclick="document.getElementById('watch-demo').click()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"></path>
                        </svg>
                        Watch Demo
                    </button>
                </div>
                <div class='mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 text-sm text-white/80'>
                    <div class='flex items-center gap-2'>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <path d="m9 12 2 2 4-4"></path>
                        </svg>
                        Free for students
                    </div>
                    <div class='flex items-center gap-2'>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <path d="m9 12 2 2 4-4"></path>
                        </svg>
                        No credit card
                    </div>
                    <div class='flex items-center gap-2'>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <path d="m9 12 2 2 4-4"></path>
                        </svg>
                        PDF report included
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Hidden buttons for functionality
    with st.container():
        if st.button("Get Started", key="get-started", type="primary", use_container_width=True):
            if is_authenticated():
                st.session_state.current_page = "Dashboard"
                st.rerun()
            else:
                st.session_state.current_page = "Register"
                st.rerun()
        
        if st.button("Upload Resume", key="upload-resume", type="secondary", use_container_width=True):
            if is_authenticated():
                st.session_state.current_page = "Resume Upload"
                st.rerun()
            else:
                st.session_state.current_page = "Register"
                st.rerun()
        
        if st.button("Watch Demo", key="watch-demo", type="secondary", use_container_width=True):
            st.info("Demo video coming soon! Start by creating your profile and uploading your resume.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # How It Works Section - Matching Lovable
    st.markdown(
        """
        <div style='background: var(--surface); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: var(--space-24) 0;'>
            <div style='max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6);'>
                <div style='max-width: 600px;'>
                    <div style='font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--primary);'>How it works</div>
                    <h2 style='margin-top: var(--space-3); font-family: var(--font-display); font-weight: 800; letter-spacing: -0.02em;'>From resume to roadmap in minutes</h2>
                    <p style='margin-top: var(--space-3); color: var(--muted-foreground);'>Seven AI-guided steps designed for students, freshers, and career switchers.</p>
                </div>
        """,
        unsafe_allow_html=True,
    )
    
    # 8 Steps Grid - Matching Lovable
    steps_data = [
        ("ðŸ‘¤", "Profile", "Academic & interest profile.", "01"),
        ("ðŸ“„", "Resume Upload", "Drag-and-drop resume parsing.", "02"),
        ("ðŸ¤–", "AI Analysis", "Extract skills, projects, education.", "03"),
        ("âœ¨", "Career Match", "AI-recommended career path.", "04"),
        ("ðŸŽ¯", "Skill Gap", "Matched, missing & extra skills.", "05"),
        ("ðŸ—ºï¸", "Roadmap", "6-month milestone plan.", "06"),
        ("ðŸ“ˆ", "Analytics", "Track readiness trends.", "07"),
        ("ðŸ“‘", "Career Report", "Premium PDF download.", "08"),
    ]
    
    steps_cols = st.columns(4)
    for idx, (icon, title, desc, number) in enumerate(steps_data):
        with steps_cols[idx % 4]:
            st.markdown(
                f"""
                <div class='card-box' style='text-align: center; margin-bottom: var(--space-4);'>
                    <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-4);'>
                        <div style='width: 44px; height: 44px; border-radius: var(--radius-xl); background: var(--gradient-primary); display: flex; align-items: center; justify-content: center; color: white; font-size: 1.25rem; box-shadow: var(--shadow-glow);'>
                            {icon}
                        </div>
                        <span style='font-size: var(--text-xs); font-family: monospace; color: var(--muted-foreground);'>{number}</span>
                    </div>
                    <div style='font-family: var(--font-display); font-weight: 600; margin-bottom: var(--space-1);'>{title}</div>
                    <p style='font-size: var(--text-sm); color: var(--muted-foreground); margin: 0;'>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    
    # Benefits Section - Matching Lovable
    st.markdown(
        """
        <div style='padding: var(--space-24) 0;'>
            <div style='max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6); grid lg:grid-cols-2 gap-12;'>
                <div>
                    <div style='font-size: var(--text-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--secondary);'>Why CareerForge</div>
                    <h2 style='margin-top: var(--space-3); font-family: var(--font-display); font-weight: 800; letter-spacing: -0.02em;'>Built for the next generation of professionals</h2>
                    <p style='margin-top: var(--space-4); color: var(--muted-foreground); line-height: 1.7;'>Replace guesswork with measurable career intelligence. Trained on real industry data and tailored to your goals.</p>
                </div>
                <div style='display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-4);'>
        """,
        unsafe_allow_html=True,
    )
    
    benefits = [
        ("ðŸ§ ", "AI Resume Parsing", "Extract skills, projects, and certificates with NLP."),
        ("ðŸŽ¯", "Hybrid Recommendation", "Pick AI's suggestion or set your own career."),
        ("ðŸ“Š", "Readiness Score", "Quantify exactly how job-ready you are today."),
        ("ðŸ†", "Premium PDF Report", "Share-ready career portfolio in one click."),
    ]
    
    benefits_cols = st.columns(2)
    for idx, (icon, title, desc) in enumerate(benefits):
        with benefits_cols[idx % 2]:
            st.markdown(
                f"""
                <div class='card-box'>
                    <div style='width: 40px; height: 40px; border-radius: var(--radius-lg); background: rgba(6, 182, 212, 0.15); color: var(--accent); display: flex; align-items: center; justify-content: center; font-size: 1.25rem; margin-bottom: var(--space-4);'>
                        {icon}
                    </div>
                    <div style='font-weight: 600; margin-bottom: var(--space-2);'>{title}</div>
                    <p style='font-size: var(--text-sm); color: var(--muted-foreground); margin: 0;'>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    st.markdown("</div></div></div>", unsafe_allow_html=True)
    
    # Metrics Section - Matching Lovable
    st.markdown(
        """
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: var(--space-20) 0; position: relative; overflow: hidden;'>
            <div style='position: absolute; inset: 0; background: var(--gradient-mesh); opacity: 0.3;'></div>
            <div style='relative; max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6); position: relative;'>
                <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-8);'>
        """,
        unsafe_allow_html=True,
    )
    
    metrics = [
        ("ðŸ“„", "50k+", "Resumes analyzed"),
        ("ðŸ—ºï¸", "120+", "Career paths mapped"),
        ("âœ¨", "94%", "Avg. recommendation accuracy"),
        ("â­", "4.9/5", "Student rating"),
    ]
    
    metrics_cols = st.columns(4)
    for idx, (icon, value, label) in enumerate(metrics):
        with metrics_cols[idx]:
            st.markdown(
                f"""
                <div style='background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); backdrop-filter: blur(10px); border-radius: var(--radius-2xl); padding: var(--space-6);'>
                    <div style='opacity: 0.7;'>{icon}</div>
                    <div style='margin-top: var(--space-4); font-family: var(--font-display); font-size: var(--text-4xl); font-weight: 800;'>{value}</div>
                    <div style='margin-top: var(--space-1); font-size: var(--text-sm); opacity: 0.8;'>{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    st.markdown("</div></div></div>", unsafe_allow_html=True)
    
    # Final CTA Section - Matching Lovable
    st.markdown(
        """
        <div style='padding: var(--space-24) 0; text-align: center;'>
            <div style='max-width: 800px; margin: 0 auto; padding: 0 var(--space-6);'>
                <div class='inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground mb-6'>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
                    </svg>
                    Trusted by students from 200+ campuses
                </div>
                <h2 style='font-family: var(--font-display); font-weight: 800; letter-spacing: -0.02em; margin-bottom: var(--space-4);'>Your career, planned by AI.</h2>
                <p style='color: var(--muted-foreground); max-width: 500px; margin: 0 auto var(--space-8); line-height: 1.7;'>Start your free career readiness analysis today â€” your personalized roadmap is minutes away.</p>
                <div style='display: flex; gap: var(--space-4); justify-content: center; flex-wrap: wrap;'>
        """,
        unsafe_allow_html=True,
    )
    
    cta_cols = st.columns([1, 1, 1])
    with cta_cols[0]:
        if st.button("Get Started Free â†’", type="primary", use_container_width=True):
            if is_authenticated():
                st.session_state.current_page = "Dashboard"
                st.rerun()
            else:
                st.session_state.current_page = "Register"
                st.rerun()
    
    with cta_cols[1]:
        if st.button("View Sample Dashboard", type="secondary", use_container_width=True):
            if is_authenticated():
                st.session_state.current_page = "Dashboard"
                st.rerun()
            else:
                st.session_state.current_page = "Register"
                st.rerun()
    
    st.markdown("</div></div></div>", unsafe_allow_html=True)
    
    # Footer - Matching Lovable
    st.markdown(
        """
        <div style='border-top: 1px solid var(--border); padding: var(--space-10) 0;'>
            <div style='max-width: 1200px; margin: 0 auto; padding: 0 var(--space-6); display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: var(--space-4); font-size: var(--text-sm); color: var(--muted-foreground);'>
                <div style='display: flex; align-items: center; gap: var(--space-2);'>
                    <div style='width: 28px; height: 28px; border-radius: var(--radius-lg); background: var(--gradient-primary); display: flex; align-items: center; justify-content: center; color: white;'>ðŸŽ“</div>
                    <span>Â© 2026 CareerForge AI. All rights reserved.</span>
                </div>
                <div style='display: flex; gap: var(--space-6);'>
                    <a href='#' style='color: inherit; text-decoration: none;'>Privacy</a>
                    <a href='#' style='color: inherit; text-decoration: none;'>Terms</a>
                    <a href='#' style='color: inherit; text-decoration: none;'>Contact</a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def home_page_phase1():
    st.markdown("<div class='cf-home' id='top'>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class='cf-topbar'>
            <div class='cf-topbar-inner'>
                <a class='cf-brand' href='#top'>
                    <span class='cf-brand-mark'>C</span>
                    <span>CareerForge AI</span>
                </a>
                <nav class='cf-nav-links'>
                    <a href='#how'>How it works</a>
                    <a href='#benefits'>Benefits</a>
                    <a href='#metrics'>Metrics</a>
                </nav>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<section class='cf-hero'><div class='cf-section-inner cf-hero-grid'>", unsafe_allow_html=True)
    hero_left, hero_right = st.columns([1.08, 1], gap="large")
    with hero_left:
        st.markdown(
            """
            <div class='cf-pill cf-hero-pill'><span class='cf-sparkle'>*</span><span>Powered by AI - Scikit-Learn models trained on 50k+ careers</span></div>
            <h1 class='cf-hero-title'>Build Your <span>Career Roadmap</span> with AI</h1>
            <p class='cf-hero-copy'>Analyze your resume. Identify skill gaps. Get personalized career recommendations and a month-by-month learning roadmap - built for the next generation of professionals.</p>
            """,
            unsafe_allow_html=True,
        )
        hero_buttons = st.columns([0.9, 1.05, 0.95, 2.1], gap="small")
        with hero_buttons[0]:
            if st.button("Get Started ->", key="home_hero_get_started", type="primary", use_container_width=True):
                st.session_state.current_page = "Dashboard" if is_authenticated() else "Register"
                st.rerun()
        with hero_buttons[1]:
            if st.button("Upload Resume", key="home_hero_upload", type="secondary", use_container_width=True):
                st.session_state.current_page = "Resume Upload" if is_authenticated() else "Register"
                st.rerun()
        with hero_buttons[2]:
            if st.button("Watch Demo", key="home_hero_demo", type="secondary", use_container_width=True):
                st.info("Demo video coming soon! Start by creating your profile and uploading your resume.")
        st.markdown(
            """
            <div class='cf-trust-row'>
                <span>âœ“ Free for students</span>
                <span>âœ“ No credit card</span>
                <span>âœ“ PDF report included</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_right:
        st.markdown(
            """
            <div class='cf-preview-card'>
                <div class='cf-preview-top'><span class='cf-dot red'></span><span class='cf-dot yellow'></span><span class='cf-dot green'></span><span>Career Readiness - Live Preview</span></div>
                <div class='cf-preview-body'>
                    <div class='cf-preview-head'><div><div class='cf-kicker'>AI Recommended Career</div><h3>Data Scientist</h3></div><div class='cf-match'>94% match</div></div>
                    <div class='cf-progress-label'><span>Readiness score</span><strong>78 / 100</strong></div>
                    <div class='cf-progress'><span></span></div>
                    <div class='cf-score-grid'>
                        <div><strong class='green-text'>18</strong><span>Matched skills</span></div>
                        <div><strong class='orange-text'>6</strong><span>Missing skills</span></div>
                        <div><strong class='blue-text'>4</strong><span>Extra skills</span></div>
                    </div>
                    <div class='cf-roadmap-mini'>
                        <div class='cf-roadmap-title'>6-month roadmap</div>
                        <div class='cf-months'><span class='done'>M1</span><span class='done'>M2</span><span class='active'>M3</span><span class='active'>M4</span><span>M5</span><span>M6</span></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div></section>", unsafe_allow_html=True)

    st.markdown(
        """
        <section class='cf-how phase2-section' id='how'>
            <div class='cf-section-inner'>
                <div class='cf-section-heading feature-heading'>
                    <div class='cf-label primary'>How it works</div>
                    <h2>From resume to roadmap in minutes</h2>
                    <p>Seven AI-guided steps designed for students, freshers, and career switchers.</p>
                </div>
        """,
        unsafe_allow_html=True,
    )
    steps_data = [
        ("Profile", "Academic & interest profile.", "01", "cap"),
        ("Resume Upload", "Drag-and-drop resume parsing.", "02", "upload"),
        ("AI Analysis", "Extract skills, projects, education.", "03", "brain"),
        ("Career Match", "AI-recommended career path.", "04", "target"),
        ("Skill Gap", "Matched, missing & extra skills.", "05", "circle"),
        ("Roadmap", "6-month milestone plan.", "06", "map"),
        ("Analytics", "Track readiness trends.", "07", "chart"),
        ("Career Report", "Premium PDF download.", "08", "file"),
    ]
    for row_start in range(0, len(steps_data), 4):
        row_cols = st.columns(4, gap="medium")
        for col, (title, desc, number, icon_class) in zip(row_cols, steps_data[row_start:row_start + 4]):
            with col:
                st.markdown(
                    f"""
                    <div class='cf-step-card feature-card gradient-border'>
                        <div class='cf-card-top'><span class='feature-icon cf-icon cf-icon-{icon_class}'></span><span class='cf-number'>{number}</span></div>
                        <h3 class='feature-title'>{title}</h3>
                        <p class='feature-copy'>{desc}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    st.markdown("</div></section>", unsafe_allow_html=True)

    st.markdown("<section class='cf-features phase2-section' id='benefits'><div class='cf-section-inner cf-feature-grid feature-grid'>", unsafe_allow_html=True)
    feature_text, feature_cards = st.columns([1, 1.28], gap="large")
    with feature_text:
        st.markdown(
            """
            <div class='cf-label secondary'>Why CareerForge</div>
            <h2 class='feature-heading-title'>Built for the next generation of professionals</h2>
            <p class='feature-heading-copy'>Replace guesswork with measurable career intelligence. Trained on real industry data and tailored to your goals.</p>
            """,
            unsafe_allow_html=True,
        )
    with feature_cards:
        features = [
            ("AI Resume Parsing", "Extract skills, projects, and certificates with NLP.", "brain"),
            ("Hybrid Recommendation", "Pick AI's suggestion or set your own career.", "target"),
            ("Readiness Score", "Quantify exactly how job-ready you are today.", "chart"),
            ("Premium PDF Report", "Share-ready career portfolio in one click.", "award"),
        ]
        for row_start in range(0, len(features), 2):
            cols = st.columns(2, gap="medium")
            for col, (title, desc, icon_class) in zip(cols, features[row_start:row_start + 2]):
                with col:
                    st.markdown(
                        f"""
                        <div class='cf-feature-card ai-card'>
                            <span class='feature-icon cf-feature-icon cf-icon-{icon_class}'></span>
                            <h3 class='feature-title'>{title}</h3>
                            <p class='feature-copy'>{desc}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    st.markdown("</div></section>", unsafe_allow_html=True)

    st.markdown("<section class='cf-metrics'><div class='cf-section-inner'>", unsafe_allow_html=True)
    metrics = [
        ("50k+", "Resumes analyzed", "file"),
        ("120+", "Career paths mapped", "map"),
        ("94%", "Avg. recommendation accuracy", "spark"),
        ("4.9/5", "Student rating", "star"),
    ]
    metric_cols = st.columns(4, gap="medium")
    for col, (value, label, icon_class) in zip(metric_cols, metrics):
        with col:
            st.markdown(
                f"""
                <div class='cf-metric-tile'>
                    <span class='cf-metric-icon cf-icon-{icon_class}'></span>
                    <strong>{value}</strong>
                    <span>{label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("</div></section>", unsafe_allow_html=True)

    st.markdown(
        """
        <section class='cf-cta'>
            <div class='cf-section-inner'>
                <div class='cf-pill cf-cta-pill'>Trusted by students from 200+ campuses</div>
                <h2>Your career, planned by AI.</h2>
                <p>Start your free career readiness analysis today - your personalized roadmap is minutes away.</p>
        """,
        unsafe_allow_html=True,
    )
    cta_cols = st.columns([1.45, 0.82, 1.08, 1.45], gap="small")
    with cta_cols[1]:
        if st.button("Get Started Free ->", key="home_cta_get_started", type="primary", use_container_width=True):
            st.session_state.current_page = "Dashboard" if is_authenticated() else "Register"
            st.rerun()
    with cta_cols[2]:
        if st.button("View Sample Dashboard", key="home_cta_dashboard", type="secondary", use_container_width=True):
            st.session_state.current_page = "Dashboard" if is_authenticated() else "Register"
            st.rerun()
    st.markdown("</div></section></div>", unsafe_allow_html=True)


def dashboard_page():
    # Hero Banner - Matching Lovable Dashboard Design
    profile = get_profile_by_user_id(st.session_state.user_id)
    resume_data = get_resume_data_by_user(st.session_state.user_id)
    latest_prediction = get_latest_career_prediction(st.session_state.user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(st.session_state.user_id)
    latest_roadmap = get_latest_roadmap(st.session_state.user_id)
    
    completion = calculate_profile_completion(profile)
    ats_score = calculate_resume_ats_score(resume_data) if resume_data else 0.0
    skill_match = float(latest_skill_gap.get("skill_match_score") or 0.0) if latest_skill_gap else 0.0
    roadmap_score = float(latest_roadmap.get("readiness_score") or 0.0) if latest_roadmap else 0.0
    overall_readiness = compute_overall_readiness(completion, ats_score, skill_match, roadmap_score)
    
    selected_career = None
    if latest_prediction:
        selected_career = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
    
    points_away = 100 - int(overall_readiness)
    career_name = selected_career if selected_career else "your target role"
    
    matched_skills = len(normalize_comma_separated_list(latest_skill_gap.get('matched_skills'))) if latest_skill_gap else 0
    missing_skills = len(normalize_comma_separated_list(latest_skill_gap.get('missing_skills'))) if latest_skill_gap else 0
    extra_skills = len(normalize_comma_separated_list(latest_skill_gap.get('extra_skills'))) if latest_skill_gap else 0
    
    st.markdown(
        f"""
        <div class='dashboard-hero'>
            <div class='dashboard-hero-inner'>
                <div class='dashboard-hero-left'>
                    <div class='hero-pill'>
                        <span>✨</span>
                        <span>AI Insight · Updated today</span>
                    </div>
                    <h1 class='hero-heading'>You're {points_away} points away from being interview-ready for <span class='text-gradient'>{career_name}</span></h1>
                    <p class='hero-description'>Focus on the {missing_skills} missing high-impact skills this month to unlock a 90+ readiness score.</p>
                    <div class='hero-actions'>
                        <button class='hero-btn-primary' onclick="document.getElementById('view-skill-gaps').click()">
                            View skill gaps
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M5 12h14"></path>
                                <path d="m12 5 7 7-7 7"></path>
                            </svg>
                        </button>
                        <button class='hero-btn-secondary' onclick="document.getElementById('open-roadmap').click()">
                            Open roadmap
                        </button>
                    </div>
                </div>
                <div class='dashboard-hero-right'>
                    <div class='readiness-card'>
                        <div class='readiness-header'>READINESS</div>
                        <div class='readiness-score'>
                            <span class='score-number'>{int(overall_readiness)}</span>
                            <span class='score-divider'>/</span>
                            <span class='score-total'>100</span>
                        </div>
                        <div class='readiness-progress'>
                            <div class='readiness-progress-bar' style='width: {overall_readiness}%;'></div>
                        </div>
                        <div class='readiness-stats'>
                            <div class='stat-item'>
                                <span class='stat-value matched'>{matched_skills}</span>
                                <span class='stat-label'>Matched</span>
                            </div>
                            <div class='stat-item'>
                                <span class='stat-value missing'>{missing_skills}</span>
                                <span class='stat-label'>Missing</span>
                            </div>
                            <div class='stat-item'>
                                <span class='stat-value extra'>{extra_skills}</span>
                                <span class='stat-label'>Extra</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Hidden buttons for functionality
    with st.container():
        if st.button("View Skill Gaps", key="view-skill-gaps", type="primary", use_container_width=True):
            st.session_state.current_page = "Skill Gap Analysis"
            st.rerun()
        
        if st.button("Open Roadmap", key="open-roadmap", type="secondary", use_container_width=True):
            st.session_state.current_page = "Roadmap Generator"
            st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # KPI Cards Section - Matching Lovable Design
    resume_data = get_resume_data_by_user(st.session_state.user_id)
    latest_prediction = get_latest_career_prediction(st.session_state.user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(st.session_state.user_id)
    latest_roadmap = get_latest_roadmap(st.session_state.user_id)
    
    completion = calculate_profile_completion(profile)
    ats_score = calculate_resume_ats_score(resume_data) if resume_data else 0.0
    skill_match = float(latest_skill_gap.get("skill_match_score") or 0.0) if latest_skill_gap else 0.0
    roadmap_score = float(latest_roadmap.get("readiness_score") or 0.0) if latest_roadmap else 0.0
    overall_readiness = compute_overall_readiness(completion, ats_score, skill_match, roadmap_score)
    
    missing_count = len(normalize_comma_separated_list(latest_skill_gap.get('missing_skills'))) if latest_skill_gap else 0
    
    # KPI Cards Row 1 - 4 cards
    st.markdown("<div class='kpi-grid'>", unsafe_allow_html=True)
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>📋</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Profile Completion</div>
                    <div class='kpi-value'>{int(completion)}%</div>
                    <div class='kpi-trend positive'>↑ 12%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols[1]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>📄</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Resume Score</div>
                    <div class='kpi-value'>{int(ats_score)}</div>
                    <div class='kpi-trend positive'>↑ 8%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols[2]:
        career_match = skill_match if skill_match > 0 else 94.0
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>🎯</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Career Match</div>
                    <div class='kpi-value'>{int(career_match)}%</div>
                    <div class='kpi-trend positive'>↑ Top 5%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols[3]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>⚡</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Readiness Score</div>
                    <div class='kpi-value'>{int(overall_readiness)}</div>
                    <div class='kpi-trend positive'>↑ 5%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    
    # KPI Cards Row 2 - 4 cards
    st.markdown("<div class='kpi-grid'>", unsafe_allow_html=True)
    kpi_cols2 = st.columns(4)
    with kpi_cols2[0]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>📊</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Readiness Score</div>
                    <div class='kpi-value'>{int(overall_readiness)}</div>
                    <div class='kpi-progress'>
                        <div class='kpi-progress-bar' style='width: {overall_readiness}%;'></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols2[1]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>📚</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Missing Skills</div>
                    <div class='kpi-value'>{missing_count}</div>
                    <div class='kpi-trend negative'>↓ 2</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols2[2]:
        roadmap_months = latest_roadmap.get('duration_months', 6) if latest_roadmap else 6
        current_month = 2  # This would come from roadmap progress
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>🗺️</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Roadmap Progress</div>
                    <div class='kpi-value'>{int(roadmap_score)}%</div>
                    <div class='kpi-trend neutral'>M{current_month} of {roadmap_months}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi_cols2[3]:
        st.markdown(
            f"""
            <div class='kpi-card'>
                <div class='kpi-icon'>⭐</div>
                <div class='kpi-content'>
                    <div class='kpi-label'>Skill Match</div>
                    <div class='kpi-value'>{int(skill_match)}%</div>
                    <div class='kpi-trend positive'>Strong</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gauge Charts
    gauge_cols = st.columns(2)
    with gauge_cols[0]:
        render_gauge_card("Resume ATS Score", ats_score, suffix="%", color="#3960ff")
    with gauge_cols[1]:
        render_gauge_card("Overall Career Readiness", overall_readiness, suffix="%", color="#0b3d91")
    
    st.markdown("---")
    
    # Bottom Action Cards - Matching Lovable Design
    st.markdown(
        """
        <div class='action-cards-grid'>
            <a href='#' class='action-card'>
                <span class='action-card-icon'>📊</span>
                <span class='action-card-title'>Career Analysis</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='action-card'>
                <span class='action-card-icon'>🎯</span>
                <span class='action-card-title'>Skill Gap</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='action-card'>
                <span class='action-card-icon'>🗺️</span>
                <span class='action-card-title'>Roadmap</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='action-card'>
                <span class='action-card-icon'>📈</span>
                <span class='action-card-title'>Analytics</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("---")
    
    # Activity Panel - Matching Lovable Design
    st.markdown(
        """
        <div class='activity-panel'>
            <div class='activity-header'>
                <h3 class='activity-title'>Activity</h3>
                <p class='activity-subtitle'>Recent updates</p>
            </div>
            <div class='activity-list'>
        """,
        unsafe_allow_html=True,
    )
    
    # Activity items data
    activities = [
        {
            "icon": "✨",
            "title": "New AI recommendation",
            "description": "Data Scientist · 94%",
            "timestamp": "2h ago",
            "icon_bg": "rgba(87, 94, 207, 0.1)",
            "icon_color": "#575ecf"
        },
        {
            "icon": "📄",
            "title": "Resume re-analyzed",
            "description": "Score jumped to 76",
            "timestamp": "5h ago",
            "icon_bg": "rgba(6, 182, 212, 0.1)",
            "icon_color": "#06b6d4"
        },
        {
            "icon": "🏆",
            "title": "Milestone reached",
            "description": "Month 1 completed",
            "timestamp": "1d ago",
            "icon_bg": "rgba(16, 185, 129, 0.1)",
            "icon_color": "#10b981"
        },
        {
            "icon": "🔔",
            "title": "New course suggested",
            "description": "Statistics for ML",
            "timestamp": "2d ago",
            "icon_bg": "rgba(245, 158, 11, 0.1)",
            "icon_color": "#f59e0b"
        },
    ]
    
    for activity in activities:
        st.markdown(
            f"""
            <div class='activity-item'>
                <div class='activity-icon-wrapper' style='background: {activity["icon_bg"]}; color: {activity["icon_color"]};'>
                    {activity["icon"]}
                </div>
                <div class='activity-content'>
                    <div class='activity-title'>{activity["title"]}</div>
                    <div class='activity-description'>{activity["description"]}</div>
                </div>
                <div class='activity-timestamp'>{activity["timestamp"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    st.markdown(
        """
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("---")
    
    # Roadmap Section - Matching Lovable Design
    st.markdown(
        """
        <div class='roadmap-section'>
            <div class='roadmap-header'>
                <div>
                    <h3 class='roadmap-title'>Your 6-month roadmap</h3>
                    <p class='roadmap-subtitle'>Data Scientist track</p>
                </div>
                <a href='#' class='roadmap-view-all'>View all â†’</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Milestone cards data
    milestones = [
        {"month": "M1", "title": "Python & SQL Foundations", "status": "completed", "icon": "âœ“"},
        {"month": "M2", "title": "Statistics & EDA", "status": "in-progress", "progress": 60},
        {"month": "M3", "title": "ML with Scikit-Learn", "status": "upcoming"},
        {"month": "M4", "title": "Deep Learning Basics", "status": "upcoming"},
    ]
    
    for milestone in milestones:
        status_class = milestone.get('status', 'upcoming')
        progress_width = milestone.get('progress', 0)
        
        st.markdown(
            f"""
            <div class='milestone-card {status_class}'>
                <div class='milestone-left'>
                    <div class='milestone-badge'>{milestone['month']}</div>
                    <div class='milestone-content'>
                        <div class='milestone-title'>{milestone['title']}</div>
                        <div class='milestone-status'>
                            {f"<span class='status-text'>{milestone.get('status', 'upcoming').replace('-', ' ').title()}</span>" if status_class == 'upcoming' else f"<span class='status-text'>{milestone.get('status', 'in progress').title()}</span>"}
                            {f"<span class='progress-text'>· {progress_width}%</span>" if progress_width > 0 else ""}
                        </div>
                    </div>
                </div>
                <div class='milestone-right'>
                    {f"<div class='milestone-icon completed'><svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'></polyline></svg></div>" if status_class == 'completed' else ""}
                    {f"<div class='milestone-progress-ring'><svg width='24' height='24' viewBox='0 0 24 24'><circle cx='12' cy='12' r='10' fill='none' stroke='#e2e8f0' stroke-width='2'></circle><circle cx='12' cy='12' r='10' fill='none' stroke='#575ecf' stroke-width='2' stroke-dasharray='{progress_width} 100' transform='rotate(-90 12 12)'></circle></svg></div>" if status_class == 'in-progress' else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    # Quick action buttons
    st.markdown(
        """
        <div class='roadmap-actions'>
            <a href='#' class='roadmap-action-btn'>
                <span class='action-icon'>ðŸ“Š</span>
                <span>Career Analysis</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='roadmap-action-btn'>
                <span class='action-icon'>ðŸŽ¯</span>
                <span>Skill Gap</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='roadmap-action-btn'>
                <span class='action-icon'>ðŸ—ï¸</span>
                <span>Roadmap</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
            <a href='#' class='roadmap-action-btn'>
                <span class='action-icon'>ðŸ“ˆ</span>
                <span>Analytics</span>
                <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M5 12h14'></path><path d='m12 5 7 7-7 7'></path></svg>
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)

def cached_system_overview():
    return get_system_overview()


@st.cache_data(ttl=300)

def cached_latest_users(limit: int = 5):
    return get_latest_registered_users(limit)


@st.cache_data(ttl=300)

def cached_user_activity_scores(limit: int = 5):
    return get_user_activity_scores(limit)


@st.cache_data(ttl=300)

def cached_user_readiness_scores(limit: int = 5, highest: bool = True):
    return get_user_readiness_scores(limit, highest)


@st.cache_data(ttl=300)

def cached_career_summary():
    return get_career_recommendation_summary()


@st.cache_data(ttl=300)

def cached_most_selected_careers():
    return get_most_selected_careers()


@st.cache_data(ttl=300)

def cached_career_selection_counts():
    return get_career_selection_counts()


@st.cache_data(ttl=300)

def cached_career_override_statistics():
    return get_career_override_statistics()


@st.cache_data(ttl=300)

def cached_career_domains():
    return get_career_domain_distribution()


@st.cache_data(ttl=300)

def cached_skill_summary():
    return get_skill_gap_summary()


@st.cache_data(ttl=300)

def cached_resume_analytics():
    return get_resume_analytics()


@st.cache_data(ttl=300)

def cached_roadmap_analytics():
    return get_roadmap_analytics()


@st.cache_data(ttl=300)

def cached_database_health():
    return get_database_health()


@st.cache_data(ttl=300)

def cached_search_users(name: str = None, email: str = None, career_role: str = None):
    return search_users(name, email, career_role)


def admin_dashboard_page():
    if not is_authenticated():
        st.warning("Please log in to access the Admin Dashboard.")
        return
    if not is_admin():
        st.error("Admin access required. Please log in with an administrator account.")
        return

    render_section_header(
        "Admin Dashboard",
        "SaaS Analytics Control Panel for platform adoption, career trends, skill health, and database stability.",
        icon="ðŸ›¡ï¸",
    )

    overview = cached_system_overview()
    metrics = st.columns(6)
    metric_labels = [
        ("Total Users", "ðŸ‘¥"),
        ("Total Profiles", "ðŸ§¾"),
        ("Total Resumes", "ðŸ“„"),
        ("Career Predictions", "ðŸŽ¯"),
        ("Skill Gap Analyses", "âš¡"),
        ("Total Roadmaps", "ðŸ—ºï¸"),
    ]
    values = [
        overview.get("total_users", 0),
        overview.get("total_profiles", 0),
        overview.get("total_resumes", 0),
        overview.get("total_career_predictions", 0),
        overview.get("total_skill_gap_analyses", 0),
        overview.get("total_roadmaps", 0),
    ]
    for col, (label, icon), value in zip(metrics, metric_labels, values):
        with col:
            render_metric_card(label, str(value), icon=icon)

    st.markdown("---")
    st.subheader("Career Analytics")
    career_summary = cached_career_summary()
    career_domains = cached_career_domains()
    if career_summary:
        career_df = pd.DataFrame(career_summary)
        career_df.columns = ["Career Role", "Count"]
        fig_career = px.bar(
            career_df,
            x="Count",
            y="Career Role",
            orientation="h",
            text="Count",
            color="Career Role",
            title="Most Recommended Careers",
            template="plotly_white",
        )
        fig_career.update_layout(showlegend=False, margin=dict(t=45, r=20, l=20, b=20))
        st.plotly_chart(fig_career, use_container_width=True)
    else:
        st.info("No career recommendations available yet.")

    if career_domains:
        domain_df = pd.DataFrame(list(career_domains.items()), columns=["Domain", "Count"])
        fig_domain = px.pie(
            domain_df,
            names="Domain",
            values="Count",
            title="Career Domain Distribution",
            hole=0.42,
            template="plotly_white",
        )
        st.plotly_chart(fig_domain, use_container_width=True)

    st.markdown("---")
    st.subheader("Career Selection Analytics")
    career_selection_counts = cached_career_selection_counts()
    selection_cols = st.columns(4)
    selection_cols[0].metric("AI Recommendations", career_selection_counts.get("total_ai_recommendations", 0))
    selection_cols[1].metric("User Overrides", career_selection_counts.get("total_user_overrides", 0))
    selected_careers = cached_most_selected_careers()
    selection_cols[2].metric("Top User Selected Career", selected_careers[0]["career_role"] if selected_careers else "N/A")
    selection_cols[3].metric("Top Selected Count", selected_careers[0]["count"] if selected_careers else 0)

    override_stats = cached_career_override_statistics()
    if override_stats:
        st.markdown("**Most Overridden Careers**")
        override_df = pd.DataFrame(override_stats)
        override_df.columns = ["Career Role", "Override Count"]
        st.table(override_df)
    else:
        st.info("No user override records are available yet.")

    st.markdown("---")
    st.subheader("Skill Analytics")
    skill_summary = cached_skill_summary()
    skill_row = st.columns(4)
    skill_row[0].metric("Avg Skill Match", f"{skill_summary.get('average_skill_match_score', 0.0):.1f}%")
    skill_row[1].metric("Avg Readiness", f"{skill_summary.get('average_readiness_score', 0.0):.1f}%")
    skill_row[2].metric("Most Missing Skills", len(skill_summary.get("most_missing_skills", [])))
    skill_row[3].metric("Most Common Skills", len(skill_summary.get("most_common_skills", [])))

    missing_skills = skill_summary.get("most_missing_skills", [])
    if missing_skills:
        df_missing = pd.DataFrame(missing_skills, columns=["Skill", "Count"])
        fig_missing = px.bar(
            df_missing,
            x="Count",
            y="Skill",
            orientation="h",
            title="Most Missing Skills",
            template="plotly_white",
        )
        st.plotly_chart(fig_missing, use_container_width=True)

    matched_skills = skill_summary.get("most_common_skills", [])
    if matched_skills:
        df_matched = pd.DataFrame(matched_skills, columns=["Skill", "Count"])
        fig_matched = px.pie(
            df_matched,
            names="Skill",
            values="Count",
            title="Most Common Matched Skills",
            hole=0.4,
            template="plotly_white",
        )
        st.plotly_chart(fig_matched, use_container_width=True)

    st.markdown("---")
    st.subheader("Resume Analytics")
    resume_analytics = cached_resume_analytics()
    resume_row = st.columns(3)
    resume_row[0].metric("Avg ATS Score", f"{resume_analytics.get('average_ats_score', 0.0):.1f}%")
    resume_row[1].metric("Total Resumes", resume_analytics.get("total_resumes", 0))
    resume_row[2].metric("Distinct Top Skills", len(resume_analytics.get("most_common_skills", [])))

    skills = resume_analytics.get("most_common_skills", [])
    if skills:
        df_resume_skills = pd.DataFrame(skills, columns=["Skill", "Count"])
        fig_resume = px.bar(
            df_resume_skills,
            x="Count",
            y="Skill",
            orientation="h",
            title="Most Common Resume Skills",
            template="plotly_white",
        )
        st.plotly_chart(fig_resume, use_container_width=True)

    st.markdown("---")
    st.subheader("Roadmap Analytics")
    roadmap_analytics = cached_roadmap_analytics()
    roadmap_cols = st.columns(2)
    roadmap_cols[0].metric("Avg Roadmap Duration", f"{roadmap_analytics.get('average_roadmap_duration', 0.0):.1f} months")
    roadmap_cols[1].metric("Top Generated Paths", len(roadmap_analytics.get("most_generated_roadmaps", [])))

    generated = roadmap_analytics.get("most_generated_roadmaps", [])
    if generated:
        df_roadmap = pd.DataFrame(generated, columns=["Career Role", "Count"])
        fig_roadmap = px.bar(
            df_roadmap,
            x="Count",
            y="Career Role",
            orientation="h",
            title="Top Generated Career Roadmaps",
            template="plotly_white",
        )
        st.plotly_chart(fig_roadmap, use_container_width=True)

    st.markdown("---")
    st.subheader("Database Health")
    db_health = cached_database_health()
    health_cols = st.columns(3)
    health_cols[0].metric("Connected", str(db_health.get("connected")))
    health_cols[1].metric("Total Tables", len(db_health.get("tables_found", [])))
    health_cols[2].metric("Total Records", sum(db_health.get("total_records", {}).values()))
    st.write(db_health.get("total_records", {}))

    st.markdown("---")
    st.subheader("User Search")
    with st.form(key="admin_search_form"):
        search_name = st.text_input("Name")
        search_email = st.text_input("Email")
        search_career = st.text_input("Career Role")
        search_submit = st.form_submit_button("Search")

    if search_submit:
        results = cached_search_users(search_name, search_email, search_career)
        if results:
            st.success(f"Found {len(results)} matching user records.")
            st.dataframe(results)
            df = pd.DataFrame(results)
            st.download_button(
                label="Download CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="admin_user_search.csv",
                mime="text/csv",
            )
        else:
            st.info("No users matched the search criteria.")


def login_page():
    st.title("Login")
    st.write("Access your career readiness dashboard by signing in.")

    with st.form(key="login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")

    if submitted:
        if not email or not password:
            st.error("Please enter both email and password.")
            return

        user = get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            st.error("Invalid credentials. Please check your email and password.")
            return

        login_user(user)
        st.success("Login successful. Redirecting to dashboard...")
        st.rerun()


def register_page():
    st.title("Register")
    st.write("Create an account to start tracking your career readiness.")

    with st.form(key="registration_form"):
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account")

    if submitted:
        errors = validate_registration(full_name, email, password, confirm_password)
        if errors:
            for error in errors:
                st.error(error)
            return

        if get_user_by_email(email):
            st.error("That email is already registered. Please log in or use a different email.")
            return

        password_hash = hash_password(password)
        try:
            create_user(full_name, email, password_hash)
            st.success("Registration successful. You can now log in.")
        except Exception as error:
            st.error(f"An error occurred while creating your account: {error}")


def profile_page():
    if not is_authenticated():
        st.warning("Please log in to access your profile.")
        return

    existing_profile = get_profile_by_user_id(st.session_state.user_id)
    completion = calculate_profile_completion(existing_profile)
    user = get_user_by_id(st.session_state.user_id) or {}
    display_name = user.get("name") or st.session_state.user_name or "Student"
    display_email = user.get("email") or "Not available"
    initials = "".join([part[0] for part in display_name.split()[:2]]).upper() or "U"

    if completion >= 80:
        strength_label = "Strong"
        strength_class = "strong"
    elif completion >= 60:
        strength_label = "Good"
        strength_class = "good"
    elif completion >= 40:
        strength_label = "Fair"
        strength_class = "fair"
    else:
        strength_label = "Needs Work"
        strength_class = "needs-work"

    cgpa_display = float(existing_profile.get("cgpa", 0.0) if existing_profile else 0.0)
    communication_display = int(existing_profile.get("communication", 5) if existing_profile else 5)
    logical_display = int(existing_profile.get("logical_reasoning", 5) if existing_profile else 5)
    projects_display = int(existing_profile.get("projects_count", 0) if existing_profile else 0)
    certifications_display = int(existing_profile.get("certifications_count", 0) if existing_profile else 0)
    internship_display = int(existing_profile.get("internship_count", 0) if existing_profile else 0)
    interest_display = existing_profile.get("interest_domain") if existing_profile else ""
    interest_text = interest_display if interest_display else "Select interest domain"
    profile_status = "AI-Verified Profile" if existing_profile else "Profile Pending"

    st.markdown(
        """
        <div class='profile-page-shell'>
            <div class='profile-topbar'>
                <div>
                    <h1>Profile</h1>
                    <p>Manage your academic and professional identity</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page_cols = st.columns([0.95, 2.05], gap="medium")

    with page_cols[0]:
        with st.container():
            st.markdown(
                f"""
                <section class='profile-identity-card'>
                    <div class='profile-avatar'>{initials[:2]}</div>
                    <h2>{display_name}</h2>
                    <p>{interest_text}</p>
                    <span class='profile-verified profile-verified-{strength_class}'>✓ {profile_status}</span>
                    <div class='profile-contact-list'>
                        <div><span>✉</span><strong>{display_email}</strong></div>
                        <div><span>◎</span><strong>{st.session_state.get('user_role', 'user').title()}</strong></div>
                        <div><span>⌁</span><strong>{interest_text}</strong></div>
                    </div>
                </section>
                """,
                unsafe_allow_html=True,
            )

        with st.container():
            st.markdown(
                f"""
                <section class='profile-strength-card'>
                    <div class='profile-card-heading'>
                        <h3>Profile Strength</h3>
                        <span class='profile-strength-label profile-strength-{strength_class}'>{strength_label}</span>
                    </div>
                    <div class='profile-score'>{completion}<span>%</span></div>
                    <div class='profile-progress-track'>
                        <div class='profile-progress-fill' style='width: {completion}%;'></div>
                    </div>
                    <ul class='profile-check-list'>
                        <li class='{'' if cgpa_display <= 0 else 'is-complete'}'>Personal info</li>
                        <li class='{'' if cgpa_display <= 0 else 'is-complete'}'>Academic details</li>
                        <li class='{'' if not interest_display else 'is-complete'}'>Career interest</li>
                        <li class='{'' if projects_display < 1 else 'is-complete'}'>Projects ({projects_display}/5)</li>
                        <li class='{'' if certifications_display < 1 else 'is-complete'}'>Certifications</li>
                    </ul>
                </section>
                """,
                unsafe_allow_html=True,
            )

    with page_cols[1]:
        st.markdown("<section class='profile-form-card'>", unsafe_allow_html=True)
        with st.form(key="profile_form"):
            st.markdown(
                """
                <div class='profile-card-heading profile-form-heading'>
                    <h3>Profile Information</h3>
                    <span>Edit</span>
                </div>
                <div class='profile-section-kicker'>Academic Overview</div>
                """,
                unsafe_allow_html=True,
            )

            academic_cols = st.columns(2, gap="medium")
            with academic_cols[0]:
                cgpa = st.number_input(
                    "CGPA",
                    min_value=0.0,
                    max_value=10.0,
                    value=float(existing_profile.get("cgpa", 0.0) if existing_profile else 0.0),
                    step=0.1,
                    help="Your cumulative GPA (0-10 scale)"
                )
                communication = st.slider(
                    "Communication Skills",
                    1,
                    10,
                    int(existing_profile.get("communication", 5) if existing_profile else 5),
                    help="Rate your communication skills (1-10)"
                )
                projects_count = st.number_input(
                    "Projects Completed",
                    min_value=0,
                    max_value=50,
                    value=int(existing_profile.get("projects_count", 0) if existing_profile else 0),
                    help="Number of projects you've completed"
                )
            with academic_cols[1]:
                logical_reasoning = st.slider(
                    "Logical Reasoning",
                    1,
                    10,
                    int(existing_profile.get("logical_reasoning", 5) if existing_profile else 5),
                    help="Rate your logical reasoning ability (1-10)"
                )
                certifications_count = st.number_input(
                    "Certifications Earned",
                    min_value=0,
                    max_value=50,
                    value=int(existing_profile.get("certifications_count", 0) if existing_profile else 0),
                    help="Number of professional certifications"
                )
                internship_count = st.number_input(
                    "Internships Completed",
                    min_value=0,
                    max_value=10,
                    value=int(existing_profile.get("internship_count", 0) if existing_profile else 0),
                    help="Number of internships completed"
                )

            interest_options = [
                "",
                "Data Science",
                "Artificial Intelligence",
                "Machine Learning",
                "Software Development",
                "Web Development",
                "Cloud Computing",
                "Cyber Security",
                "DevOps",
                "Business Analytics",
            ]

            default_interest_index = 0
            if existing_profile and existing_profile.get("interest_domain") in interest_options:
                default_interest_index = interest_options.index(existing_profile.get("interest_domain"))

            st.markdown("<div class='profile-section-kicker'>Interest Domains</div>", unsafe_allow_html=True)
            interest_domain = st.selectbox(
                "Primary Interest Domain",
                interest_options,
                index=default_interest_index,
                help="Select your primary area of interest"
            )

            submitted = st.form_submit_button("💾 Save Profile", type="primary", use_container_width=True)
        st.markdown("</section>", unsafe_allow_html=True)

    if submitted:
        try:
            if existing_profile:
                update_profile(
                    st.session_state.user_id,
                    cgpa,
                    communication,
                    logical_reasoning,
                    projects_count,
                    certifications_count,
                    internship_count,
                    interest_domain,
                )
                st.success("✅ Profile updated successfully!")
            else:
                create_profile(
                    st.session_state.user_id,
                    cgpa,
                    communication,
                    logical_reasoning,
                    projects_count,
                    certifications_count,
                    internship_count,
                    interest_domain,
                )
                st.success("✅ Profile created successfully!")
            st.rerun()
        except Exception as error:
            st.error(f"❌ Unable to save profile information: {error}")

    if existing_profile:
        st.markdown("<div class='profile-summary-grid'>", unsafe_allow_html=True)
        summary_cols = st.columns(3, gap="medium")
        with summary_cols[0]:
            st.markdown(
                f"""
                <section class='profile-info-card'>
                    <div class='profile-card-heading'><h3>Academic Overview</h3><span>Edit</span></div>
                    <div class='profile-info-grid'>
                        <div><small>CGPA</small><strong>{cgpa_display:.2f} / 10</strong></div>
                        <div><small>Communication</small><strong>{communication_display} / 10</strong></div>
                        <div><small>Logical Reasoning</small><strong>{logical_display} / 10</strong></div>
                    </div>
                </section>
                """,
                unsafe_allow_html=True,
            )
        with summary_cols[1]:
            st.markdown(
                f"""
                <section class='profile-info-card'>
                    <div class='profile-card-heading'><h3>Skill Overview</h3><span>Edit</span></div>
                    <div class='profile-pill-row'>
                        <span>Communication</span>
                        <span>Logical Reasoning</span>
                        <span>{interest_text}</span>
                    </div>
                    <button class='profile-add-chip' type='button'>+ Add skill</button>
                </section>
                """,
                unsafe_allow_html=True,
            )
        with summary_cols[2]:
            st.markdown(
                f"""
                <section class='profile-info-card'>
                    <div class='profile-card-heading'><h3>Experience</h3><span>Edit</span></div>
                    <div class='profile-info-grid'>
                        <div><small>Projects</small><strong>{projects_display}</strong></div>
                        <div><small>Internships</small><strong>{internship_display}</strong></div>
                        <div><small>Certifications</small><strong>{certifications_display}</strong></div>
                    </div>
                </section>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        next_steps = []
        if completion < 100:
            if not existing_profile.get('interest_domain'):
                next_steps.append("Select your primary interest domain")
            if existing_profile.get('projects_count', 0) < 3:
                next_steps.append("Add more projects to your profile")
            if existing_profile.get('internship_count', 0) < 1:
                next_steps.append("Add internship experience if available")
            if existing_profile.get('certifications_count', 0) < 2:
                next_steps.append("Consider adding professional certifications")

        if next_steps:
            st.markdown("<section class='profile-info-card profile-next-card'><div class='profile-card-heading'><h3>Recommended Next Steps</h3><span>Plan</span></div>", unsafe_allow_html=True)
            for idx, step in enumerate(next_steps, 1):
                st.markdown(f"<div class='profile-next-step'><span>{idx}</span>{step}</div>", unsafe_allow_html=True)
            st.markdown("</section>", unsafe_allow_html=True)
        else:
            st.success("🎉 Your profile is complete! Proceed to upload your resume or generate career recommendations.")
def resume_upload_page():
    if not is_authenticated():
        st.warning("Please log in to access the Resume Upload page.")
        login_page()
        return

    render_section_header(
        "Resume Intelligence Center",
        "Upload your resume and let AI analyze your career readiness.",
        icon="ðŸ“„"
    )

    ensure_resume_upload_dir()
    resume_data = get_resume_data_by_user(st.session_state.user_id)
    parsed_data = None

    upload_cols = st.columns([2, 1])

    with upload_cols[0]:
        st.markdown(
            """
            <div class='resume-card'>
                <div class='resume-header-card'>
                    <span class='eyebrow'>Resume Center</span>
                    <h1>Resume Intelligence Center</h1>
                    <p>Upload your resume and let AI analyze your career readiness.</p>
                </div>
                <div class='upload-zone'>
                    <div class='upload-zone-inner'>
                        <div class='upload-icon'>ðŸ“„</div>
                        <h3>Drop your resume here</h3>
                        <p>PDF resumes are accepted. Maximum size: 5 MB.</p>
                        <span class='upload-note'>We’ll extract skills, education, experience, and certifications.</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload Resume",
            type=["pdf"],
            help="Maximum file size: 5 MB",
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            uploaded_file.seek(0, 2)
            file_size = uploaded_file.tell()
            uploaded_file.seek(0)

            if uploaded_file.type != "application/pdf":
                st.error("âŒ Only PDF files are allowed.")
                return
            if file_size > MAX_RESUME_SIZE_BYTES:
                st.error(
                    f"âŒ The uploaded resume exceeds the maximum allowed size of 5 MB. Your file: {file_size / (1024*1024):.2f} MB"
                )
                return
            if uploaded_file.name.split(".")[-1].lower() not in ALLOWED_RESUME_EXTENSIONS:
                st.error("âŒ Invalid file extension. Only .pdf resumes are accepted.")
                return

            st.markdown(
                f"""
                <div class='status-card'>
                    <div class='status-content'>
                        <div>
                            <p class='status-label'>Uploaded file</p>
                            <h4>{uploaded_file.name}</h4>
                            <p>{file_size / (1024*1024):.2f} MB</p>
                        </div>
                        <span class='success-badge'>Ready to analyze</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            action_cols = st.columns([1, 1])
            analyze_pressed = action_cols[0].button("Analyze Resume", type="primary", use_container_width=True)
            if resume_data:
                update_pressed = action_cols[1].button("Update Resume", type="secondary", use_container_width=True)
            else:
                update_pressed = False

            if analyze_pressed or update_pressed:
                try:
                    with st.spinner("ðŸ”„ Parsing your resume... This may take a moment."):
                        saved_path = save_uploaded_resume(uploaded_file)
                        parsed_data = parse_resume(saved_path)

                    skills_text = ", ".join(parsed_data.get("skills", []))
                    projects_text = ", ".join(parsed_data.get("projects", []))
                    certifications_text = ", ".join(parsed_data.get("certifications", []))
                    education_text = ", ".join(parsed_data.get("education", []))

                    if resume_data:
                        update_resume_data(
                            st.session_state.user_id,
                            saved_path,
                            skills_text,
                            projects_text,
                            certifications_text,
                            education_text,
                        )
                        st.success("âœ… Resume updated and parsed successfully!")
                    else:
                        create_resume_data(
                            st.session_state.user_id,
                            saved_path,
                            skills_text,
                            projects_text,
                            certifications_text,
                            education_text,
                        )
                        st.success("âœ… Resume uploaded and parsed successfully!")

                    resume_data = get_resume_data_by_user(st.session_state.user_id)
                except Exception as error:
                    st.error(f"âŒ Unable to parse resume: {error}")

    with upload_cols[1]:
        st.markdown(
            """
            <div class='resume-card resume-summary-card'>
                <div class='resume-summary-header'>
                    <span class='eyebrow'>Upload Status</span>
                    <h3>Resume status</h3>
                </div>
            """,
            unsafe_allow_html=True,
        )

        if resume_data:
            upload_date = resume_data.get('upload_date', 'N/A')
            file_name = resume_data.get('resume_file', 'Resume.pdf')
            st.markdown(
                f"""
                <div class='status-card'>
                    <div class='status-content'>
                        <div>
                            <p class='status-label'>Current file</p>
                            <h4>{file_name}</h4>
                            <p>Uploaded: {upload_date}</p>
                        </div>
                        <span class='success-badge'>Saved</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <div class='status-meta'>
                    <div>
                        <span class='meta-label'>Resume Parsed</span>
                        <p>Yes</p>
                    </div>
                    <div>
                        <span class='meta-label'>Insights Ready</span>
                        <p>Live</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class='status-card'>
                    <div class='status-content'>
                        <div>
                            <p class='status-label'>No resume uploaded yet</p>
                            <h4>Start with a resume upload</h4>
                            <p>Drop a PDF to see extracted skills, education, experience, and certifications.</p>
                        </div>
                        <span class='success-badge'>Waiting</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    if resume_data or parsed_data:
        current_data = {}
        if parsed_data:
            current_data = parsed_data
        elif resume_data:
            current_data = {
                'skills': resume_data.get('skills', '').split(', ') if resume_data.get('skills') else [],
                'certifications': resume_data.get('certifications', '').split(', ') if resume_data.get('certifications') else [],
                'education': resume_data.get('education', '').split(', ') if resume_data.get('education') else [],
                'projects': resume_data.get('projects', '').split(', ') if resume_data.get('projects') else [],
            }

        completeness = calculate_resume_completeness(
            current_data.get('skills', []),
            current_data.get('projects', []),
            current_data.get('certifications', []),
            current_data.get('education', []),
        )

        preview_cols = st.columns([3, 1])
        with preview_cols[0]:
            st.markdown("<div class='analysis-grid'>", unsafe_allow_html=True)

            st.markdown(
                f"""
                <div class='skill-card'>
                    <div class='skill-card-header'>
                        <h4>Extracted Skills</h4>
                        <span class='badge badge-primary'>Skills</span>
                    </div>
                    <div class='skill-card-body'>
                        {''.join([f"<span class='badge badge-info'>{skill.strip()}</span>" for skill in current_data.get('skills', [])[:12] if skill.strip()])}
                        {f'<p class="small-text">+{len(current_data.get("skills", [])) - 12} more</p>' if len(current_data.get('skills', [])) > 12 else ''}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class='skill-card'>
                    <div class='skill-card-header'>
                        <h4>Education</h4>
                        <span class='badge badge-purple'>Education</span>
                    </div>
                    <div class='skill-card-body'>
                        {''.join([f'<p>• {edu.strip()}</p>' for edu in current_data.get('education', [])[:3] if edu.strip()])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class='skill-card'>
                    <div class='skill-card-header'>
                        <h4>Experience</h4>
                        <span class='badge badge-info'>Experience</span>
                    </div>
                    <div class='skill-card-body'>
                        {''.join([f'<p>• {project.strip()}</p>' for project in current_data.get('projects', [])[:3] if project.strip()])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div class='skill-card'>
                    <div class='skill-card-header'>
                        <h4>Certifications</h4>
                        <span class='badge badge-success'>Certifications</span>
                    </div>
                    <div class='skill-card-body'>
                        {''.join([f'<p>• {cert.strip()}</p>' for cert in current_data.get('certifications', [])[:5] if cert.strip()])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("</div>", unsafe_allow_html=True)

        with preview_cols[1]:
            st.markdown(
                f"""
                <div class='score-card'>
                    <div class='score-card-header'>
                        <div>
                            <p class='score-label'>Resume Completeness</p>
                            <h2>{completeness}%</h2>
                        </div>
                        <span class='score-badge'>{'Ready' if completeness >= 80 else 'Improving' if completeness >= 60 else 'Needs Work'}</span>
                    </div>
                    <div class='score-progress'>
                        <div class='score-progress-bar' style='width: {completeness}%;'></div>
                    </div>
                    <p class='score-note'>A modern readiness indicator based on extracted resume contents.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if completeness >= 80:
                st.success("Excellent resume! Your analysis is in a strong position.")
            elif completeness >= 60:
                st.info("Good resume. Add a few more details for a stronger score.")
            else:
                st.warning("Your resume could benefit from more information and detail.")


def career_recommendation_page():
    if not is_authenticated():
        st.warning("Please log in to access Career Recommendation.")
        login_page()
        return

    create_career_predictions_table_if_missing()
    profile = get_profile_by_user_id(st.session_state.user_id)
    resume_data_db = get_resume_data_by_user(st.session_state.user_id)
    latest_prediction = get_latest_career_prediction(st.session_state.user_id)

    if latest_prediction and st.session_state.predicted_role is None:
        st.session_state.predicted_role = latest_prediction.get("predicted_role") or latest_prediction.get("recommended_role")
        st.session_state.prediction_confidence = float(latest_prediction.get("prediction_confidence") or latest_prediction.get("confidence_score") or 0.0)
        st.session_state.selected_role = latest_prediction.get("selected_role") or st.session_state.predicted_role
        st.session_state.final_selected_role = st.session_state.selected_role
        st.session_state.career_selection_type = (
            "AI Recommended"
            if st.session_state.selected_role == st.session_state.predicted_role
            else "User Selected"
        )

    if not profile:
        st.error("Profile data is required to generate a recommendation.")
        return

    if not resume_data_db:
        st.error("Resume data is required to generate a recommendation.")
        return

    profile_features = build_profile_features(profile)
    resume_features = build_resume_features(resume_data_db)

    render_section_header(
        "AI Career Recommendation",
        "Get personalized career suggestions powered by machine learning",
        icon="ðŸŽ¯"
    )
    
    # Career Options
    career_options = [
        "Data Analyst",
        "Data Scientist",
        "Machine Learning Engineer",
        "Software Developer",
        "Cloud Engineer",
        "DevOps Engineer",
        "Business Analyst",
        "Cyber Security Analyst",
        "Full Stack Developer",
        "AI Engineer",
    ]

    # Generate Button
    st.markdown(
        """
        <div class='card-box' style='text-align: center; margin-bottom: 2rem;'>
            <div style='font-size: 3rem; margin-bottom: 1rem;'>ðŸ¤–</div>
            <h3>Ready to Discover Your Ideal Career?</h3>
            <p style='color: var(--text-secondary); margin-bottom: 1.5rem;'>
                Our AI will analyze your profile and resume to recommend the best career paths
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    if st.button("ðŸš€ Generate AI Recommendations", type="primary", use_container_width=True):
        try:
            with st.spinner("ðŸ”„ Analyzing your profile and generating recommendations..."):
                recommendations = predict_career(profile_features, resume_features)

            if not recommendations:
                st.warning("No recommendation results available.")
                return

            st.markdown("---")
            render_section_header(
                "Top Career Recommendations",
                "Ranked by match confidence",
                icon="â­"
            )
            
            # Display recommendations in beautiful cards
            for idx, rec in enumerate(recommendations[:5], 1):
                confidence = rec['confidence']
                career = rec['career']
                
                # Determine badge color based on confidence
                if confidence >= 80:
                    badge_class = "badge-success"
                    badge_text = "Excellent Match"
                elif confidence >= 60:
                    badge_class = "badge-info"
                    badge_text = "Good Match"
                else:
                    badge_class = "badge-warning"
                    badge_text = "Potential Match"
                
                st.markdown(
                    f"""
                    <div class='glass-card' style='margin-bottom: 1rem;'>
                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;'>
                            <h3 style='margin: 0;'>#{idx} {career}</h3>
                            <span class='badge {badge_class}'>{badge_text}</span>
                        </div>
                        <div style='margin-bottom: 1rem;'>
                            <div class='stProgress' style='height: 12px;'>
                                <div style='height: 100%; width: {confidence}%; background: linear-gradient(90deg, #1256d4, #7c3aed); border-radius: 9999px;'></div>
                            </div>
                        </div>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <span style='font-size: 1.5rem; font-weight: 700; color: var(--primary-blue);'>{confidence:.1f}%</span>
                            <span style='color: var(--text-secondary);'>Match Confidence</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Save top recommendation
            top_career = recommendations[0]
            save_career_prediction(
                st.session_state.user_id,
                top_career["career"],
                round(top_career["confidence"], 2),
                top_career["career"],
            )

            st.session_state.predicted_role = top_career["career"]
            st.session_state.prediction_confidence = round(top_career["confidence"], 2)
            st.session_state.selected_role = top_career["career"]
            st.session_state.final_selected_role = top_career["career"]
            st.session_state.career_selection_type = "AI Recommended"

            latest_prediction = get_latest_career_prediction(st.session_state.user_id)
            if latest_prediction:
                st.markdown("---")
                st.subheader("Latest Stored Recommendation")
                st.write(latest_prediction)
        except FileNotFoundError as missing_error:
            st.error(str(missing_error))
        except Exception as error:
            st.error(f"Error generating recommendation: {error}")

    if st.session_state.predicted_role:
        st.markdown("---")
        render_section_header(
            "AI Recommended Career",
            "Based on your profile and resume analysis",
            icon="âœ¨"
        )
        
        reason = _build_recommendation_reason(
            st.session_state.predicted_role,
            resume_data_db.get("skills", "").split(", ") if resume_data_db.get("skills") else [],
        )
        
        # Enhanced recommendation card
        confidence = float(st.session_state.prediction_confidence or 0.0)
        badge_label = "AI Recommended" if st.session_state.career_selection_type == "AI Recommended" else "User Selected"
        
        st.markdown(
            f"""
            <div class='card-box' style='border-left: 4px solid var(--primary-blue);'>
                <div style='display: flex; justify-content: space-between; align-items: start; margin-bottom: 1.5rem;'>
                    <div>
                        <h2 style='margin: 0 0 0.5rem 0; color: var(--primary-blue);'>{st.session_state.predicted_role}</h2>
                        <span class='badge badge-primary'>{badge_label}</span>
                    </div>
                    <div style='text-align: right;'>
                        <div style='font-size: 2.5rem; font-weight: 800; color: var(--primary-blue);'>{confidence:.1f}%</div>
                        <div style='color: var(--text-secondary); font-size: 0.9rem;'>Confidence</div>
                    </div>
                </div>
                <div style='margin-bottom: 1rem;'>
                    <div class='stProgress' style='height: 8px;'>
                        <div style='height: 100%; width: {confidence}%; background: linear-gradient(90deg, #1256d4, #7c3aed); border-radius: 9999px;'></div>
                    </div>
                </div>
                <div style='background: rgba(59, 130, 246, 0.05); padding: 1rem; border-radius: var(--radius-lg);'>
                    <strong>ðŸ’¡ AI Reasoning:</strong> {reason}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        render_section_header(
            "Final Career Selection",
            "Choose whether to use the AI recommendation or select your own career goal",
            icon="ðŸŽ¯"
        )
        
        selection_cols = st.columns([1, 2])
        with selection_cols[0]:
            st.markdown(
                """
                <div class='info-card' style='text-align: center;'>
                    <div style='font-size: 2rem; margin-bottom: 0.5rem;'>ðŸ¤–</div>
                    <h4>Use AI Recommendation</h4>
                    <p style='font-size: 0.9rem;'>Accept the AI-suggested career path</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("âœ“ Use AI Recommendation", type="primary", use_container_width=True):
                st.session_state.selected_role = st.session_state.predicted_role
                st.session_state.final_selected_role = st.session_state.predicted_role
                st.session_state.career_selection_type = "AI Recommended"
                update_latest_career_prediction(st.session_state.user_id, st.session_state.predicted_role)
                st.success("âœ… AI recommended career confirmed as final selection!")
                st.rerun()

        with selection_cols[1]:
            st.markdown(
                """
                <div class='info-card' style='text-align: center;'>
                    <div style='font-size: 2rem; margin-bottom: 0.5rem;'>ðŸŽ¯</div>
                    <h4>Choose Your Own Career</h4>
                    <p style='font-size: 0.9rem;'>Select a different career goal</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            selected_career = st.selectbox(
                "Select Career Goal",
                career_options,
                index=career_options.index(st.session_state.selected_role) if st.session_state.selected_role in career_options else 0,
                label_visibility="collapsed"
            )
            if st.button("âœ“ Select This Career", type="secondary", use_container_width=True):
                st.session_state.selected_role = selected_career
                st.session_state.final_selected_role = selected_career
                st.session_state.career_selection_type = "User Selected"
                update_latest_career_prediction(st.session_state.user_id, selected_career)
                st.success(f"âœ… Final career path set to {selected_career}!")
                st.rerun()

        if st.session_state.final_selected_role:
            st.markdown("---")
            st.markdown(
                f"""
                <div class='card-box' style='text-align: center; background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));'>
                    <h3 style='margin-bottom: 0.5rem;'>ðŸŽ¯ Your Final Career Path</h3>
                    <h2 style='color: var(--primary-blue); margin-bottom: 0.5rem;'>{st.session_state.final_selected_role}</h2>
                    <span class='badge badge-info'>{st.session_state.career_selection_type}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def skill_gap_analysis_page():
    if not is_authenticated():
        st.warning("Please log in to access Skill Gap Analysis.")
        login_page()
        return

    create_skill_gap_table_if_missing()
    profile = get_profile_by_user_id(st.session_state.user_id)
    resume_data_db = get_resume_data_by_user(st.session_state.user_id)
    latest_prediction = get_latest_career_prediction(st.session_state.user_id)
    previous_analysis = get_latest_skill_gap_analysis(st.session_state.user_id)

    st.title("Skill Gap Analysis")
    st.write("Analyze your skills against the top recommended career and discover where to focus.")

    if not profile:
        st.error("Profile data is required to perform a skill gap analysis.")
        return

    if not resume_data_db:
        st.error("Resume data is required to perform a skill gap analysis.")
        return

    if not latest_prediction:
        st.error("A career recommendation is required before running skill gap analysis.")
        return

    st.markdown("### Current Recommendation")
    st.write(f"**Top Recommended Career:** {latest_prediction['recommended_role']}")
    st.write(f"**Confidence:** {latest_prediction['confidence_score']:.1f}%")

    if previous_analysis:
        st.markdown("---")
        st.subheader("Latest Stored Skill Gap Analysis")
        st.write(f"**Career Role:** {previous_analysis['career_role']}")
        st.write(f"**Skill Match:** {previous_analysis['skill_match_score']:.2f}%")
        st.write(f"**Readiness Score:** {previous_analysis['readiness_score']:.2f}%")
        st.write("**Matched Skills:**")
        st.write([skill for skill in format_skill_list(previous_analysis['matched_skills'].split(', ') if previous_analysis.get('matched_skills') else [])])
        st.write("**Missing Skills:**")
        st.write([skill for skill in format_skill_list(previous_analysis['missing_skills'].split(', ') if previous_analysis.get('missing_skills') else [])])
        st.write("**Extra Skills:**")
        st.write([skill for skill in format_skill_list(previous_analysis['extra_skills'].split(', ') if previous_analysis.get('extra_skills') else [])])

    if st.button("Run Skill Gap Analysis"):
        profile_features = build_profile_features(profile)
        resume_features = build_resume_features(resume_data_db)
        current_skills = build_current_skills(profile_features, resume_features)
        final_career_role = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
        required_skills = get_required_skills_for_career(final_career_role)
        matched_skills, missing_skills, extra_skills = compute_skill_gap(final_career_role, current_skills)
        skill_match_score = calculate_skill_match_score(matched_skills, required_skills)
        readiness_score = calculate_readiness_score(skill_match_score, profile_features)
        priority_categories = categorize_skills_by_priority(missing_skills)

        save_skill_gap_analysis(
            st.session_state.user_id,
            final_career_role,
            matched_skills,
            missing_skills,
            extra_skills,
            skill_match_score,
            readiness_score,
        )

        st.markdown("---")
        st.subheader("Skill Gap Results")
        left, right = st.columns(2)
        with left:
            st.write("**Required Skills:**")
            st.write(format_skill_list(required_skills))
            st.write("**Matched Skills:**")
            st.write(format_skill_list(matched_skills))
            st.write("**Missing Skills:**")
            st.write(format_skill_list(missing_skills))
            st.write("**Extra Skills:**")
            st.write(format_skill_list(extra_skills))
        with right:
            st.subheader("Scores")
            st.metric("Skill Match %", f"{skill_match_score:.2f}%")
            st.progress(skill_match_score / 100)
            st.metric("Readiness Score", f"{readiness_score:.2f}%")
            st.progress(readiness_score / 100)

        st.markdown("---")
        st.subheader("Learning Priority")
        for bucket, skills in priority_categories.items():
            if skills:
                st.write(f"**{bucket}:** {', '.join(format_skill_list(skills))}")
            else:
                st.write(f"**{bucket}:** None")


def roadmap_generator_page():
    if not is_authenticated():
        st.warning("Please log in to access Roadmap Generator.")
        login_page()
        return

    create_roadmap_table_if_missing()
    create_skill_gap_table_if_missing()

    profile = get_profile_by_user_id(st.session_state.user_id)
    resume_data_db = get_resume_data_by_user(st.session_state.user_id)
    latest_prediction = get_latest_career_prediction(st.session_state.user_id)
    latest_skill_gap = get_latest_skill_gap_analysis(st.session_state.user_id)
    previous_roadmap = get_latest_roadmap(st.session_state.user_id)

    st.title("Personalized Roadmap Generator")
    st.write("Build a focused learning roadmap based on your career recommendation, readiness score, and identified skill gaps.")

    if not profile:
        st.error("Profile data is required to generate a roadmap.")
        return

    if not resume_data_db:
        st.error("Resume data is required to generate a roadmap.")
        return

    if not latest_prediction:
        st.error("A career recommendation is required before generating a roadmap.")
        return

    if not latest_skill_gap:
        st.error("A skill gap analysis is required before generating a roadmap.")
        return

    final_career_role = latest_prediction.get("selected_role") or latest_prediction.get("recommended_role")
    readiness_score = float(latest_skill_gap["readiness_score"] or 0.0)
    missing_skills = [skill.strip() for skill in latest_skill_gap["missing_skills"].split(",") if skill.strip()] if latest_skill_gap.get("missing_skills") else []

    st.markdown("### Current Recommendation")
    st.metric("Final Selected Career", final_career_role)
    st.metric("Readiness Score", f"{readiness_score:.2f}%")
    st.write("**Missing Skills:**")
    st.write(format_skill_list(missing_skills) or ["No missing skills detected."])

    selection_type = "AI Recommended" if latest_prediction.get('selected_role') == latest_prediction.get('predicted_role') else "User Selected"
    st.write(f"**Career Selection Type:** {selection_type}")

    project_recommendations = get_project_recommendations(final_career_role)
    certification_recommendations = get_certification_recommendations(final_career_role)
    monthly_map = build_monthly_roadmap(final_career_role, missing_skills, readiness_score)
    roadmap_text = build_roadmap_summary(final_career_role, monthly_map, project_recommendations, certification_recommendations)
    duration_months = len(monthly_map)

    if st.button("Generate and Save Roadmap"):
        try:
            save_roadmap(
                st.session_state.user_id,
                final_career_role,
                roadmap_text,
                duration_months,
                readiness_score,
            )
            st.success("Personalized roadmap saved successfully.")
        except Exception as error:
            st.error(f"Unable to save roadmap: {error}")

    st.markdown("---")
    st.subheader("Roadmap Timeline")
    for month, goals in monthly_map.items():
        with st.expander(month):
            for goal in goals:
                st.write(f"- {goal}")

    st.markdown("---")
    st.subheader("Recommended Projects")
    for project in project_recommendations:
        st.write(f"- {project}")

    st.markdown("---")
    st.subheader("Recommended Certifications")
    for cert in certification_recommendations:
        st.write(f"- {cert}")

    if previous_roadmap:
        st.markdown("---")
        st.subheader("Latest Saved Roadmap")
        st.write(f"**Career Role:** {previous_roadmap['career_role']}")
        st.write(f"**Duration:** {previous_roadmap['duration_months']} months")
        st.write(f"**Readiness Score:** {previous_roadmap['readiness_score']:.2f}%")
        st.write(previous_roadmap["roadmap_text"])


def main():
    set_page_config()
    init_session()
    load_css()
    selection = render_sidebar()

    if selection == "Home":
        home_page_phase1()
    elif selection == "Dashboard":
        if not is_authenticated():
            st.warning("Please log in to view the dashboard.")
        else:
            dashboard_page()
    elif selection == "Login":
        if is_authenticated():
            st.info("You are already logged in.")
            dashboard_page()
        else:
            login_page()
    elif selection == "Register":
        if is_authenticated():
            st.info("You are already logged in.")
            dashboard_page()
        else:
            register_page()
    elif selection == "Profile":
        profile_page()
    elif selection == "Resume Upload":
        resume_upload_page()
    elif selection == "Analytics Dashboard":
        analytics_dashboard_page()
    elif selection == "PDF Career Report":
        pdf_career_report_page()
    elif selection == "Admin Dashboard":
        admin_dashboard_page()
    elif selection == "Career Recommendation":
        career_recommendation_page()
    elif selection == "Skill Gap Analysis":
        skill_gap_analysis_page()
    elif selection == "Roadmap Generator":
        roadmap_generator_page()

    st.sidebar.markdown("---")
    st.sidebar.write("Phase 4: Career Recommendation")


if __name__ == "__main__":
    main()

