import sys
import os
import base64
import streamlit as st
from io import BytesIO
from app import ConversationAgent
from quiz_agent import QuizAgent
from utils import DocumentProcessor

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))

if project_root not in sys.path:
    sys.path.append(project_root)

from resources.config import LLM_MODELS

if "selected_model" not in st.session_state:
    st.session_state.selected_model = LLM_MODELS[0]
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def initialize_session():
    """Initialise tous les agents et les variables de session."""
    
    if "quiz_manager" not in st.session_state:
        st.session_state.quiz_manager = QuizAgent()
    
    if "conversation_agent" not in st.session_state:
        st.session_state.conversation_agent = ConversationAgent(
            quiz_agent=st.session_state.quiz_manager
        )
    
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = LLM_MODELS[0]
    if "course_text_content" not in st.session_state:
        st.session_state.course_text_content = ""
    if "image_base64_url" not in st.session_state:
        st.session_state.image_base64_url = None

def render_start_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Affiche les contrôles pour démarrer le quiz et la zone de conversation standard."""
    
    st.header("Démarrez un cycle de révision.")
    
    default_topic = "le cours ci-joint" if st.session_state.course_text_content else "un sujet libre"
    
    st.markdown("### Configuration du Quiz")
    
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        topic = st.text_input("Sujet de l'évaluation", value=default_topic, 
                            placeholder="Ex: La Révolution Française")
    with c2:
        num_questions = st.slider("Nb Questions", 1, 20, 3)
    with c3:
        st.session_state.selected_model = st.selectbox(
            "Modèle", 
            options=LLM_MODELS,
            index=0,
            key='llm_select_quiz'
        )
    with c4:
        difficulty = st.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])
    
    if st.button("🚀 Générer l'évaluation") and topic:
        
        st.session_state['topic'] = topic
        st.session_state['num_questions'] = num_questions
        st.session_state['difficulty'] = difficulty
        
        quiz_manager.set_state('generating')
        st.rerun()


def render_questioning_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Affiche la question en cours et le formulaire de réponse."""
    
    q_data = quiz_manager.read_current_question()
    q_index = quiz_manager.read_quiz_length() - (quiz_manager.read_quiz_length() - quiz_manager.read_current_question_index())
    
    st.header(f"Question {q_index + 1}/{quiz_manager.read_quiz_length()}")
    st.subheader(q_data['question'])
    
    user_answer = ""
    
    with st.form("current_question_form", clear_on_submit=True):
        
        if q_data['type'] == 'qcm':
            choices_with_letters = q_data['choices']          
            user_choice_with_letter = st.radio(
                "Choisis ta réponse :",
                options=choices_with_letters, 
                index=None,
                key='qcm_answer'
            )
            if user_choice_with_letter:
                user_answer = user_choice_with_letter[0] 
                
        else:
            user_answer = st.text_area("Ta réponse rédigée :", key='open_answer')
            
        
        if st.form_submit_button("Soumettre la Réponse et Passer à la Suivante"):
            if not user_answer:
                st.warning("Veuillez saisir ou choisir une réponse, Sensei n'aime pas le vide.")
                return 

            quiz_manager.record_answer_and_advance(user_answer)
            st.rerun()

def render_final_review_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Déclenche la correction finale par le LLM et passe à l'affichage des résultats."""
    
    model_id = st.session_state.selected_model
    
    st.header("Correction en Cours...")
    st.info("Maître Splinter évalue la qualité de votre pratique. Cela peut prendre quelques instants pour les questions ouvertes.")
    
    with st.spinner("Évaluation finale par le tuteur IA..."):
        quiz_manager.finalize_quiz_results(agent, model=model_id)
        
    st.rerun()

def render_finished_interface(quiz_manager: QuizAgent):
    
    total = quiz_manager.read_quiz_length()
    score = quiz_manager.read_score()
    
    st.header("🔥 Fin de l'Évaluation 🔥")
    st.success(f"### 🏆 Score Final : {score} / {total}")
    
    st.markdown("---")
    st.subheader("Correction Détaillée de Maître Splinter :")
    
    for i, result in enumerate(quiz_manager.read_results()):
        q_data = result['question_data']
        correction = result['correction']
        
        status_icon = "✅" if correction['score'] == 1 else "❌"
        st.markdown(f"#### {status_icon} Question {i+1}: {q_data['question']}")
        
        st.markdown(f"**Votre réponse :** *{result['user_answer']}*")
        
        st.info(f"**Feedback du Sensei :** {correction['feedback']}")

        if q_data['type'] == 'qcm':
            st.caption(f"Réponse attendue : {q_data['correct_identifier']}")
            
        st.write("---")

    if st.button("🥋 Recommencer l'Entraînement"):
        quiz_manager.delete_quiz()
        st.rerun()

def render_chat_history(agent: ConversationAgent):
    
    for message in agent.history:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                if "image_url" in message and message["image_url"]:
                    st.image(message["image_url"], width=300) 

