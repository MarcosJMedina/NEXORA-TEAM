// Abre y cierra la ventana del chat
function toggleChat() {
    const chatWindow = document.getElementById('chat-window');
    chatWindow.classList.toggle('hidden');
}

// Captura si el usuario presiona "Enter" en el teclado
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Envía el mensaje del estudiante
function sendMessage() {
    const input = document.getElementById('user-input');
    const messageText = input.value.trim();
    
    if (messageText === '') return;

    const messagesContainer = document.getElementById('chat-messages');

    // 1. Pintar el mensaje del usuario en pantalla
    const userDiv = document.createElement('div');
    userDiv.className = 'message user-message';
    userDiv.innerText = messageText;
    messagesContainer.appendChild(userDiv);

    input.value = '';
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // 2. Pintar indicador de carga ("escribiendo...")
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typing-loader';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // 3. CONEXIÓN CON EL BACKEND EN PYTHON (FASTAPI)
    fetch('http://127.0.0.1:3000/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: 4501,         // ID simulado (en Moodle vendrá de PHP)
            course_id: 102,        // ID simulado
            message: messageText   // El texto real que escribiste
        })
    })
    .then(res => res.json())
    .then(data => {
        // Remover indicador de carga
        const loader = document.getElementById('typing-loader');
        if (loader) loader.remove();

        // 4. Pintar la respuesta real que devolvió el servidor en Python
        const botDiv = document.createElement('div');
        botDiv.className = 'message bot-message';
        botDiv.innerText = data.response; 
        
        messagesContainer.appendChild(botDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    })
    .catch(error => {
        console.error("Error conectando al backend:", error);
        const loader = document.getElementById('typing-loader');
        if (loader) loader.remove();
        
        // Mensaje de contingencia si el servidor de Python se apaga
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message bot-message';
        errorDiv.style.color = 'red';
        errorDiv.innerText = "Error: No se pudo conectar con el servidor backend en Python.";
        messagesContainer.appendChild(errorDiv);
    });
}