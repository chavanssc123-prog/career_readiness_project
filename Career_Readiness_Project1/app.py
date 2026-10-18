import streamlit as st
from database.db_utils import (
    create_profile,
    create_user,
    get_profile_by_user_id,
    get_user_by_email,
    update_profile,
)
from utils.auth import hash_password, verify_password
from utils.profile_utils import calculate_profile_completion
from utils.session_manager import init_session, is_authenticated, login_user, logout_user
from utils.validators import validate_registration


def set_page_config():
    st.set_page_config(
        page_title="AI Career Readiness & Skill Gap Analyzer",
        page_icon="🚀",
        layout="wide",
    )


def load_css():
    css = """
    <style>
        .card-title {
            font-size: 1.35rem;
            font-weight: 700;
        }
        .card-box {
            padding: 1.4rem;
            border-radius: 16px;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.04);
        }
        .feature-card {
            padding: 1.1rem 1rem;
            border-radius: 14px;
            background-color: #ffffff;
            border: 1px solid #e5e5e5;
            transition: transform 0.15s ease-in-out;
        }
        .feature-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 22px rgba(0, 0, 0, 0.06);
        }
        .feature-card h4 {
            margin-bottom: 0.7rem;
        }
        .metric-box {
            padding: 1rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #ffffff, #f2f7ff);
            border: 1px solid #dde6f4;
            text-align: center;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_sidebar():
    st.sidebar.title("Navigation")
    menu_items = ["Home", "Login", "Register", "Profile", "Resume Upload"]

    if is_authenticated():
        menu_items.insert(1, "Dashboard")

    selection = st.sidebar.radio("Go to", menu_items)

    if is_authenticated() and st.sidebar.button("Logout"):
        logout_user()
        st.experimental_rerun()

    return selection


def home_page():
    st.markdown("# AI Career Readiness & Skill Gap Analyzer")
    st.markdown(
        "This platform helps students prepare for future careers by collecting profile data, "
        "evaluating readiness, and enabling future recommendations. Phase 2 builds authentication, profile management, and dashboard tracking."
    )
    st.markdown("---")

    with st.container():
        st.subheader("Future Modules")
        columns = st.columns(3)
        module_data = [
            ("Career Recommendation", "Personalized career suggestions based on your skills and profile."),
            ("Resume Analyzer", "Analyze resume structure and automatically detect keywords."),
            ("ATS Score", "Estimate how well your resume scores against applicant tracking systems."),
            ("Skill Gap Analysis", "Find the missing skills for your target career path."),
            ("Readiness Score", "Assess your readiness for the selected career domain."),
            ("Roadmap Generator", "Generate a learning roadmap for the next 8 weeks."),
        ]

        for index, module in enumerate(module_data):
            with columns[index % 3]:
                st.markdown(
                    f"<div class='feature-card'><h4>{module[0]}</h4><p>{module[1]}</p></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    with st.container():
        st.subheader("Platform Overview")
        st.write(
            "Complete the registration and profile to unlock future modules: resume parsing, career recommendations, "
            "skill gap analysis, ATS scoring, and roadmap generation."
        )


def dashboard_page():
    st.markdown(f"# Welcome, {st.session_state.user_name}")
    profile = get_profile_by_user_id(st.session_state.user_id)
    completion = calculate_profile_completion(profile)

    st.markdown("---")
    st.subheader("Profile Status")
    if profile:
        st.success("Profile found and ready for updates.")
    else:
        st.warning("No profile found yet. Please complete your profile details.")

    st.progress(completion / 100)
    st.markdown(f"**Profile Completion:** {completion}%")

    st.markdown("---")
    metrics = st.columns(4)
    metrics[0].markdown("<div class='metric-box'><h4>Career Recommendation</h4><p>Placeholder</p></div>", unsafe_allow_html=True)
    metrics[1].markdown("<div class='metric-box'><h4>Resume Analyzer</h4><p>Placeholder</p></div>", unsafe_allow_html=True)
    metrics[2].markdown("<div class='metric-box'><h4>ATS Score</h4><p>Placeholder</p></div>", unsafe_allow_html=True)
    metrics[3].markdown("<div class='metric-box'><h4>Skill Gap Analysis</h4><p>Placeholder</p></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Quick Actions")
    action_cards = ["Career Recommendation", "Roadmap Generator", "Resume Upload"]
    action_columns = st.columns(3)

    for col, action in zip(action_columns, action_cards):
        col.markdown(
            f"<div class='card-box'><h4>{action}</h4><p>Coming soon in future phases.</p></div>",
            unsafe_allow_html=True,
        )


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
        st.experimental_rerun()


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

    st.title("Profile")
    st.write("Create or update your career readiness profile information.")

    existing_profile = get_profile_by_user_id(st.session_state.user_id)
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

    with st.form(key="profile_form"):
        cgpa = st.number_input(
            "CGPA",
            min_value=0.0,
            max_value=10.0,
            value=float(existing_profile.get("cgpa", 0.0) if existing_profile else 0.0),
            step=0.1,
        )
        communication = st.slider(
            "Communication Skill",
            1,
            10,
            int(existing_profile.get("communication", 5) if existing_profile else 5),
        )
        logical_reasoning = st.slider(
            "Logical Reasoning",
            1,
            10,
            int(existing_profile.get("logical_reasoning", 5) if existing_profile else 5),
        )
        projects_count = st.number_input(
            "Projects Count",
            min_value=0,
            max_value=50,
            value=int(existing_profile.get("projects_count", 0) if existing_profile else 0),
        )
        certifications_count = st.number_input(
            "Certifications Count",
            min_value=0,
            max_value=50,
            value=int(existing_profile.get("certifications_count", 0) if existing_profile else 0),
        )
        internship_count = st.number_input(
            "Internship Count",
            min_value=0,
            max_value=10,
            value=int(existing_profile.get("internship_count", 0) if existing_profile else 0),
        )
        interest_domain = st.selectbox(
            "Interest Domain",
            interest_options,
            index=default_interest_index,
        )
        submitted = st.form_submit_button("Save Profile")

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
                st.success("Profile updated successfully.")
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
                st.success("Profile created successfully.")
            st.experimental_rerun()
        except Exception as error:
            st.error(f"Unable to save profile information: {error}")

    if existing_profile:
        st.markdown("### Existing Profile")
        st.write(existing_profile)


def resume_upload_page():
    st.title("Resume Upload")
    st.write("Resume upload and parsing features will be implemented in Phase 3.")
    st.file_uploader("Upload your resume (PDF)", type=["pdf"])


def main():
    set_page_config()
    init_session()
    load_css()
    selection = render_sidebar()

    if selection == "Home":
        home_page()
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

    st.sidebar.markdown("---")
    st.sidebar.write("Phase 2: Authentication and Profile Management")


if __name__ == "__main__":
    main()
