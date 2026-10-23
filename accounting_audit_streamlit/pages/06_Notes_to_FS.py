import streamlit as st
from src.financial_statements import draft_notes_checklist
st.title("Notes to Financial Statements")
st.dataframe(draft_notes_checklist(),use_container_width=True)
