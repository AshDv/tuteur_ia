import sys
import os
import base64
import streamlit as streamlit
from app import ConversationAgent
from quiz_agent import QuizAgent
from utils import DocumentProcessor

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))

if project_root not in sys.path:
    sys.path.append(project_root)

from resources.config import LLM_MODELS

if "uploader_key" not in streamlit.session_state:
    streamlit.session_state.uploader_key = 0

if "selected_model" not in streamlit.session_state:
    streamlit.session_state.selected_model = LLM_MODELS[0]
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def initialize_session():
    
    if "quiz_manager" not in streamlit.session_state:
        streamlit.session_state.quiz_manager = QuizAgent()
    
    if "conversation_agent" not in streamlit.session_state:
        streamlit.session_state.conversation_agent = ConversationAgent(
            quiz_agent=streamlit.session_state.quiz_manager
        )
    
    if "course_text_content" not in streamlit.session_state:
        streamlit.session_state.course_text_content = ""
    if "image_base64_url" not in streamlit.session_state:
        streamlit.session_state.image_base64_url = None

def render_start_interface(conversation_agent: ConversationAgent, quiz_manager: QuizAgent):
    
    streamlit.header("Démarrez un cycle de révision.")
    
    default_topic = "le cours ci-joint" if streamlit.session_state.course_text_content else "un sujet libre"
    
    streamlit.markdown("### Configuration du Quiz")
    
    c1, c2, c3, c4 = streamlit.columns([3, 1, 1, 1])
    with c1:
        topic = streamlit.text_input("Sujet de l'évaluation", value=default_topic, 
                            placeholder="Ex: La Révolution Française")
    with c2:
        num_questions = streamlit.slider("Nb Questions", 1, 20, 3)
    with c3:
        streamlit.session_state.selected_model = streamlit.selectbox(
            "Modèle", 
            options=LLM_MODELS,
            index=2,
            key='llm_select_quiz'
        )
    with c4:
        difficulty = streamlit.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])
    
    if streamlit.button("🚀 Générer l'évaluation") and topic:
        
        streamlit.session_state['topic'] = topic
        streamlit.session_state['num_questions'] = num_questions
        streamlit.session_state['difficulty'] = difficulty
        
        quiz_manager.set_state('generating')
        streamlit.rerun()


def render_questioning_interface(conversation_agent: ConversationAgent, quiz_manager: QuizAgent):
    """Affiche la question en cours et le formulaire de réponse."""
    
    q_data = quiz_manager.read_current_question()
    q_index = quiz_manager.read_quiz_length() - (quiz_manager.read_quiz_length() - quiz_manager.read_current_question_index())
    
    streamlit.header(f"Question {q_index + 1}/{quiz_manager.read_quiz_length()}")
    streamlit.subheader(q_data['question'])
    
    user_answer = ""
    
    with streamlit.form("current_question_form", clear_on_submit=True):
        
        if q_data['type'] == 'qcm':
            choices_with_letters = q_data['choices']          
            user_choice_with_letter = streamlit.radio(
                "Choisis ta réponse :",
                options=choices_with_letters, 
                index=None,
                key='qcm_answer'
            )
            if user_choice_with_letter:
                user_answer = user_choice_with_letter[0] 
                
        else:
            user_answer = streamlit.text_area("Ta réponse rédigée :", key='open_answer')
            
        
        if streamlit.form_submit_button("Soumettre la Réponse et Passer à la Suivante"):
            if not user_answer:
                streamlit.warning("Veuillez saisir ou choisir une réponse, Sensei n'aime pas le vide.")
                return 

            quiz_manager.record_answer_and_advance(user_answer)
            streamlit.rerun()

def render_final_review_interface(conversation_agent: ConversationAgent, quiz_manager: QuizAgent):
    """Déclenche la correction finale par le LLM et passe à l'affichage des résultats."""
    
    model_id = streamlit.session_state.selected_model
    
    streamlit.header("Correction en Cours...")
    streamlit.info("Maître Splinter évalue la qualité de votre pratique. Cela peut prendre quelques instants pour les questions ouvertes.")
    
    with streamlit.spinner("Évaluation finale par le tuteur IA..."):
        quiz_manager.finalize_quiz_results(conversation_agent, model=model_id)
        
    streamlit.rerun()

