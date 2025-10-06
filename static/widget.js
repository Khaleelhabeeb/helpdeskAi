(function () {
    const agentId = document.currentScript.getAttribute("data-agent-id");
    const displayName = document.currentScript.getAttribute("display-name") || "Chat Assistant";
    let mainColor = document.currentScript.getAttribute("main-color") || "#4a6cf7";

    // Function to convert color names to hex
    function convertNamedColorToHex(color) {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = color;
        return ctx.fillStyle;
    }

    // Convert color name to hex if needed
    if (!/^#[0-9A-Fa-f]{6}$/i.test(mainColor)) {
        mainColor = convertNamedColorToHex(mainColor);
    }

    // Function to determine if a color is light or dark
    function isLightColor(color) {
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        const brightness = ((r * 299) + (g * 587) + (b * 114)) / 1000;
        return brightness > 128;
    }

    // Determine text color based on background color
    const headerTextColor = isLightColor(mainColor) ? '#000000' : '#ffffff';

    // Function to format text with markdown-style formatting
    function formatMessageText(text) {
        // Convert **text** to bold
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Convert line breaks and dashes to proper formatting
        // Split by " - " and create line breaks before each item
        text = text.replace(/\s*-\s*\*\*/g, '<br><br><strong>');
        
        // Handle remaining ** patterns that might be at the start
        text = text.replace(/^\*\*/g, '<strong>');
        text = text.replace(/\*\*$/g, '</strong>');
        
        // Convert regular line breaks to HTML line breaks
        text = text.replace(/\n/g, '<br>');
        
        return text;
    }

    // Chat history functions
    function saveChatHistory() {
        try {
            const messages = [];
            const messageElements = chatMessages.querySelectorAll('.chat-message');
            
            messageElements.forEach(element => {
                const isUser = element.classList.contains('user-message');
                messages.push({
                    type: isUser ? 'user' : 'bot',
                    content: isUser ? element.textContent : element.innerHTML,
                    timestamp: Date.now()
                });
            });
            
            const storageKey = `chat-history-${agentId || 'default'}`;
            localStorage.setItem(storageKey, JSON.stringify(messages));
            console.log('Chat history saved:', messages.length, 'messages');
        } catch (error) {
            console.error('Error saving chat history:', error);
        }
    }
    
    function loadChatHistory() {
        try {
            const storageKey = `chat-history-${agentId || 'default'}`;
            const stored = localStorage.getItem(storageKey);
            
            if (stored) {
                const messages = JSON.parse(stored);
                console.log('Loading chat history:', messages.length, 'messages');
                
                // Clear existing messages
                chatMessages.innerHTML = '';
                
                if (messages.length === 0) {
                    showWelcomeMessage();
                    return;
                }
                
                messages.forEach(message => {
                    const messageElement = document.createElement("div");
                    messageElement.className = `chat-message ${message.type}-message`;
                    
                    if (message.type === 'user') {
                        messageElement.textContent = message.content;
                    } else {
                        messageElement.innerHTML = message.content;
                    }
                    
                    chatMessages.appendChild(messageElement);
                });
                
                // Scroll to bottom
                setTimeout(() => {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }, 100);
            } else {
                console.log('No chat history found, showing welcome message');
                showWelcomeMessage();
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
            showWelcomeMessage();
        }
    }

    function showWelcomeMessage() {
        chatMessages.innerHTML = '';
        const welcomeMessage = document.createElement("div");
        welcomeMessage.className = "chat-message bot-message";
        welcomeMessage.textContent = "Hi there! How can I help you today?";
        chatMessages.appendChild(welcomeMessage);
    }

    function clearChatHistory() {
        try {
            const storageKey = `chat-history-${agentId || 'default'}`;
            localStorage.removeItem(storageKey);
            showWelcomeMessage();
            console.log('Chat history cleared');
        } catch (error) {
            console.error('Error clearing chat history:', error);
        }
    }

    // Create styles
    const style = document.createElement("style");
    style.textContent = `
        .chat-widget-button {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background-color: ${mainColor};
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            z-index: 9999;
        }

        .chat-widget-button:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
        }

        .chat-widget-button svg {
            width: 28px;
            height: 28px;
            fill: white;
        }

        .chat-widget-button-drag {
            position: absolute;
            top: -5px;
            right: -5px;
            width: 15px;
            height: 15px;
            background-color: ${mainColor};
            border: 2px solid white;
            border-radius: 50%;
            cursor: move;
        }

        .chat-widget-container {
            position: fixed;
            width: 350px;
            height: 500px;
            border-radius: 16px;
            background-color: #ffffff;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            z-index: 9998;
            transition: all 0.3s ease;
        }

        .chat-widget-header {
            background: linear-gradient(135deg, ${mainColor}, ${mainColor}dd);
            color: ${headerTextColor};
            padding: 16px;
            font-family: 'Arial', sans-serif;
            font-size: 16px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: move;
        }

        .chat-widget-close {
            cursor: pointer;
            background: transparent;
            border: none;
            color: ${headerTextColor};
            font-size: 18px;
        }

        .chat-widget-clear {
            cursor: pointer;
            background: transparent;
            border: none;
            color: ${headerTextColor};
            font-size: 12px;
            margin-right: 10px;
            opacity: 0.8;
        }

        .chat-widget-clear:hover {
            opacity: 1;
        }

        .chat-widget-messages {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            background-color: #f8f9fb;
        }

        .chat-message {
            margin-bottom: 12px;
            max-width: 80%;
            padding: 10px 14px;
            border-radius: 16px;
            font-family: 'Arial', sans-serif;
            font-size: 14px;
            line-height: 1.4;
        }

        .user-message {
            background-color: ${mainColor};
            color: white;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }

        .bot-message {
            background-color: #e9ecef;
            color: #343a40;
            margin-right: auto;
            border-bottom-left-radius: 4px;
        }

        .bot-message strong {
            font-weight: bold;
            color: ${mainColor};
        }

        .chat-widget-input-area {
            padding: 12px 16px;
            background-color: #ffffff;
            border-top: 1px solid #e9ecef;
            display: flex;
            align-items: center;
        }

        .chat-widget-input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #e9ecef;
            border-radius: 24px;
            font-family: 'Arial', sans-serif;
            font-size: 14px;
            outline: none;
            transition: border 0.3s ease;
        }

        .chat-widget-input:focus {
            border-color: ${mainColor};
        }

        .chat-widget-send {
            background-color: ${mainColor};
            color: white;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            margin-left: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }

        .chat-widget-send:hover {
            background-color: ${mainColor}dd;
        }

        .chat-widget-send svg {
            width: 18px;
            height: 18px;
            fill: white;
        }
    `;
    document.head.appendChild(style);

    // Create chat button with bot icon
    const chatButton = document.createElement("button");
    chatButton.className = "chat-widget-button";
    chatButton.innerHTML = `
        <svg width="24px" height="24px" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M21.928 11.607c-.202-.488-.635-.605-.928-.633V8c0-1.103-.897-2-2-2h-6V4.61c.305-.274.5-.668.5-1.11a1.5 1.5 0 0 0-3 0c0 .442.195.836.5 1.11V6H5c-1.103 0-2 .897-2 2v2.997l-.082.006A1 1 0 0 0 1.99 12v2a1 1 0 0 0 1 1H3v5c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2v-5a1 1 0 0 0 1-1v-1.938a1.006 1.006 0 0 0-.072-.455zM5 20V8h14l.001 3.996L19 12v2l.001.005.001 5.995H5z"/><ellipse cx="8.5" cy="12" rx="1.5" ry="2"/><ellipse cx="15.5" cy="12" rx="1.5" ry="2"/><path d="M8 16h8v2H8z"/></svg>
    `;
    document.body.appendChild(chatButton);

    // Add a drag handle to the button
    const buttonDragHandle = document.createElement("div");
    buttonDragHandle.className = "chat-widget-button-drag";
    chatButton.appendChild(buttonDragHandle);

    // Create chat container (hidden initially)
    const chatContainer = document.createElement("div");
    chatContainer.className = "chat-widget-container";
    chatContainer.style.display = "none";
    document.body.appendChild(chatContainer);

    // Create chat header with drag functionality
    const chatHeader = document.createElement("div");
    chatHeader.className = "chat-widget-header";
    chatHeader.innerHTML = `
        <div>${displayName}</div>
        <div>
            <button class="chat-widget-clear" title="Clear Chat">Clear</button>
            <button class="chat-widget-close">&times;</button>
        </div>
    `;
    chatContainer.appendChild(chatHeader);

    // Message area
    const chatMessages = document.createElement("div");
    chatMessages.className = "chat-widget-messages";
    chatContainer.appendChild(chatMessages);

    // Load chat history when the widget is created
    loadChatHistory();

    // Input area
    const inputArea = document.createElement("div");
    inputArea.className = "chat-widget-input-area";
    chatContainer.appendChild(inputArea);

    const input = document.createElement("input");
    input.type = "text";
    input.className = "chat-widget-input";
    input.placeholder = "Type your message...";
    inputArea.appendChild(input);

    const sendButton = document.createElement("button");
    sendButton.className = "chat-widget-send";
    sendButton.innerHTML = `
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
        </svg>
    `;
    inputArea.appendChild(sendButton);

    // Function to ensure an element is within viewport
    function ensureInViewport(element, offsetFromButton) {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const elementWidth = element.offsetWidth;
        const elementHeight = element.offsetHeight;

        // Get the button's position
        const buttonRect = chatButton.getBoundingClientRect();

        // Calculate ideal position (default is above the button)
        let idealLeft = buttonRect.left + (buttonRect.width / 2) - (elementWidth / 2);
        let idealTop = buttonRect.top - elementHeight - 10; // 10px gap

        // Check if we should place it below instead of above
        if (idealTop < 0) {
            idealTop = buttonRect.bottom + 10; // 10px gap below the button
        }

        // Check if we should place it to the side instead
        if (idealTop + elementHeight > viewportHeight) {
            // Try placing it to the left of the button
            if (buttonRect.left > elementWidth + 10) {
                idealLeft = buttonRect.left - elementWidth - 10;
                idealTop = buttonRect.top;
            }
            // Or to the right if there's space
            else if (viewportWidth - buttonRect.right > elementWidth + 10) {
                idealLeft = buttonRect.right + 10;
                idealTop = buttonRect.top;
            }
            // If all else fails, place it in the center of the viewport
            else {
                idealLeft = (viewportWidth - elementWidth) / 2;
                idealTop = (viewportHeight - elementHeight) / 2;
            }
        }

        // Ensure left is within viewport
        idealLeft = Math.max(10, Math.min(idealLeft, viewportWidth - elementWidth - 10));

        // Ensure top is within viewport
        idealTop = Math.max(10, Math.min(idealTop, viewportHeight - elementHeight - 10));

        // Apply the position
        element.style.left = `${idealLeft}px`;
        element.style.top = `${idealTop}px`;
        element.style.right = "auto";
        element.style.bottom = "auto";
    }

    // Make chat container draggable
    let isDraggingContainer = false;
    let containerOffsetX, containerOffsetY;

    chatHeader.addEventListener("mousedown", startDragContainer);
    document.addEventListener("mousemove", dragContainer);
    document.addEventListener("mouseup", stopDragContainer);

    function startDragContainer(e) {
        // Only start dragging if we're clicking the header itself, not its children
        if (e.target === chatHeader || e.target.parentNode === chatHeader && e.target.tagName !== "BUTTON") {
            isDraggingContainer = true;
            const rect = chatContainer.getBoundingClientRect();
            containerOffsetX = e.clientX - rect.left;
            containerOffsetY = e.clientY - rect.top;
            e.preventDefault(); // Prevent text selection during drag
        }
    }

    function dragContainer(e) {
        if (!isDraggingContainer) return;

        const x = e.clientX - containerOffsetX;
        const y = e.clientY - containerOffsetY;

        // Keep widget within visible area of the window
        const maxX = window.innerWidth - chatContainer.offsetWidth;
        const maxY = window.innerHeight - chatContainer.offsetHeight;

        chatContainer.style.left = Math.max(0, Math.min(x, maxX)) + "px";
        chatContainer.style.top = Math.max(0, Math.min(y, maxY)) + "px";

        // Remove the default positioning once dragged
        chatContainer.style.right = "auto";
        chatContainer.style.bottom = "auto";
    }

    function stopDragContainer() {
        isDraggingContainer = false;
    }

    // Make button draggable
    let isDraggingButton = false;
    let buttonOffsetX, buttonOffsetY;

    buttonDragHandle.addEventListener("mousedown", startDragButton);
    document.addEventListener("mousemove", dragButton);
    document.addEventListener("mouseup", stopDragButton);

    function startDragButton(e) {
        isDraggingButton = true;
        const rect = chatButton.getBoundingClientRect();
        buttonOffsetX = e.clientX - rect.left;
        buttonOffsetY = e.clientY - rect.top;
        e.preventDefault(); // Prevent default behavior
        e.stopPropagation(); // Stop event from bubbling to parent elements
    }

    function dragButton(e) {
        if (!isDraggingButton) return;

        const x = e.clientX - buttonOffsetX;
        const y = e.clientY - buttonOffsetY;

        // Keep button within visible area of the window
        const maxX = window.innerWidth - chatButton.offsetWidth;
        const maxY = window.innerHeight - chatButton.offsetHeight;

        chatButton.style.left = Math.max(0, Math.min(x, maxX)) + "px";
        chatButton.style.top = Math.max(0, Math.min(y, maxY)) + "px";

        // Remove the default positioning once dragged
        chatButton.style.right = "auto";
        chatButton.style.bottom = "auto";
    }

    function stopDragButton() {
        isDraggingButton = false;
    }

    // Toggle chat widget visibility
    chatButton.addEventListener("click", function(e) {
        // Only toggle if the click wasn't on the drag handle
        if (e.target !== buttonDragHandle) {
            if (chatContainer.style.display === "none") {
                // Position the container intelligently before showing it
                chatContainer.style.display = "flex";
                setTimeout(() => {
                    ensureInViewport(chatContainer);
                }, 50); // Small delay

                chatButton.innerHTML = `
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                `;
                // Re-add the drag handle
                chatButton.appendChild(buttonDragHandle);

                // Focus the input field
                setTimeout(() => input.focus(), 100);
            } else {
                chatContainer.style.display = "none";
                chatButton.innerHTML = `
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM16 12.75H13.25V15.5C13.25 16.05 12.8 16.5 12.25 16.5H11.75C11.2 16.5 10.75 16.05 10.75 15.5V12.75H8C7.45 12.75 7 12.3 7 11.75V11.25C7 10.7 7.45 10.25 8 10.25H10.75V7.5C10.75 6.95 11.2 6.5 11.75 6.5H12.25C12.8 6.5 13.25 6.95 13.25 7.5V10.25H16C16.55 10.25 17 10.7 17 11.25V11.75C17 12.3 16.55 12.75 16 12.75Z"/>
                    </svg>
                `;
                // Re-add the drag handle
                chatButton.appendChild(buttonDragHandle);
            }
        }
    });

    // Close button functionality
    const closeButton = chatContainer.querySelector(".chat-widget-close");
    closeButton.onclick = () => {
        chatContainer.style.display = "none";
        chatButton.innerHTML = `
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM16 12.75H13.25V15.5C13.25 16.05 12.8 16.5 12.25 16.5H11.75C11.2 16.5 10.75 16.05 10.75 15.5V12.75H8C7.45 12.75 7 12.3 7 11.75V11.25C7 10.7 7.45 10.25 8 10.25H10.75V7.5C10.75 6.95 11.2 6.5 11.75 6.5H12.25C12.8 6.5 13.25 6.95 13.25 7.5V10.25H16C16.55 10.25 17 10.7 17 11.25V11.75C17 12.3 16.55 12.75 16 12.75Z"/>
            </svg>
        `;
        // Re-add the drag handle
        chatButton.appendChild(buttonDragHandle);
    };

    // Clear chat button functionality
    const clearButton = chatContainer.querySelector(".chat-widget-clear");
    clearButton.onclick = () => {
        if (confirm("Are you sure you want to clear the chat history?")) {
            clearChatHistory();
        }
    };

    // Handle window resize to keep elements in viewport
    window.addEventListener("resize", function() {
        if (chatContainer.style.display !== "none") {
            ensureInViewport(chatContainer);
        }

        // Also check if the button is now outside viewport
        const buttonRect = chatButton.getBoundingClientRect();
        if (buttonRect.right > window.innerWidth || buttonRect.bottom > window.innerHeight ||
            buttonRect.left < 0 || buttonRect.top < 0) {
            // Reset button to bottom right if it's outside viewport after resize
            chatButton.style.left = "auto";
            chatButton.style.top = "auto";
            chatButton.style.right = "20px";
            chatButton.style.bottom = "20px";
        }
    });

    // Send message functionality
    function sendMessage() {
        const userMessage = input.value.trim();
        if (!userMessage) return;

        // Add user message to chat
        const userMessageElement = document.createElement("div");
        userMessageElement.className = "chat-message user-message";
        userMessageElement.textContent = userMessage;
        chatMessages.appendChild(userMessageElement);

        // Clear input
        input.value = "";

        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Save after adding user message
        saveChatHistory();

        // Send to backend and get response
        fetch(`https://example.com/chat/${agentId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: userMessage })
        })
        .then(async response => {
            if (!response.ok) {
                let errorText = "Sorry, there was an error processing your request.";
                if (response.status === 401) errorText = "You are not authorized.";
                if (response.status === 403) errorText = "Access forbidden.";
                const errorMessage = document.createElement("div");
                errorMessage.className = "chat-message bot-message";
                errorMessage.textContent = errorText;
                chatMessages.appendChild(errorMessage);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                saveChatHistory();
                return;
            }
            let data;
            try {
                data = await response.json();
            } catch (e) {
                data = null;
            }
            if (data && data.response) {
                const botMessageElement = document.createElement("div");
                botMessageElement.className = "chat-message bot-message";
                // Format the response text before displaying
                botMessageElement.innerHTML = formatMessageText(data.response);
                chatMessages.appendChild(botMessageElement);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                saveChatHistory();
            } else {
                const errorMessage = document.createElement("div");
                errorMessage.className = "chat-message bot-message";
                errorMessage.textContent = "Sorry, there was an error processing your request.";
                chatMessages.appendChild(errorMessage);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                saveChatHistory();
            }
        })
        .catch(error => {
            console.error("Error:", error);
            const errorMessage = document.createElement("div");
            errorMessage.className = "chat-message bot-message";
            errorMessage.textContent = "Sorry, there was an error processing your request.";
            chatMessages.appendChild(errorMessage);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            saveChatHistory();
        });
    }

    // Handle send button click
    sendButton.onclick = sendMessage;

    // Handle Enter key press
    input.addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    window.chatWidget = {
        saveChatHistory,
        loadChatHistory,
        clearChatHistory,
        agentId
    };
})();