from flask import Flask, request, jsonify, make_response
from sentence_transformers import SentenceTransformer, util
import numpy as np
import mysql.connector
from mysql.connector import errorcode
import uuid # pour générer des identifiants de session uniques
from fuzzywuzzy import fuzz
import unicodedata
import re
import string
import spacy


model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

nlp = spacy.load("fr_core_news_sm")
common_words = set(["est", "la", "de", "le", "les", "et", "un", "une", "pour", "que", "en", "des"])

app = Flask(__name__)

# Configuration de la base de données
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'clinique_chatbot'


# Fonction pour obtenir une connexion à la base de données
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Erreur : Nom d'utilisateur ou mot de passe incorrect")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Erreur : La base de données n'existe pas")
        else:
            print(err)

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def normalize_text(text):
    text = remove_accents(text)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()  # Remove extra spaces and trim
    text = text.translate(str.maketrans('', '', string.punctuation))  # Remove punctuation
    return text

def generate_response(user_message):
    try:
        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor()

        # Normaliser la question de l'utilisateur
        normalized_user_message = normalize_text(user_message)
        print(f"Normalized User Message: {normalized_user_message}")  # Débogage

        # Encoder la question de l'utilisateur
        user_embedding = model.encode(normalized_user_message, convert_to_tensor=True)

        # Récupérer toutes les questions fréquentes et leurs réponses
        cursor.execute("SELECT question, answer FROM faq")
        faqs = cursor.fetchall()

        # Stocker les meilleures correspondances
        best_match = None
        best_match_score = -1

        for faq in faqs:
            normalized_faq_question = normalize_text(faq[0])
            faq_embedding = model.encode(normalized_faq_question, convert_to_tensor=True)
            score = util.pytorch_cos_sim(user_embedding, faq_embedding).item()
            print(f"Comparing with: {normalized_faq_question}, Score: {score}")  # Débogage

            if score > best_match_score:
                best_match_score = score
                best_match = faq

        # Définir un seuil de similarité pour accepter une correspondance
        similarity_threshold = 0.7  # Ajustez ce seuil selon vos besoins

        if best_match and best_match_score >= similarity_threshold:
            response = best_match[1]
            print(f"Best Match: {best_match[0]} with score {best_match_score}")  # Débogage
        else:
            # Réponses par défaut pour les messages généraux
            default_responses = {
                'bonjour': 'Bonjour ! Comment puis-je vous aider aujourd\'hui ?',
                'au revoir': 'Au revoir ! Passez une excellente journée !',
                'merci': 'De rien ! Je suis là pour vous aider.',
                'pardon': 'Pas de problème ! Comment puis-je vous aider ?',
                'comment ça va': 'Je suis juste un chatbot, mais merci de demander ! Comment puis-je vous aider aujourd\'hui ?',
                'ça va': 'Je suis juste un chatbot, mais merci de demander ! Comment puis-je vous aider aujourd\'hui ?'
            }
            response = default_responses.get(normalized_user_message, "N'étant pas en mesure de répondre à cette question, je peux vous proposer de contacter l'équipe EXCEL Vision au 0800 200 388")
        
        return response
    except Exception as e:
        print(f"Erreur dans generate_response: {e}")
        return "Désolé, une erreur est survenue. Veuillez réessayer plus tard."
    finally:
        cursor.close()
        conn.close()


@app.route('/')
def home():
    return "Bienvenue sur le chatbot d'EXCEL Vision !"

@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            
        user_message = request.json['message']
        response = generate_response(user_message)

        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insertion des données dans la base de données
        cursor.execute("INSERT INTO messages (session_id, user_message, bot_response) VALUES (%s, %s, %s)",
                    (session_id, user_message, response))
        conn.commit()
        
        resp = make_response(jsonify({"response": response}))
        resp.set_cookie('session_id', session_id)
        return resp
    except Exception as e:
        print(f"Erreur dans send_message: {e}")
        return jsonify({"response": "Désolé, une erreur est survenue. Veuillez réessayer plus tard."})
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)