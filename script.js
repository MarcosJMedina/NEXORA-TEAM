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

    // 3. DETECCIÓN ROBUSTA DE USUARIO (USER ID)
    function detectarUserId() {
        if (typeof M !== 'undefined' && M.cfg && M.cfg.userid && parseInt(M.cfg.userid) > 0) {
            return parseInt(M.cfg.userid);
        }
        const userMenu = document.querySelector('[data-userid]');
        if (userMenu && userMenu.getAttribute('data-userid')) {
            const uid = parseInt(userMenu.getAttribute('data-userid'));
            if (uid > 0) return uid;
        }
        const profileLink = document.querySelector('.userbutton a[href*="/user/"], a.dropdown-item[href*="/user/profile.php?id="], a[href*="/user/view.php?id="]');
        if (profileLink) {
            const matchUser = profileLink.href.match(/[?&]id=(\d+)/);
            if (matchUser && parseInt(matchUser[1]) > 0) {
                return parseInt(matchUser[1]);
            }
        }
        return 0;
    }

    // 4. DETECCIÓN ROBUSTA DE MATERIA (COURSE ID)
    // NOTA TÉCNICA: Jamás usar M.cfg.courseId porque Moodle le asigna 1 globalmente en la cabecera.
    function detectarCourseId() {
        const urlParams = new URLSearchParams(window.location.search);
        const idFromUrl = urlParams.get('id');
        const courseParam = urlParams.get('course') || urlParams.get('courseid');

        // Prioridad 1: Vista directa del curso (/course/view.php?id=X) o pantalla de matriculación (/enrol/index.php?id=X)
        if (idFromUrl && !isNaN(idFromUrl) && parseInt(idFromUrl) > 0 && 
            (window.location.pathname.includes('/course/') || window.location.pathname.includes('/enrol/'))) {
            return parseInt(idFromUrl);
        }

        // Prioridad 2: Si estamos dentro de una tarea, foro o recurso (?course=X)
        if (courseParam && !isNaN(courseParam) && parseInt(courseParam) > 0) {
            return parseInt(courseParam);
        }

        // Prioridad 3: Atributo data-course-id del contenedor de página en Moodle Boost/Classic
        const pageEl = document.getElementById('page') || document.querySelector('[data-course-id]');
        if (pageEl && pageEl.getAttribute('data-course-id')) {
            const pid = parseInt(pageEl.getAttribute('data-course-id'));
            if (pid > 0) return pid;
        }

        // Prioridad 4: Breadcrumbs de navegación con enlace al curso
        const breadcrumbLinks = document.querySelectorAll('.breadcrumb a[href*="/course/view.php?id="], #page-navbar a[href*="/course/view.php?id="], nav a[href*="/course/view.php?id="]');
        if (breadcrumbLinks.length > 0) {
            const ultimoLink = breadcrumbLinks[breadcrumbLinks.length - 1];
            const matchBread = ultimoLink.href.match(/[?&]id=(\d+)/);
            if (matchBread && parseInt(matchBread[1]) > 0) {
                return parseInt(matchBread[1]);
            }
        }

        // Prioridad 5: Clases en body buscando IDs de materias reales (> 1)
        if (document.body && document.body.className) {
            const bodyMatches = document.body.className.match(/\bcourse-(\d+)\b/g);
            if (bodyMatches) {
                for (let c of bodyMatches) {
                    let num = parseInt(c.replace('course-', ''));
                    if (num > 1) return num;
                }
            }
        }

        // Prioridad 6: Si no se detecta curso específico, se asume la Portada/Dashboard (1)
        return 1;
    }

    const userId = detectarUserId();
    const courseId = detectarCourseId();

    console.log(`📡 [CHATBOT MOODLE] Usuario autenticado: ${userId} | Materia detectada: ${courseId} | URL: ${window.location.pathname}${window.location.search}`);

    fetch('http://127.0.0.1:3000/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: userId,
            course_id: courseId,
            message: messageText
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