def render_chat_input(agent: ConversationAgent):
    """Gère l'entrée utilisateur pour le mode conversationnel/vision."""
    
    uploaded_image_file = st.session_state.get('img_uploader')
    
    if user_input := st.chat_input("Pose ta question ou demande un résumé à Splinter..."):
        
        context_text = st.session_state.course_text_content
        model_id = st.session_state.selected_model
        image_url_full = None
        
        if uploaded_image_file:
            uploaded_image_file.seek(0)
            
            image_b64_raw = base64.b64encode(uploaded_image_file.read()).decode('utf-8')
            mime_type = uploaded_image_file.type
            
            image_url_full = f"data:{mime_type};base64,{image_b64_raw}"
            
        with st.spinner("Splinter réfléchit..."):
            
            if uploaded_image_file:
                response = agent.ask_vision_model(
                    user_interaction=user_input,
                    image_b64=image_b64_raw,
                    mime_type=mime_type,
                    image_url_for_display=image_url_full,
                    model=VISION_MODEL
                )
            else:
                response = agent.ask_llm(
                    user_interaction=user_input,
                    model=model_id,
                    context_text=context_text
                )
        
        if 'img_uploader' in st.session_state:
            del st.session_state['img_uploader']
            
        st.rerun()

def run_app():
    """Point d'entrée principal de l'application Streamlit."""
    
    st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")
    initialize_session()
    
    agent = st.session_state.conversation_agent
    quiz_manager = st.session_state.quiz_manager
    current_state = quiz_manager.read_state()
    
    with st.sidebar:
        st.title("📚 Outils d'Entraînement")
        
        uploaded_pdf_list = st.file_uploader(
            "Fichiers PDF (Cours - Max. 5)", 
            type="pdf", 
            key="pdf_uploader",
            accept_multiple_files=True
        )
        
        if uploaded_pdf_list:
            
            uploaded_pdf_list = uploaded_pdf_list[:5]
            
            st.session_state.course_text_content = ""
            
            with st.spinner(f"Analyse de {len(uploaded_pdf_list)} documents..."):
                
                all_text_with_names = []
                total_chars = 0
                
                for pdf_file in uploaded_pdf_list:
                    text = DocumentProcessor.extract_text_from_pdf(pdf_file)
                    
                    separator_and_text = f"\n--- Fichier : {pdf_file.name} ---\n{text}"
                    all_text_with_names.append(separator_and_text)
                    total_chars += len(text)
                
                st.session_state.course_text_content = "\n".join(all_text_with_names)
                
                st.success(f"{len(uploaded_pdf_list)} PDF(s) chargés en mémoire !")
                st.caption(f"Total : {total_chars} caractères.")
        
        elif 'course_text_content' in st.session_state:
            st.session_state.course_text_content = ""
        
        st.divider()

        uploaded_image_list = st.file_uploader(
            "Schémas/Graphiques (pour analyse vision - Max. 5)", 
            type=["png", "jpg", "jpeg"], 
            key="img_uploader",
            accept_multiple_files=True
        )
        
        st.session_state.image_base64_url = []
        if uploaded_image_list:
            
            if len(uploaded_image_list) > 5:
                st.warning("Seuls les 5 premières images seront traitées.")
                uploaded_image_list = uploaded_image_list[:5]
                
            for img_file in uploaded_image_list:
                base64_url = DocumentProcessor.convert_image_to_base64(img_file)
                if base64_url:
                    st.session_state.image_base64_url.append(base64_url)
                    st.image(img_file, width=150) # Affichage de l'aperçu dans la sidebar
            
            if st.session_state.image_base64_url:
                st.success(f"{len(st.session_state.image_base64_url)} image(s) prête(s) !")

    
    st.title("🐭 Maître Splinter - Tuteur IA")
    
    if current_state in ['start', 'questioning', 'final_review', 'finished']:
        tab_chat, tab_quiz = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
    else:
        tab_chat, tab_quiz = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
        
    
    with tab_chat:
        st.header("Discours & Sagesse du Maître")
        
        st.session_state.selected_model = st.selectbox(
            "Modèle de Conversation", 
            options=LLM_MODELS,
            index=0,
            key='llm_select_chat'
        )
        
        render_chat_history(agent)
        
        if current_state == 'start':
            render_chat_input(agent)
        elif current_state != 'start':
            st.warning("Veuillez compléter ou annuler le quiz avant de commencer une nouvelle discussion.")


    with tab_quiz:
        
        if current_state == 'start':
            render_start_interface(agent, quiz_manager)

        elif current_state == 'generating':
            with st.spinner("Création du questionnaire par le Maître..."):
                model_id = st.session_state.selected_model
                topic_input = st.session_state.get('topic', 'sujet libre')
                num_questions = st.session_state.get('num_questions', 3)
                context_text = st.session_state.course_text_content
                difficulty = st.session_state.get('difficulty', 'Moyen')
                success = st.session_state.conversation_agent.generate_quiz(
                    topic=topic_input, 
                    n_questions=num_questions, 
                    model=model_id,
                    context_instruction=context_text,
                    difficulty=difficulty
                )
                
                if not success:
                    st.error("❌ Échec de la génération du quiz. Vérifiez le sujet ou le format JSON.")
                    quiz_manager.set_state('start')
                    
                st.rerun()

        elif current_state == 'questioning':
            render_questioning_interface(agent, quiz_manager)

        elif current_state == 'final_review':
            render_final_review_interface(agent, quiz_manager)

        elif current_state == 'finished':
            render_finished_interface(quiz_manager)


if __name__ == "__main__":
    run_app()