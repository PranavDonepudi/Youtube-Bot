// Configuration
const API_URL = 'http://localhost:8000';

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadStats();
    
    // Enable Enter key to send (Shift+Enter for new line)
    document.getElementById('questionInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });
});

// Check API health status
async function checkHealth() {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        
        if (data.status === 'healthy') {
            statusDot.className = 'status-dot connected';
            statusText.textContent = '✅ Connected and ready';
        } else {
            statusDot.className = 'status-dot error';
            statusText.textContent = '⚠️ Service degraded - check configuration';
        }
    } catch (error) {
        statusDot.className = 'status-dot error';
        statusText.textContent = '❌ Cannot connect to API server';
        console.error('Health check failed:', error);
    }
}

// Load database statistics
async function loadStats() {
    const statsContent = document.getElementById('statsContent');
    
    try {
        const response = await fetch(`${API_URL}/stats`);
        const data = await response.json();
        
        let statsHTML = `
            <div class="stat-item">
                <span class="stat-label">Total Chunks:</span> ${data.total_chunks.toLocaleString()}
            </div>
            <div class="stat-item">
                <span class="stat-label">Total Videos:</span> ${data.total_videos}
            </div>
        `;
        
        if (data.sample_videos && data.sample_videos.length > 0) {
            statsHTML += `
                <div class="stat-item">
                    <span class="stat-label">Sample Videos:</span>
                    <ul style="margin-top: 8px; padding-left: 20px;">
                        ${data.sample_videos.slice(0, 5).map(v => 
                            `<li style="margin: 4px 0;">${v.title}</li>`
                        ).join('')}
                    </ul>
                </div>
            `;
        }
        
        statsContent.innerHTML = statsHTML;
    } catch (error) {
        statsContent.innerHTML = '<p style="color: #ef4444;">Failed to load stats</p>';
        console.error('Stats loading failed:', error);
    }
}

// Send a question to the bot
async function sendQuestion() {
    const input = document.getElementById('questionInput');
    const question = input.value.trim();
    
    if (!question) return;
    
    // Disable input while processing
    const sendButton = document.getElementById('sendButton');
    const buttonText = document.getElementById('buttonText');
    const buttonLoader = document.getElementById('buttonLoader');
    
    input.disabled = true;
    sendButton.disabled = true;
    buttonText.style.display = 'none';
    buttonLoader.style.display = 'inline-block';
    
    // Add user message to chat
    addMessage(question, 'user');
    
    // Clear input
    input.value = '';
    
    try {
        const response = await fetch(`${API_URL}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                n_results: 5
            })
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Add bot response to chat
        addMessage(data.answer, 'bot', data.sources);
        
    } catch (error) {
        console.error('Error:', error);
        addMessage(
            '❌ Sorry, I encountered an error while processing your question. Please make sure the API server is running and try again.',
            'bot'
        );
    } finally {
        // Re-enable input
        input.disabled = false;
        sendButton.disabled = false;
        buttonText.style.display = 'inline';
        buttonLoader.style.display = 'none';
        input.focus();
    }
}

// Add a message to the chat
function addMessage(content, type, sources = null) {
    const messagesContainer = document.getElementById('messagesContainer');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    let messageHTML = `
        <div class="message-content">
            <p>${formatText(content)}</p>
    `;
    
    // Add sources if available
    if (sources && sources.length > 0) {
        messageHTML += `
            <div class="sources">
                <h4>📚 Sources:</h4>
        `;
        
        // Group sources by video to avoid duplicates
        const uniqueVideos = {};
        sources.forEach(source => {
            if (!uniqueVideos[source.video_id]) {
                uniqueVideos[source.video_id] = source;
            }
        });
        
        Object.values(uniqueVideos).forEach(source => {
            messageHTML += `
                <div class="source-item">
                    <div class="source-title">${escapeHtml(source.title)}</div>
                    <a href="${escapeHtml(source.url)}" target="_blank" class="source-link">
                        Watch video →
                    </a>
                </div>
            `;
        });
        
        messageHTML += `</div>`;
    }
    
    messageHTML += `</div>`;
    
    messageDiv.innerHTML = messageHTML;
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Format text with basic markdown-like parsing
function formatText(text) {
    // Convert newlines to <br>
    text = text.replace(/\n/g, '<br>');
    
    // Bold text with **
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic text with *
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    return text;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Example questions for users to try
const exampleQuestions = [
    "What topics are covered in these videos?",
    "Summarize the main themes",
    "What did they say about [specific topic]?",
    "Which video talks about [X]?"
];

// You can add a button to show example questions if desired
function showExampleQuestions() {
    const examples = exampleQuestions
        .map(q => `<button onclick="fillQuestion('${q}')" class="example-btn">${q}</button>`)
        .join('');
    
    // Could add this to the UI if desired
    console.log('Example questions:', exampleQuestions);
}

function fillQuestion(question) {
    document.getElementById('questionInput').value = question;
}
