import streamlit as streamlite
import json

class QuizAgent:
    
    quiz_data_key = 'quiz_data'
    current_step_key = 'current_step'
    score_key = 'score'
    result_key = 'results'
    quiz_state_key = 'quiz_state'

    def __init__(self):
        
        if self.quiz_state_key not in streamlite.session_state:
            streamlite.session_state[self.quiz_state_key] = 'start' 
            
        if self.quiz_data_key not in streamlite.session_state:
            streamlite.session_state[self.quiz_data_key] = []
        if self.current_step_key not in streamlite.session_state:
            streamlite.session_state[self.current_step_key] = 0
        if self.score_key not in streamlite.session_state:
            streamlite.session_state[self.score_key] = 0
        if self.result_key not in streamlite.session_state:
            streamlite.session_state[self.result_key] = []

    def create_quiz(self, quiz_data: list):
        streamlite.session_state[self.quiz_data_key] = quiz_data
        streamlite.session_state[self.quiz_state_key] = 'questioning'
        streamlite.session_state[self.current_step_key] = 0
        streamlite.session_state[self.score_key] = 0
        streamlite.session_state[self.result_key] = []

    def read_current_question(self) -> dict:
        step = streamlite.session_state.get(self.current_step_key, 0)
        quiz_data = streamlite.session_state.get(self.quiz_data_key, [])
        
        if 0 <= step < len(quiz_data):
            return quiz_data[step]
        return {}

    def read_state(self) -> str:
        return streamlite.session_state[self.quiz_state_key]

    def read_score(self) -> int:
        return streamlite.session_state[self.score_key]

    def read_results(self) -> list:
        return streamlite.session_state[self.result_key]

    def read_quiz_length(self) -> int:
        return len(streamlite.session_state[self.quiz_data_key])

    def set_state(self, new_state: str):
        streamlite.session_state[self.quiz_state_key] = new_state

    def update_score_and_results(self, user_answer, correction_data: dict):        
        current_q_data = self.read_current_question()
        result_log = {
            'question': current_q_data['question'],
            'user_answer': user_answer,
            'correction': correction_data
        }
        
        streamlite.session_state[self.score_key] += correction_data['score']
        streamlite.session_state[self.result_key].append(result_log)
        
        self.set_state('review')

    def update_next_step(self):
        if streamlite.session_state[self.current_step_key] < self.read_quiz_length() - 1:
            streamlite.session_state[self.current_step_key] += 1
            self.set_state('questioning')
        else:
            self.set_state('finished')

    def delete_quiz(self):
        for key in [self.quiz_data_key, self.current_step_key, self.score_key, 
                    self.result_key, self.quiz_state_key]:
            if key in streamlite.session_state:
                del streamlite.session_state[key]
