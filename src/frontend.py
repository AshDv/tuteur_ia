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
    
    # 1. Initialisation de l'état du quiz
    if "quiz_manager" not in st.session_state:
        st.session_state.quiz_manager = QuizAgent()
    
    # 2. Initialisation de l'agent principal (avec injection de dépendance)
    if "conversation_agent" not in st.session_state:
        st.session_state.conversation_agent = ConversationAgent(
            quiz_agent=st.session_state.quiz_manager
        )
    
    # Variables pour le frontal
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = LLM_MODELS[0]
    if "course_text_content" not in st.session_state:
        st.session_state.course_text_content = ""
    if "image_base64_url" not in st.session_state:
        st.session_state.image_base64_url = None

# --- FONCTIONS D'AFFICHAGE DU FLUX QUIZ ---

def render_start_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Affiche les contrôles pour démarrer le quiz et la zone de conversation standard."""
    
    st.header("Démarrez un cycle de révision.")
    
    # Récupération du sujet si un PDF a été chargé
    default_topic = "le cours ci-joint" if st.session_state.course_text_content else "un sujet libre"
    
    st.markdown("### Configuration du Quiz")
    
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        topic = st.text_input("Sujet de l'évaluation", value=default_topic, 
                            placeholder="Ex: La Révolution Française")
    with c2:
        num_questions = st.slider("Nb Questions", 1, 10, 3)
    with c3:
        st.session_state.selected_model = st.selectbox(
            "Modèle", 
            options=LLM_MODELS,
            index=0,
            key='llm_select_quiz'
        )
    
    
    if st.button("🚀 Générer l'évaluation") and topic:
        quiz_manager.set_state('generating')
        st.rerun() # Recharger pour afficher le spinner


def render_questioning_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Affiche la question en cours et le formulaire de réponse."""
    
    q_data = quiz_manager.read_current_question()
    q_index = quiz_manager.read_quiz_length() - (quiz_manager.read_quiz_length() - quiz_manager.read_current_question_index())
    
    # Affichage de l'énoncé
    st.header(f"Question {q_index + 1}/{quiz_manager.read_quiz_length()}")
    st.subheader(q_data['question'])
    
    user_answer = ""
    
    # Formulaire de soumission
    with st.form("current_question_form", clear_on_submit=True):
        
        # Logique de l'interface QCM vs OUVERTE
        if q_data['type'] == 'qcm':
            # Interface QCM : Radio buttons
            choices_with_letters = [f"{chr(65 + i)}. {choice}" for i, choice in enumerate(q_data['choices'])]
            
            # Stocke la réponse complète (ex: "A. Choix 1")
            user_choice_with_letter = st.radio(
                "Choisis ta réponse :",
                options=choices_with_letters, 
                index=None,
                key='qcm_answer'
            )
            if user_choice_with_letter:
                # On stocke uniquement la lettre (A, B, C, D) pour la correction
                user_answer = user_choice_with_letter[0] 
                
        else: # type == 'open'
            # Interface Ouverte : Zone de texte
            user_answer = st.text_area("Ta réponse rédigée :", key='open_answer')
            
        
        # Bouton de soumission
        if st.form_submit_button("Soumettre la Réponse et Passer à la Suivante"):
            if not user_answer:
                st.warning("Veuillez saisir ou choisir une réponse, Sensei n'aime pas le vide.")
                return 

            # Enregistre la réponse et avance l'état (sans correction immédiate)
            quiz_manager.record_answer_and_advance(user_answer)
            st.rerun() # Recharger pour passer à la question suivante ou à la fin

def render_final_review_interface(agent: ConversationAgent, quiz_manager: QuizAgent):
    """Déclenche la correction finale par le LLM et passe à l'affichage des résultats."""
    
    # Utilise le modèle sélectionné par l'utilisateur pour le quiz
    model_id = st.session_state.selected_model
    
    st.header("Correction en Cours...")
    st.info("Maître Splinter évalue la qualité de votre pratique. Cela peut prendre quelques instants pour les questions ouvertes.")
    
    with st.spinner("Évaluation finale par le tuteur IA..."):
        # Appel de la méthode qui boucle et corrige toutes les réponses
        quiz_manager.finalize_quiz_results(agent, model=model_id)
        
    st.rerun() # Passe à l'état 'finished'

