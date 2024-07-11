from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from sentence_transformers import SentenceTransformer, util
import numpy as np
import mysql.connector
from mysql.connector import errorcode
import uuid  # pour générer des identifiants de session uniques
import unicodedata
import re
import string
import spacy
from flask_caching import Cache

# Configuration du cache
config = {
    "CACHE_TYPE": "redis",
    "CACHE_REDIS_HOST": "localhost",
    "CACHE_REDIS_PORT": 6379,
    "CACHE_REDIS_DB": 0,
    "CACHE_REDIS_URL": "redis://localhost:6379/0",
    "CACHE_DEFAULT_TIMEOUT": 300  # Temps de cache par défaut en secondes
}

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

nlp = spacy.load("fr_core_news_sm")
common_words = set(["est", "la", "de", "le", "les", "et", "un", "une", "pour", "que", "en", "des"])

app = Flask(__name__)
CORS(app)  # Ajout de cette ligne pour activer CORS
app.config.from_mapping(config)
cache = Cache(app)

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

def replace_pronouns(text):
    replacements = {
        "vous": "EXCEL Vision",
        "tu": "EXCEL Vision",
        "votre": "EXCEL Vision",
        "ton": "EXCEL Vision",
        "tes": "EXCEL Vision",
        "tes": "EXCEL Vision"
    }
    text = text.lower()
    for pronoun, replacement in replacements.items():
        text = re.sub(rf'\b{pronoun}\b', replacement, text)
    return text

def normalize_text(text):
    text = replace_pronouns(text)
    text = remove_accents(text)
    doc = nlp(text.lower())
    normalized_tokens = [token.lemma_ for token in doc if not token.is_stop]
    return " ".join(normalized_tokens)

# Charger les questions et leurs embeddings au démarrage de l'application
faq_data = []

def load_faq_data():
    global faq_data
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer FROM faq")
    faqs = cursor.fetchall()
    for faq in faqs:
        normalized_question = normalize_text(faq[0])
        question_embedding = model.encode(normalized_question, convert_to_tensor=True)
        faq_data.append((faq[0], faq[1], question_embedding))
    cursor.close()
    conn.close()

# Appeler cette fonction au démarrage de l'application
load_faq_data()

@cache.memoize()
def cached_generate_response(normalized_user_message):
    user_embedding = model.encode(normalized_user_message, convert_to_tensor=True)

    best_match = None
    best_match_score = -1

    for faq_question, faq_answer, faq_embedding in faq_data:
        score = util.pytorch_cos_sim(user_embedding, faq_embedding).item()
        if score > best_match_score:
            best_match_score = score
            best_match = (faq_question, faq_answer)

    similarity_threshold = 0.7  # Ajustez ce seuil selon vos besoins

    if best_match and best_match_score >= similarity_threshold:
        return best_match[1]
    else:
        default_responses = {
            'bonjour': 'Bonjour ! Comment puis-je vous aider aujourd\'hui ?',
            'au revoir': 'Au revoir ! Passez une excellente journée !',
            'merci': 'De rien ! Je suis là pour vous aider.',
            'pardon': 'Pas de problème ! Comment puis-je vous aider ?',
            'comment ça va': 'Je suis juste un chatbot, mais merci de demander ! Comment puis-je vous aider aujourd\'hui ?',
            'ça va': 'Je suis juste un chatbot, mais merci de demander ! Comment puis-je vous aider aujourd\'hui ?'
        }
        return default_responses.get(normalized_user_message, "N'étant pas en mesure de répondre à cette question, je peux vous proposer de contacter l'équipe EXCEL Vision au 0800 200 388.")

def generate_response(user_message):
    try:
        normalized_user_message = normalize_text(user_message)
        response = cached_generate_response(normalized_user_message)
        return response
    except Exception as e:
        print(f"Erreur dans generate_response: {e}")
        return "Désolé, une erreur est survenue. Veuillez réessayer plus tard."

@app.route('/')
def home():
    return "Bienvenue sur le chatbot d'EXCEL Vision !"

@app.route('/send_message', methods=['POST'])
def send_message():
    conn = None
    cursor = None
    try:
        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            
        user_message = request.json['message']
        response = generate_response(user_message)

        conn = get_db_connection()
        cursor = conn.cursor()
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Assurez-vous que le port est 5000

