import streamlit as streamlit
import json

class QuizAgent:
    
    quiz_data_key = 'quiz_data'
    current_step_key = 'current_step'
    score_key = 'score'
    result_key = 'results'
    quiz_state_key = 'quiz_state'

    def __init__(self):
        
        if self.quiz_state_key not in streamlit.session_state:
            streamlit.session_state[self.quiz_state_key] = 'start' 
            
        if self.quiz_data_key not in streamlit.session_state:
            streamlit.session_state[self.quiz_data_key] = []
        if self.current_step_key not in streamlit.session_state:
            streamlit.session_state[self.current_step_key] = 0
        if self.score_key not in streamlit.session_state:
            streamlit.session_state[self.score_key] = 0
        if self.result_key not in streamlit.session_state:
            streamlit.session_state[self.result_key] = []

    def create_quiz(self, quiz_data: list):
        streamlit.session_state[self.quiz_data_key] = quiz_data
        streamlit.session_state[self.quiz_state_key] = 'questioning'
        streamlit.session_state[self.current_step_key] = 0
        streamlit.session_state[self.score_key] = 0
        streamlit.session_state[self.result_key] = []

    def read_current_question(self) -> dict:
        step = streamlit.session_state.get(self.current_step_key, 0)
        quiz_data = streamlit.session_state.get(self.quiz_data_key, [])
        
        if 0 <= step < len(quiz_data):
            return quiz_data[step]
        return {}
    
    def read_current_question_index(self) -> int:
        return streamlit.session_state.get(self.current_step_key, 0)
    
    def read_state(self) -> str:
        return streamlit.session_state[self.quiz_state_key]
    
    def read_score(self) -> int:
        return streamlit.session_state[self.score_key]
    
    def read_results(self) -> list:
        return streamlit.session_state[self.result_key]
    
    def read_quiz_length(self) -> int:
        return len(streamlit.session_state[self.quiz_data_key])
    
    def set_state(self, new_state: str):
        streamlit.session_state[self.quiz_state_key] = new_state

    def record_answer_and_advance(self, user_answer):
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
        streamlit.session_state[self.quiz_data_key] = []
        streamlit.session_state[self.current_step_key] = 0
        streamlit.session_state[self.score_key] = 0
        streamlit.session_state[self.result_key] = []
        streamlit.session_state[self.quiz_state_key] = 'start'