import streamlit as st


def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = "user"
    if "page" not in st.session_state:
        st.session_state.page = "Home"
    if "predicted_role" not in st.session_state:
        st.session_state.predicted_role = None
    if "selected_role" not in st.session_state:
        st.session_state.selected_role = None
    if "final_selected_role" not in st.session_state:
        st.session_state.final_selected_role = None
    if "prediction_confidence" not in st.session_state:
        st.session_state.prediction_confidence = None
    if "career_selection_type" not in st.session_state:
        st.session_state.career_selection_type = None


def login_user(user: dict):
    st.session_state.authenticated = True
    st.session_state.user_id = user.get("id")
    st.session_state.user_name = user.get("name")
    st.session_state.user_role = user.get("role", "user")
    st.session_state.page = "Dashboard"


def logout_user():
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_role = "user"
    st.session_state.page = "Home"


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def is_admin() -> bool:
    return st.session_state.get("user_role", "user") == "admin"
