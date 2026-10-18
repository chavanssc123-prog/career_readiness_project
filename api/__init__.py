"""FastAPI layer for the Career Readiness project.

This package is an *additional* entry point next to the Streamlit app (app.py).
It reuses database/, models/, utils/ and resume_parser/ exactly as they are and
never imports app.py or utils.session_manager (which depend on Streamlit).
"""
