import streamlit as st
from groq import Groq
from dotenv import load_dotenv
import os
import json
import PyPDF2

# --- FONCTIONS UTILITAIRES ---
def extract_text_from_pdf(pdf_file):
    """Extrait le texte brut d'un fichier PDF uploadé"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text
    except Exception as e:
        return f"Erreur de lecture PDF : {e}"

# --- BACKEND : Le Cerveau de Splinter ---
class ConversationAgent:
    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GROQ_KEY")
        if not api_key:
            st.error("Clé API introuvable. Vérifie ton fichier .env")
            st.stop()
        self.client = Groq(api_key=api_key)

    def generate_response(self, messages, context_text=None):
        if context_text:
            system_message_content = (
                "Tu es Splinter, un tuteur pédagogue. "
                "Utilise le cours fourni ci-dessous pour répondre. "
                "Si la réponse n'est pas dans le cours, utilise tes connaissances.\n\n"
                f"--- COURS ---\n{context_text[:25000]}"
            )
            messages_with_context = [{"role": "system", "content": system_message_content}] + messages
        else:
            messages_with_context = messages

        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages_with_context,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2048,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            return f"Erreur : {e}"

    def generate_quiz(self, topic, difficulty, num_questions, context_text=None):
        """
        Génère un quiz avec un nombre CIBLE de questions.
        """
        context_instruction = ""
        if context_text:
            context_instruction = f"Base tes questions EXCLUSIVEMENT sur le cours suivant :\n{context_text[:20000]}"
        
        prompt = f"""
        Tu es un professeur expert qui crée un examen.
        Sujet : "{topic}".
        Niveau : {difficulty}.
        Objectif : Générer EXACTEMENT {num_questions} questions.
        
        {context_instruction}
        
        INSTRUCTIONS STRICTES :
        1. Tu DOIS générer {num_questions} questions. Pas moins.
        2. Si le texte est court, interroge sur des détails, des définitions, ou des exemples pour atteindre le chiffre {num_questions}.
        3. Varie le type de questions pour ne pas être répétitif, mais respecte le compte.
        
        Réponds UNIQUEMENT avec un JSON valide au format suivant :
        {{
            "questions": [
                {{
                    "question": "...",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": "...",
                    "explanation": "..."
                }}
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.5, # Temperature basse pour respecter les consignes
                max_tokens=4096, 
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"Erreur génération quiz : {e}")
            return None

# --- FRONTEND : L'interface Streamlit ---
st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")

# -- SIDEBAR --
with st.sidebar:
    st.image("https://img.icons8.com/dusk/64/000000/rat.png")
    st.title("📚 Tes Cours")
    uploaded_file = st.file_uploader("Fichier PDF", type="pdf")
    
    course_content = ""
    if uploaded_file is not None:
        with st.spinner("Analyse du document..."):
            course_content = extract_text_from_pdf(uploaded_file)
            st.success(f"Cours chargé ! ({len(course_content)} caractères)")

st.title("🐭 Splinter - Tuteur IA")

tab1, tab2 = st.tabs(["💬 Discussion", "📝 Quiz Dynamique"])

# --- ONGLET 1 : CHAT ---
with tab1:
    chat_container = st.container()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    with chat_container:
        if course_content and st.button("📑 Résumer ce cours"):
            st.session_state.messages.append({"role": "user", "content": "Résume ce cours en détail."})
            st.rerun()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Pose ta question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        agent = ConversationAgent()
        response = agent.generate_response(st.session_state.messages, context_text=course_content)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# --- ONGLET 2 : QUIZ ---
with tab2:
    st.header("Mode Évaluation")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        default_topic = "Le cours complet ci-joint" if course_content else ""
        topic = st.text_input("Sujet à évaluer", value=default_topic)
    
    with col2:
        difficulty = st.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])
        
    with col3:
        # Changement du libellé pour refléter l'ordre strict
        num_questions = st.slider("Nombre de questions", min_value=1, max_value=20, value=5)

    if st.button("Générer l'évaluation") and topic:
        agent = ConversationAgent()
        with st.spinner(f"Génération de {num_questions} questions en cours..."):
            
            quiz_data = agent.generate_quiz(topic, difficulty, num_questions, context_text=course_content)
            
            if quiz_data:
                st.session_state.current_quiz = quiz_data
                st.session_state.user_answers = {} 
                st.session_state.quiz_submitted = False
                st.rerun()

    if "current_quiz" in st.session_state:
        quiz = st.session_state.current_quiz
        nb_questions_generated = len(quiz["questions"])
        
        # Petit message pour confirmer si l'IA a obéi
        if nb_questions_generated < num_questions:
            st.warning(f"L'IA n'a trouvé assez de matière que pour {nb_questions_generated} questions sur les {num_questions} demandées.")
        else:
            st.success(f"Quiz de {nb_questions_generated} questions généré !")

        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Question {i+1} :** {q['question']}")
                st.radio("Votre réponse :", q["options"], key=f"q_{i}", index=None, label_visibility="collapsed")
                st.write("---")
            
            if st.form_submit_button("Valider mes réponses"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.get("quiz_submitted"):
            st.divider()
            score = 0
            for i, q in enumerate(quiz["questions"]):
                user_choice = st.session_state.get(f"q_{i}")
                if user_choice == q["correct_answer"]:
                    score += 1
                    st.success(f"✅ Q{i+1} : Correct")
                else:
                    st.error(f"❌ Q{i+1} : Faux (Votre choix : {user_choice})")
                    st.markdown(f"👉 **Bonne réponse :** {q['correct_answer']}")
                    st.caption(f"💡 *Explication : {q['explanation']}*")
            
            final_score = (score / nb_questions_generated) * 20
            st.markdown(f"### 🏆 Note finale : {score}/{nb_questions_generated} ({final_score:.1f}/20)")