def render_finished_interface(quiz_manager: QuizAgent):
    """Affiche le score final et les corrections détaillées."""
    
    total = quiz_manager.read_quiz_length()
    score = quiz_manager.read_score()
    
    st.header("🔥 Fin de l'Évaluation 🔥")
    st.success(f"### 🏆 Score Final : {score} / {total}")
    
    st.markdown("---")
    st.subheader("Correction Détaillée de Maître Splinter :")
    
    # Boucle sur les résultats corrigés
    for i, result in enumerate(quiz_manager.read_results()):
        q_data = result['question_data']
        correction = result['correction']
        
        # Affichage du statut
        status_icon = "✅" if correction['score'] == 1 else "❌"
        st.markdown(f"#### {status_icon} Question {i+1}: {q_data['question']}")
        
        st.markdown(f"**Votre réponse :** *{result['user_answer']}*")
        
        # Affichage du feedback (ton de Maître Splinter)
        st.info(f"**Feedback du Sensei :** {correction['feedback']}")

        if q_data['type'] == 'qcm':
            # Afficher la bonne lettre si c'était un QCM
            st.caption(f"Réponse attendue : {q_data['correct_identifier']}")
            
        st.write("---")

    if st.button("🥋 Recommencer l'Entraînement"):
        quiz_manager.delete_quiz()
        st.rerun()

# --- FONCTIONS D'AFFICHAGE DU FLUX DE CHAT ---

def render_chat_history(agent: ConversationAgent):
    """Affiche l'historique de la conversation, y compris les images."""
    
    # L'historique d'affichage est conservé dans agent.history
    for message in agent.history:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Affichage de l'image si la clé existe (stockée en Data URI)
                if "image_url" in message and message["image_url"]:
                    # Utiliser width pour éviter le warning de dépréciation
                    st.image(message["image_url"], width=300) 

def render_chat_input(agent: ConversationAgent):
    """Gère l'entrée utilisateur pour le mode conversationnel/vision."""
    
    # Détecter si l'utilisateur a chargé une image
    uploaded_image_file = st.session_state.get('img_uploader')
    
    if user_input := st.chat_input("Pose ta question ou demande un résumé à Splinter..."):
        
        # Récupération des données pour l'appel
        context_text = st.session_state.course_text_content
        model_id = st.session_state.selected_model
        image_url_full = None
        
        # Traitement de l'image si elle est présente
        if uploaded_image_file:
            # Assurez-vous que l'objet fichier est réinitialisé avant l'encodage
            uploaded_image_file.seek(0)
            
            # Encoder pour l'API
            image_b64_raw = base64.b64encode(uploaded_image_file.read()).decode('utf-8')
            mime_type = uploaded_image_file.type
            
            # Préparer l'URL d'affichage
            image_url_full = f"data:{mime_type};base64,{image_b64_raw}"
            
        with st.spinner("Splinter réfléchit..."):
            
            if uploaded_image_file:
                # --- MODE VISION ---
                response = agent.ask_vision_model(
                    user_interaction=user_input,
                    image_b64=image_b64_raw,
                    mime_type=mime_type,
                    image_url_for_display=image_url_full,
                    model=VISION_MODEL # Vision utilise un modèle spécifique
                )
            else:
                # --- MODE CHAT/DOCUMENT ---
                response = agent.ask_llm(
                    user_interaction=user_input,
                    model=model_id,
                    context_text=context_text # Passage du contenu du PDF
                )
        
        # Réinitialisation du file uploader (pour ne pas réutiliser l'image)
        if 'img_uploader' in st.session_state:
            del st.session_state['img_uploader']
            
        st.rerun()


# --- FENÊTRE PRINCIPALE ---

