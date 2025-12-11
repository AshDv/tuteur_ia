import streamlit as st
# Importation de tes nouveaux modules locaux
from utils import DocumentProcessor
from backend import SplinterBrain
from session import SessionManager

class SplinterApp:
    """Classe principale gérant l'affichage Streamlit."""

    def __init__(self):
        st.set_page_config(page_title="Splinter - Tuteur IA", page_icon="🐭", layout="wide")
        self.brain = SplinterBrain()
        self.session_manager = SessionManager()
        self.session_manager.initialize_state()
        
        # Variables pour stocker les fichiers chargés
        self.course_text_content = ""
        self.image_base64_url = None

    def render_sidebar(self):
        """Affiche la barre latérale pour l'upload de fichiers."""
        with st.sidebar:
            st.image("https://img.icons8.com/dusk/64/000000/rat.png")
            st.title("📚 Tes Documents")
            
            # 1. Gestion PDF
            uploaded_pdf = st.file_uploader("Fichier PDF (Cours)", type="pdf", key="pdf_uploader")
            if uploaded_pdf:
                with st.spinner("Analyse du PDF..."):
                    self.course_text_content = DocumentProcessor.extract_text_from_pdf(uploaded_pdf)
                    st.success(f"PDF chargé ! ({len(self.course_text_content)} car.)")

            st.divider()

            # 2. Gestion Image
            st.title("🖼️ Image à analyser")
            uploaded_image = st.file_uploader("Schéma/Graphique", type=["png", "jpg", "jpeg"], key="img_uploader")
            if uploaded_image:
                st.image(uploaded_image, caption="Aperçu", use_container_width=True)
                self.image_base64_url = DocumentProcessor.convert_image_to_base64(uploaded_image)
                if self.image_base64_url:
                    st.success("Image prête !")

    def render_chat_tab(self):
        """Gère l'affichage et la logique de l'onglet Discussion."""
        chat_container = st.container()

        # Zone d'affichage des messages
        with chat_container:
            # Bouton contextuel
            if self.course_text_content and st.button("📑 Résumer ce cours"):
                self.session_manager.add_message("user", "Résume ce cours en détail.")
                st.rerun()

            # Affichage historique
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Zone de saisie utilisateur
        if user_input := st.chat_input("Pose ta question à Splinter..."):
            self.session_manager.add_message("user", user_input)
            
            # Génération réponse
            with st.spinner("Splinter réfléchit..."):
                ai_response = self.brain.generate_chat_response(
                    st.session_state.messages,
                    context_text=self.course_text_content,
                    image_url=self.image_base64_url
                )
            
            self.session_manager.add_message("assistant", ai_response)
            st.rerun()

    def render_quiz_tab(self):
        """Gère l'affichage et la logique de l'onglet Quiz."""
        st.header("📝 Mode Évaluation")
        
        # Configuration du Quiz
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            default_sujet = "Le cours ci-joint" if self.course_text_content else ""
            topic = st.text_input("Sujet", value=default_sujet, placeholder="Ex: La Révolution Française")
        with c2:
            difficulty = st.selectbox("Niveau", ["Débutant", "Moyen", "Expert"])
        with c3:
            num_questions = st.slider("Nb Questions", 1, 20, 5)

        # Action : Générer le quiz
        if st.button("🚀 Générer l'évaluation") and topic:
            with st.spinner("Création du questionnaire..."):
                quiz_data = self.brain.generate_quiz_json(
                    topic, difficulty, num_questions, self.course_text_content
                )
                if quiz_data:
                    st.session_state.current_quiz = quiz_data
                    self.session_manager.clear_quiz_state()
                    st.rerun()

        # Action : Afficher et Corriger le quiz
        if st.session_state.current_quiz:
            self._display_quiz_form()

    def _display_quiz_form(self):
        """Méthode privée pour afficher le formulaire de questions."""
        quiz = st.session_state.current_quiz
        st.info(f"Quiz généré : {len(quiz['questions'])} questions.")

        with st.form("quiz_form"):
            for i, q in enumerate(quiz["questions"]):
                st.markdown(f"**Q{i+1} :** {q['question']}")
                st.radio("Réponse", q["options"], key=f"q_{i}", index=None, label_visibility="collapsed")
                st.write("---")
            
            if st.form_submit_button("Valider mes réponses"):
                st.session_state.quiz_submitted = True
                st.rerun()

        if st.session_state.quiz_submitted:
            self._calculate_and_show_score(quiz)

    def _calculate_and_show_score(self, quiz_data):
        """Calcule le score et affiche les corrections."""
        score = 0
        total = len(quiz_data["questions"])
        
        st.divider()
        st.subheader("📊 Résultats")
        
        for i, question in enumerate(quiz_data["questions"]):
            user_choice = st.session_state.get(f"q_{i}")
            correct_answer = question["correct_answer"]
            
            if user_choice == correct_answer:
                score += 1
                st.success(f"✅ Question {i+1} : Correct !")
            else:
                st.error(f"❌ Question {i+1} : Faux (Votre choix : {user_choice})")
                st.markdown(f"👉 **Bonne réponse :** {correct_answer}")
                st.caption(f"💡 *Explication : {question['explanation']}*")

        final_note = (score / total) * 20
        st.markdown(f"### 🏆 Note Finale : {score}/{total} ({final_note:.1f}/20)")

    def run(self):
        """Point d'entrée principal de l'application."""
        self.render_sidebar()
        
        st.title("🐭 Splinter - Tuteur IA")
        
        tab_chat, tab_quiz = st.tabs(["💬 Discussion & Vision", "📝 Quiz Dynamique"])
        
        with tab_chat:
            self.render_chat_tab()
        
        with tab_quiz:
            self.render_quiz_tab()

# --- EXÉCUTION DU PROGRAMME ---
if __name__ == "__main__":
    app = SplinterApp()
    app.run()