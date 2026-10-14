from pathlib import Path
import streamlit as st

def apply_dashboard_style():
    css_path = Path(__file__).resolve().parent / ".streamlit" / "dashboard.css"
    css = css_path.read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