def run_app():
    """Point d'entrée principal de l'application Streamlit."""
    
    st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")
    initialize_session()
    
    agent = st.session_state.conversation_agent
    quiz_manager = st.session_state.quiz_manager
    current_state = quiz_manager.read_state()
    
    # --- BARRE LATÉRALE ---
    with st.sidebar:
        # ... (image, titre)
        st.title("📚 Outils d'Entraînement")
        
        # 1. Upload PDF (GESTION MULTIPLE)
        # 💡 Changement 1 : Utilisation de accept_multiple_files=True
        uploaded_pdf_list = st.file_uploader(
            "Fichiers PDF (Cours - Max. 5)", 
            type="pdf", 
            key="pdf_uploader",
            accept_multiple_files=True # Permet de charger plusieurs fichiers
        )
        
        # Logique de lecture des PDF (à adapter)
        if uploaded_pdf_list and not st.session_state.course_text_content:
            
            # Limiter à 5 fichiers
            if len(uploaded_pdf_list) > 5:
                st.warning("Seuls les 5 premiers fichiers seront traités.")
                uploaded_pdf_list = uploaded_pdf_list[:5]
            
            with st.spinner(f"Analyse de {len(uploaded_pdf_list)} documents..."):
                all_text = []
                total_chars = 0
                for pdf_file in uploaded_pdf_list:
                    text = DocumentProcessor.extract_text_from_pdf(pdf_file)
                    all_text.append(text)
                    total_chars += len(text)
                
                # Concaténer tout le contenu du cours
                st.session_state.course_text_content = "\n\n--- NOUVEAU DOCUMENT ---\n\n".join(all_text)
                
                st.success(f"{len(uploaded_pdf_list)} PDF(s) chargé(s) ! ({total_chars} car.)")

        st.divider()

        # 2. Upload Image (GESTION MULTIPLE JUSQU'À 5)
        # 💡 Changement 2 : Utilisation de accept_multiple_files=True
        uploaded_image_list = st.file_uploader(
            "Schémas/Graphiques (pour analyse vision - Max. 5)", 
            type=["png", "jpg", "jpeg"], 
            key="img_uploader",
            accept_multiple_files=True # Permet de charger plusieurs images
        )
        
        # Logique de lecture des images
        # Nous allons stocker une liste d'URLs Base64 dans la session state
        st.session_state.image_base64_url = []
        if uploaded_image_list:
            
            # Limiter à 5 fichiers
            if len(uploaded_image_list) > 5:
                st.warning("Seuls les 5 premières images seront traitées.")
                uploaded_image_list = uploaded_image_list[:5]
                
            for img_file in uploaded_image_list:
                # Utiliser la fonction pour encoder chaque image
                base64_url = DocumentProcessor.convert_image_to_base64(img_file)
                if base64_url:
                    st.session_state.image_base64_url.append(base64_url)
                    st.image(img_file, width=150) # Affichage de l'aperçu dans la sidebar
            
            if st.session_state.image_base64_url:
                st.success(f"{len(st.session_state.image_base64_url)} image(s) prête(s) !")

    
    st.title("🐭 Maître Splinter - Tuteur IA")
    
    # --- LOGIQUE CONDITIONNELLE DU FLUX ---
    
    if current_state in ['start', 'questioning', 'final_review', 'finished']:
        tab_chat, tab_quiz = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
    else:
        # Afficher uniquement le tab quiz pendant la génération pour ne pas perdre le focus
        tab_chat, tab_quiz = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
        
    
    with tab_chat:
        st.header("Discours & Sagesse du Maître")
        
        # Afficher la sélection du modèle LLM ici pour le mode conversationnel
        st.session_state.selected_model = st.selectbox(
            "Modèle de Conversation", 
            options=LLM_MODELS,
            index=0,
            key='llm_select_chat'
        )
        
        # Afficher l'historique
        render_chat_history(agent)
        
        # Afficher le chat input (uniquement si le quiz n'est pas actif)
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
                
                # Assurez-vous que le sujet, nb questions et modèle sont passés correctement
                success = agent.generate_quiz(
                    topic=topic_input, 
                    n_questions=num_questions, 
                    model=model_id
                )
                
                if not success:
                    st.error("❌ Échec de la génération du quiz. Vérifiez le sujet ou le format JSON.")
                    quiz_manager.set_state('start')
                    
                st.rerun() # Passe à l'état 'questioning'

        elif current_state == 'questioning':
            render_questioning_interface(agent, quiz_manager)

        elif current_state == 'final_review':
            render_final_review_interface(agent, quiz_manager)

        elif current_state == 'finished':
            render_finished_interface(quiz_manager)


# --- EXÉCUTION DU PROGRAMME ---
if __name__ == "__main__":
    run_app()