def render_finished_interface(quiz_manager: QuizAgent):
    
    total = quiz_manager.read_quiz_length()
    score = quiz_manager.read_score()
    
    streamlit.header("🔥 Fin de l'Évaluation 🔥")
    streamlit.success(f"### 🏆 Score Final : {score} / {total}")
    
    streamlit.markdown("---")
    streamlit.subheader("Correction Détaillée de Maître Splinter :")
    
    for i, result in enumerate(quiz_manager.read_results()):
        q_data = result['question_data']
        correction = result['correction']
        
        status_icon = "✅" if correction['score'] == 1 else "❌"
        streamlit.markdown(f"#### {status_icon} Question {i+1}: {q_data['question']}")
        
        streamlit.markdown(f"**Votre réponse :** *{result['user_answer']}*")
        
        streamlit.info(f"**Feedback du Sensei :** {correction['feedback']}")

        if q_data['type'] == 'qcm':
            streamlit.caption(f"Réponse attendue : {q_data['correct_identifier']}")
            
        streamlit.write("---")

    if streamlit.button("🥋 Recommencer l'Entraînement"):
        quiz_manager.delete_quiz()
        streamlit.rerun()

def render_chat_history(conversation_agent: ConversationAgent):
    
    for message in conversation_agent.history:
        if message["role"] != "system":
            with streamlit.chat_message(message["role"]):
                streamlit.markdown(message["content"])
                
                if "image_url" in message and message["image_url"]:
                    streamlit.image(message["image_url"], width=300) 

def render_chat_input(conversation_agent: ConversationAgent):
    """Gère l'entrée utilisateur pour le mode conversationnel/vision."""
    
    # Récupère la LISTE des fichiers (grâce à accept_multiple_files=True)
    uploaded_images_list = streamlit.session_state.get('img_uploader')
    
    if user_input := streamlit.chat_input("Pose ta question ou demande un résumé à Splinter..."):
        
        context_text = streamlit.session_state.course_text_content
        model_id = streamlit.session_state.selected_model
        
        # Préparation des données images
        images_data = []
        
        if uploaded_images_list:
            # On boucle sur chaque fichier de la liste
            for img_file in uploaded_images_list:
                img_file.seek(0)
                image_b64_raw = base64.b64encode(img_file.read()).decode('utf-8')
                mime_type = img_file.type
                
                images_data.append({
                    'b64': image_b64_raw,
                    'mime': mime_type,
                    'display_url': f"data:{mime_type};base64,{image_b64_raw}"
                })
            
        with streamlit.spinner("Splinter réfléchit..."):
            
            if images_data:
                # On appelle la nouvelle version de la fonction qui accepte une liste
                response = conversation_agent.ask_vision_model(
                    user_interaction=user_input,
                    images_data=images_data, # On passe la liste complète
                    model=VISION_MODEL
                )
            else:
                response = conversation_agent.ask_llm(
                    user_interaction=user_input,
                    model=model_id,
                    context_text=context_text
                )
        
        if 'img_uploader' in streamlit.session_state:
            del streamlit.session_state['img_uploader']
            
        streamlit.rerun()

