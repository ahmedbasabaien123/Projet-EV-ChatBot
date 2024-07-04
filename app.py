from flask import Flask, request, jsonify, make_response
import mysql.connector
from mysql.connector import errorcode
import uuid # pour générer des identifiants de session uniques

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

# Fonction pour générer une réponse basée sur le message de l'utilisateur
def generate_response(user_message):
    try:
        # Connexion à la base de données
        conn = get_db_connection()
        cursor = conn.cursor()

        # Vérifier si la question existe dans les questions fréquentes
        cursor.execute("SELECT answer FROM faq WHERE question LIKE %s", (f"%{user_message}%",))
        result = cursor.fetchone()
        
        # Lire tous les résultats pour éviter "Unread result found"
        while cursor.nextset():
            cursor.fetchall()

        if result:
            response = result[0]
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