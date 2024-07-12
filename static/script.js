function appendMessage(message, sender) {
    const chatContainer = document.getElementById('chatBox');
    const messageElement = document.createElement('div');
    const messageContent = document.createElement('div');

    messageElement.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
    messageContent.classList.add('message-content');
    messageContent.textContent = message;

    if (sender === 'bot') {
        const logoContainer = document.createElement('div');
        logoContainer.classList.add('logo-container');

        const logo = document.createElement('img');
        logo.src = '/imgs/logo.png'; // Remplacez par le chemin réel de votre logo
        logoContainer.appendChild(logo);

        const statusIndicator = document.createElement('div');
        statusIndicator.classList.add('status-indicator');
        logoContainer.appendChild(statusIndicator);

        messageElement.appendChild(logoContainer);
    }

    messageElement.appendChild(messageContent);
    chatContainer.appendChild(messageElement);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function sendMessage() {
    const userInput = document.getElementById('userInput');
    const message = userInput.value.trim();
    if (message === '') return;
    appendMessage(message, 'user');
    userInput.value = '';

    const typingIndicator = document.getElementById('typingIndicator');
    typingIndicator.style.display = 'flex';

    try {
        const response = await fetch('http://127.0.0.1:5000/send_message', {  // Assurez-vous que le port est 5000
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        typingIndicator.style.display = 'none';
        appendMessage(data.response, 'bot');
    } catch (error) {
        typingIndicator.style.display = 'none';
        appendMessage('Désolé, une erreur est survenue. Veuillez réessayer plus tard.', 'bot');
        console.error('Error:', error);
    }
}

// Attacher l'événement à l'élément du bouton
document.addEventListener('DOMContentLoaded', function () {
    const sendButton = document.querySelector('button');
    sendButton.addEventListener('click', sendMessage);

    // Optionnel : Permettre l'envoi en appuyant sur la touche "Entrée"
    const userInput = document.getElementById('userInput');
    userInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});
