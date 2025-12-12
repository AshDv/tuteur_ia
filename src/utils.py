import streamlit as st
import PyPDF2
import base64
import re
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

class DocumentProcessor:
    """Gère l'extraction de texte et l'encodage d'images."""

    @staticmethod
    def extract_text_from_pdf(pdf_file) -> str:
        """Lit un fichier PDF et retourne son contenu textuel."""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_content = ""
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text_content += extracted_text + "\n"
            return text_content
        except Exception as e:
            st.error(f"Erreur lors de la lecture du PDF : {e}")
            return ""

    @staticmethod
    def convert_image_to_base64(image_file) -> str | None:
        """Convertit une image uploadée en chaîne Base64 pour l'API."""
        if image_file is None:
            return None
        try:
            image_file.seek(0)
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return f"data:{image_file.type};base64,{encoded_string}"
        except Exception as e:
            st.error(f"Erreur d'encodage de l'image : {e}")
            return None

class YouTubeProcessor:
    """Gère l'extraction de transcriptions YouTube."""

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """Extrait l'ID de la vidéo depuis différents formats d'URL YouTube."""
        # Patterns pour youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
        regex_patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
            r"(?:embed\/)([0-9A-Za-z_-]{11})"
        ]
        
        for pattern in regex_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def get_transcript_text(video_id: str) -> str | None:
        """Récupère la transcription en français ou anglais."""
        try:
            # On essaie de récupérer en priorité le français, sinon l'anglais
            # 'fr' = français manuel, 'fr-FR' = français local, 'en' = anglais
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['fr', 'fr-FR', 'en', 'en-US', 'en-GB'])
            
            # Concaténation du texte
            full_text = " ".join([item['text'] for item in transcript_list])
            return full_text
            
        except NoTranscriptFound:
            st.error("Aucune transcription trouvée pour cette vidéo (ni FR ni EN).")
            return None
        except TranscriptsDisabled:
            st.error("Les sous-titres sont désactivés sur cette vidéo.")
            return None
        except Exception as e:
            st.error(f"Erreur lors de la récupération YouTube : {e}")
            return None