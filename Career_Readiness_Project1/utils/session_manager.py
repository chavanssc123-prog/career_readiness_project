import streamlit as st


def init_session():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "page" not in st.session_state:
        st.session_state.page = "Home"


def login_user(user: dict):
    st.session_state.authenticated = True
    st.session_state.user_id = user.get("id")
    st.session_state.user_name = user.get("name")
    st.session_state.page = "Dashboard"


def logout_user():
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.page = "Home"


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)