def run_app():
    """Point d'entrée principal de l'application Streamlit."""
    
    streamlit.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")
    initialize_session()
    
    agent = streamlit.session_state.conversation_agent
    quiz_manager = streamlit.session_state.quiz_manager
    current_state = quiz_manager.read_state()
    
    with streamlit.sidebar:
        streamlit.title("📚 Outils d'Entraînement")
        
        uploaded_pdf_list = streamlit.file_uploader(
            "Fichiers PDF (Cours - Max. 5)", 
            type="pdf", 
            key="pdf_uploader",
            accept_multiple_files=True,
        )
        
        if uploaded_pdf_list:
            
            uploaded_pdf_list = uploaded_pdf_list[:5]
            
            streamlit.session_state.course_text_content = ""
            
            with streamlit.spinner(f"Analyse de {len(uploaded_pdf_list)} documents..."):
                
                all_text_with_names = []
                total_chars = 0
                
                for pdf_file in uploaded_pdf_list:
                    text = DocumentProcessor.extract_text_from_pdf(pdf_file)
                    
                    separator_and_text = f"\n--- Fichier : {pdf_file.name} ---\n{text}"
                    all_text_with_names.append(separator_and_text)
                    total_chars += len(text)
                
                streamlit.session_state.course_text_content = "\n".join(all_text_with_names)
                
                streamlit.success(f"{len(uploaded_pdf_list)} PDF(s) chargés en mémoire !")
                streamlit.caption(f"Total : {total_chars} caractères.")
        
        elif 'course_text_content' in streamlit.session_state:
            streamlit.session_state.course_text_content = ""
        
        streamlit.divider()

        uploaded_image_list = streamlit.file_uploader(
            "Schémas/Graphiques (pour analyse vision - Max. 5)", 
            type=["png", "jpg", "jpeg"], 
            key="img_uploader",
            accept_multiple_files=True,
        )
        
        streamlit.session_state.image_base64_url = []
        if uploaded_image_list:
            
            if len(uploaded_image_list) > 5:
                streamlit.warning("Seuls les 5 premières images seront traitées.")
                uploaded_image_list = uploaded_image_list[:5]
                
            for img_file in uploaded_image_list:
                base64_url = DocumentProcessor.convert_image_to_base64(img_file)
                if base64_url:
                    streamlit.session_state.image_base64_url.append(base64_url)
                    streamlit.image(img_file, width=150) # Affichage de l'aperçu dans la sidebar
            
            if streamlit.session_state.image_base64_url:
                streamlit.success(f"{len(streamlit.session_state.image_base64_url)} image(s) prête(s) !")

    
    streamlit.title("🐭 Maître Splinter - Tuteur IA")
    
    if current_state in ['start', 'questioning', 'final_review', 'finished']:
        tab_chat, tab_quiz = streamlit.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
    else:
        tab_chat, tab_quiz = streamlit.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
        
    
    with tab_chat:
        streamlit.header("Discours & Sagesse du Maître")
        
        streamlit.session_state.selected_model = streamlit.selectbox(
            "Modèle de Conversation", 
            options=LLM_MODELS,
            index=2,
            key='llm_select_chat'
        )
        
        render_chat_history(agent)
        
        if current_state == 'start':
            render_chat_input(agent)
        elif current_state != 'start':
            streamlit.warning("Veuillez compléter ou annuler le quiz avant de commencer une nouvelle discussion.")


    with tab_quiz:
        
        if current_state == 'start':
            render_start_interface(agent, quiz_manager)

        elif current_state == 'generating':
            with streamlit.spinner("Création du questionnaire par le Maître..."):
                model_id = streamlit.session_state.selected_model
                topic_input = streamlit.session_state.get('topic', 'sujet libre')
                num_questions = streamlit.session_state.get('num_questions', 3)
                context_text = streamlit.session_state.course_text_content
                difficulty = streamlit.session_state.get('difficulty', 'Moyen')
                success = streamlit.session_state.conversation_agent.generate_quiz(
                    topic=topic_input, 
                    n_questions=num_questions, 
                    model=model_id,
                    context_instruction=context_text,
                    difficulty=difficulty
                )
                
                if not success:
                    streamlit.error("❌ Échec de la génération du quiz. Vérifiez le sujet ou le format JSON.")
                    quiz_manager.set_state('start')
                    
                streamlit.rerun()

        elif current_state == 'questioning':
            render_questioning_interface(agent, quiz_manager)

        elif current_state == 'final_review':
            render_final_review_interface(agent, quiz_manager)

        elif current_state == 'finished':
            render_finished_interface(quiz_manager)


if __name__ == "__main__":
    run_app()