import streamlit as streamlit
import json

class QuizAgent:
    """
    Gère le cycle de vie des données du quiz dans st.session_state : 
    questions, score, étape actuelle, résultats et état de l'interface.
    """
    
    # --- Clés de Session (Constantes) ---
    quiz_data_key = 'quiz_data'
    current_step_key = 'current_step'
    score_key = 'score'
    result_key = 'results'
    quiz_state_key = 'quiz_state'

    def __init__(self):
        """Initialise l'état du quiz dans st.session_state si nécessaire."""
        
        # Initialisation de la phase de l'application
        if self.quiz_state_key not in streamlit.session_state:
            # Phases: 'start', 'generating', 'questioning', 'final_review', 'finished'
            streamlit.session_state[self.quiz_state_key] = 'start' 
            
        # Initialisation des données
        if self.quiz_data_key not in streamlit.session_state:
            streamlit.session_state[self.quiz_data_key] = []
        if self.current_step_key not in streamlit.session_state:
            streamlit.session_state[self.current_step_key] = 0
        if self.score_key not in streamlit.session_state:
            streamlit.session_state[self.score_key] = 0
        if self.result_key not in streamlit.session_state:
            streamlit.session_state[self.result_key] = []

    # --- CRUD (Create / Write) ---

    def create_quiz(self, quiz_data: list):
        """
        [CREATE] Stocke les données du quiz générées par le LLM et initialise les variables.
        """
        streamlit.session_state[self.quiz_data_key] = quiz_data
        streamlit.session_state[self.quiz_state_key] = 'questioning'
        streamlit.session_state[self.current_step_key] = 0
        streamlit.session_state[self.score_key] = 0
        streamlit.session_state[self.result_key] = []

    # --- CRUD (Read) ---

    def read_current_question(self) -> dict:
        """[READ] Retourne les données de la question en cours."""
        step = streamlit.session_state.get(self.current_step_key, 0)
        quiz_data = streamlit.session_state.get(self.quiz_data_key, [])
        
        if 0 <= step < len(quiz_data):
            return quiz_data[step]
        return {}
    
    def read_current_question_index(self) -> int:
        """[READ] Retourne l'index (0-basé) de la question en cours."""
        return streamlit.session_state.get(self.current_step_key, 0)
    
    def read_state(self) -> str:
        """[READ] Retourne la phase actuelle du quiz."""
        return streamlit.session_state[self.quiz_state_key]
    
    def read_score(self) -> int:
        """[READ] Retourne le score actuel."""
        return streamlit.session_state[self.score_key]
    
    def read_results(self) -> list:
        """[READ] Retourne le tableau des résultats (questions corrigées)."""
        return streamlit.session_state[self.result_key]
    
    def read_quiz_length(self) -> int:
        """[READ] Retourne le nombre total de questions."""
        return len(streamlit.session_state[self.quiz_data_key])
    
    def set_state(self, new_state: str):
        """Définit la phase du quiz (ex: 'generating')."""
        streamlit.session_state[self.quiz_state_key] = new_state

    def record_answer_and_advance(self, user_answer):
        """Enregistre la réponse de l'utilisateur et passe à l'étape suivante (sans corriger)."""
        current_q_data = self.read_current_question()
        
        result_log = {
            'question_data': current_q_data,
            'user_answer': user_answer,
            'correction': None
        }
        
        streamlit.session_state[self.result_key].append(result_log)
        
        self.update_next_step()

    def update_next_step(self):
        if streamlit.session_state[self.current_step_key] < self.read_quiz_length() - 1:
            streamlit.session_state[self.current_step_key] += 1
            self.set_state('questioning')
        else:
            self.set_state('final_review') 

    def finalize_quiz_results(self, conversation_agent: 'ConversationAgent', model: str):
        """
        Boucle sur toutes les réponses enregistrées et demande la correction au LLM/Python.
        (Nécessite l'instance de ConversationAgent pour l'appel LLM)
        """
        
        streamlit.session_state[self.score_key] = 0
        
        final_results = []
        
        for result in streamlit.session_state[self.result_key]:
            q_data = result['question_data']
            user_answer = result['user_answer']
            
            correction = conversation_agent.get_correction_for_final_review(
                question_data=q_data, 
                user_answer=user_answer, 
                model=model
            )
            
            streamlit.session_state[self.score_key] += correction['score']
            result['correction'] = correction
            final_results.append(result)
            
        streamlit.session_state[self.result_key] = final_results
        self.set_state('finished')

    def delete_quiz(self):
        """[DELETE] Réinitialise toutes les variables de session liées au quiz."""
        for key in [self.quiz_data_key, self.current_step_key, self.score_key, 
                    self.result_key, self.quiz_state_key]:
            if key in streamlit.session_state:
                del streamlit.session_state[key]