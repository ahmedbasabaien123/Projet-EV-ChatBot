from flask import Flask, request, jsonify, make_response
import mysql.connector
from mysql.connector import errorcode
import uuid # pour générer des identifiants de session uniques
from fuzzywuzzy import fuzz
import unicodedata

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

def calculate_similarity(user_keywords, faq_keywords):
    user_keywords_str = " ".join(user_keywords)  # Convertir en chaîne
    faq_keywords_str = " ".join(faq_keywords)  # Convertir en chaîne
    return fuzz.token_set_ratio(user_keywords_str, faq_keywords_str) / 100.0

def generate_response(user_message):
    try:
        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor()

        # Séparer la question de l'utilisateur en mots-clés, supprimer les accents et filtrer les mots communs
        user_keywords = set(remove_accents(user_message.lower()).split()) - common_words
        print(f"User Keywords: {user_keywords}")  # Débogage

        # Récupérer toutes les questions fréquentes et leurs mots-clés
        cursor.execute("SELECT question, answer, keywords FROM faq")
        faqs = cursor.fetchall()

        # Recherche de correspondance exacte
        for faq in faqs:
            if faq[0].lower() == user_message.lower():
                return faq[1]

        # Recherche de correspondance des mots-clés
        best_match = None
        best_match_similarity = 0

        for faq in faqs:
            faq_keywords = set(remove_accents(faq[2].lower()).split(',')) if faq[2] else set()
            faq_keywords -= common_words
            print(f"FAQ Keywords for '{faq[0]}': {faq_keywords}")  # Débogage

            similarity = calculate_similarity(user_keywords, faq_keywords)
            print(f"Similarity for '{faq[0]}': {similarity}")  # Débogage

            # Ajouter une pondération pour les correspondances exactes
            if faq[0].lower() == user_message.lower():
                similarity += 0.5

            if similarity > best_match_similarity:
                best_match_similarity = similarity
                best_match = faq

        if best_match and best_match_similarity > 0.4:  # Seuil de similarité ajustable
            response = best_match[1]
            print(f"Best Match: {best_match[0]} with similarity {best_match_similarity}")  # Débogage
        else:
            # Réponses par défaut pour les messages généraux
            default_responses = {
                'bonjour': 'Bonjour ! Comment puis-je vous aider aujourd\'hui ?',
                'au revoir': 'Au revoir ! Passez une excellente journée !',
                'merci': 'De rien ! Je suis là pour vous aider.',
                'pardon': 'Pas de problème ! Comment puis-je vous aider ?',
                'comment ça va ?': 'Je suis juste un chatbot, mais merci de demander ! Comment puis-je vous aider aujourd\'hui ?'
            }
            user_message_lower = user_message.lower()
            response = default_responses.get(user_message_lower, "Excusez-moi, je ne suis pas sûr de cela. Veuillez nous contacter par 03 90 40 46 02 et nous serons heureux de vous aider.")
        
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