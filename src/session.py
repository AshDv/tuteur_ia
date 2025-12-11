import streamlit as st

class SessionManager:
    """Initialise et gère les variables de session Streamlit."""
    
    @staticmethod
    def initialize_state():
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "current_quiz" not in st.session_state:
            st.session_state.current_quiz = None
        if "quiz_submitted" not in st.session_state:
            st.session_state.quiz_submitted = False
        if "user_answers" not in st.session_state:
            st.session_state.user_answers = {}

    @staticmethod
    def add_message(role: str, content: str):
        st.session_state.messages.append({"role": role, "content": content})

    @staticmethod
    def clear_quiz_state():
        st.session_state.user_answers = {}
        st.session_state.quiz_submitted = False