/**
 * ══════════════════════════════════════════════════════════
 * AI Co-Worker Engine — Frontend Application
 * ══════════════════════════════════════════════════════════
 */

const API_BASE = 'http://localhost:8000/api';

// ══════════════════════════════════════════════════════════
// State
// ══════════════════════════════════════════════════════════

const state = {
    sessionId: localStorage.getItem('sessionId') || generateSessionId(),
    currentAgent: 'CEO',
    autoRoute: false,  // When true, let AI decide which agent responds
    messageCount: 0,
    sentiment: 0.5,
    latency: 0,
    isLoading: false,
    tasks: {
        problem_statement_written: false,
        ceo_consulted: false,
        chro_consulted: false,
        competency_model_drafted: false,
        '360_program_designed': false,
        regional_manager_consulted: false,
        rollout_plan_built: false,
        kpi_table_defined: false
    }
};

// Save session ID to local storage
localStorage.setItem('sessionId', state.sessionId);

// ══════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function formatTime(date) {
    return new Intl.DateTimeFormat('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ══════════════════════════════════════════════════════════
// DOM Elements
// ══════════════════════════════════════════════════════════

const elements = {
    messagesContainer: document.getElementById('messages-container'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    loadingOverlay: document.getElementById('loading-overlay'),
    agentCards: document.querySelectorAll('.agent-card'),
    newChatBtn: document.getElementById('new-session-btn'),
    exportBtn: document.getElementById('export-btn'),
    sessionIdEl: document.getElementById('session-id'),
    messageCountEl: document.getElementById('turn-count'),
    sentimentFill: document.getElementById('sentiment-fill'),
    latencyBadge: document.getElementById('latency-badge'),
    currentAgentName: document.getElementById('current-agent-name'),
    currentAgentRole: document.getElementById('current-agent-desc'),
    agentBadge: document.getElementById('current-agent-badge'),
    taskItems: document.querySelectorAll('.task-item'),
    autoRouteToggle: document.getElementById('auto-route-toggle')
};

// ══════════════════════════════════════════════════════════
// API Calls
// ══════════════════════════════════════════════════════════

async function sendMessage(text) {
    const startTime = performance.now();
    
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: 'web_user_' + state.sessionId.substring(0, 8),
                session_id: state.sessionId,
                message: text,
                // If autoRoute is ON, send null to let Supervisor decide
                target_agent: state.autoRoute ? null : state.currentAgent
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        state.latency = Math.round(performance.now() - startTime);
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function loadChatHistory() {
    try {
        const response = await fetch(`${API_BASE}/chat/history/${state.sessionId}`);
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
    return [];
}

async function loadSessionState() {
    try {
        const response = await fetch(`${API_BASE}/chat/state/${state.sessionId}`);
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('Failed to load state:', error);
    }
    return null;
}

async function exportChat() {
    try {
        const response = await fetch(`${API_BASE}/chat/export/${state.sessionId}`);
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `chat_${state.sessionId}.md`;
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch (error) {
        console.error('Export failed:', error);
    }
}

async function deleteSession() {
    try {
        await fetch(`${API_BASE}/chat/sessions/${state.sessionId}`, {
            method: 'DELETE'
        });
    } catch (error) {
        console.error('Delete failed:', error);
    }
}

// ══════════════════════════════════════════════════════════
// UI Updates
// ══════════════════════════════════════════════════════════

function updateUI() {
    // Update session info (with null checks)
    if (elements.sessionIdEl) elements.sessionIdEl.textContent = state.sessionId.substring(0, 20) + '...';
    if (elements.messageCountEl) elements.messageCountEl.textContent = state.messageCount;
    if (elements.sentimentFill) elements.sentimentFill.style.width = `${state.sentiment * 100}%`;
    if (elements.latencyBadge) elements.latencyBadge.textContent = `${state.latency}ms`;
    
    // Update agent cards
    elements.agentCards.forEach(card => {
        card.classList.toggle('active', card.dataset.agent === state.currentAgent);
    });
    
    // Update header
    const agentInfo = getAgentInfo(state.currentAgent);
    if (elements.currentAgentName) elements.currentAgentName.textContent = agentInfo.name;
    if (elements.currentAgentRole) elements.currentAgentRole.textContent = agentInfo.role;
    if (elements.agentBadge) elements.agentBadge.textContent = agentInfo.emoji;
}

function getAgentInfo(agent) {
    const agents = {
        CEO: { name: 'CEO', role: 'Gucci Group CEO — Group DNA & Strategy', emoji: '👔' },
        CHRO: { name: 'CHRO', role: 'HR & Competencies', emoji: '👥' },
        RegionalManager: { name: 'Regional Manager', role: 'Europe Operations', emoji: '🌍' },
        Mentor: { name: 'System Guide', role: 'Hints & Guidance', emoji: '💡' },
        System: { name: 'System', role: 'Safety', emoji: '🛡️' }
    };
    return agents[agent] || agents.CEO;
}

function addMessage(content, type = 'agent', agentName = null) {
    if (!elements.messagesContainer) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const avatar = type === 'user' ? '👤' : getAgentInfo(agentName || state.currentAgent).emoji;
    
    let html = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            ${escapeHtml(content).replace(/\n/g, '<br>')}
    `;
    
    if (type === 'agent' && agentName) {
        html += `
            <div class="message-meta">
                <span class="agent-name ${agentName}">${agentName}</span>
                <span>•</span>
                <span>${formatTime(new Date())}</span>
            </div>
        `;
    }
    
    html += '</div>';
    messageDiv.innerHTML = html;
    
    elements.messagesContainer.appendChild(messageDiv);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    
    state.messageCount++;
    updateUI();
}

function addSystemMessage(text) {
    if (!elements.messagesContainer) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message system';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(text)}</p>
        </div>
    `;
    elements.messagesContainer.appendChild(messageDiv);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function showLoading(show = true) {
    state.isLoading = show;
    if (elements.loadingOverlay) elements.loadingOverlay.style.display = show ? 'flex' : 'none';
    if (elements.sendBtn) elements.sendBtn.disabled = show;
}

function showTypingIndicator() {
    if (!elements.messagesContainer) return;
    
    const indicator = document.createElement('div');
    indicator.className = 'message agent typing-indicator';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = `
        <div class="message-avatar">${getAgentInfo(state.currentAgent).emoji}</div>
        <div class="message-content">
            <span style="color: var(--text-muted)">Typing...</span>
        </div>
    `;
    elements.messagesContainer.appendChild(indicator);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
}

function updateTaskProgress(agentType, backendTaskProgress) {
    // Use backend task_progress if available (authoritative source)
    if (backendTaskProgress && typeof backendTaskProgress === 'object') {
        for (const [key, value] of Object.entries(backendTaskProgress)) {
            if (key in state.tasks) {
                state.tasks[key] = value;
            }
        }
    }
    
    // Also mark task based on which agent was consulted (frontend-side)
    if (agentType === 'CEO') {
        state.tasks.ceo_consulted = true;
    } else if (agentType === 'CHRO') {
        state.tasks.chro_consulted = true;
    } else if (agentType === 'RegionalManager') {
        state.tasks.regional_manager_consulted = true;
    }
    
    // Update task items UI
    elements.taskItems.forEach(item => {
        const task = item.dataset.task;
        if (state.tasks[task]) {
            item.classList.add('completed');
        }
    });
}

// ══════════════════════════════════════════════════════════
// Event Handlers
// ══════════════════════════════════════════════════════════

async function handleSend() {
    if (!elements.messageInput) return;
    
    const text = elements.messageInput.value.trim();
    if (!text || state.isLoading) return;
    
    // Add user message
    addMessage(text, 'user');
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        const response = await sendMessage(text);
        hideTypingIndicator();
        
        // Determine which agent responded
        const respondingAgent = response.agent || state.currentAgent;
        
        // If auto-route: update header and highlight the responding agent
        if (state.autoRoute && respondingAgent && respondingAgent !== 'System') {
            // Update header to show who is responding
            const agentInfo = getAgentInfo(respondingAgent);
            if (elements.currentAgentName) elements.currentAgentName.textContent = agentInfo.name;
            if (elements.currentAgentRole) elements.currentAgentRole.textContent = agentInfo.role;
            if (elements.agentBadge) elements.agentBadge.textContent = agentInfo.emoji;
            
            // Highlight the responding agent card
            elements.agentCards.forEach(card => {
                card.classList.toggle('active', card.dataset.agent === respondingAgent);
            });
        }
        
        // If Mentor responded via Director hint, show as hint message
        // But still show it as a proper agent message with the Mentor label
        if (respondingAgent === 'Mentor') {
            addMessage(`💡 Hint: ${response.response}`, 'agent', 'Mentor');
        } else {
            // Add normal agent response with agent name
            addMessage(response.response, 'agent', respondingAgent);
        }
        
        // Update task progress from backend (authoritative)
        const taskProgress = response.state_update?.task_progress;
        updateTaskProgress(respondingAgent, taskProgress);
        
        // Update sentiment from backend
        if (response.state_update?.sentiment_score !== undefined) {
            state.sentiment = response.state_update.sentiment_score;
        }
        
        updateUI();
    } catch (error) {
        hideTypingIndicator();
        addMessage(`Error: ${error.message}. Please check if the backend is running.`, 'system');
    }
}

function handleAgentSwitch(agent) {
    state.currentAgent = agent;
    
    // Turn off auto-route when user manually selects an agent
    if (state.autoRoute) {
        state.autoRoute = false;
        if (elements.autoRouteToggle) {
            elements.autoRouteToggle.checked = false;
            elements.autoRouteToggle.closest('.auto-route-toggle')?.classList.remove('active');
            elements.autoRouteToggle.closest('.agent-section')?.classList.remove('auto-mode');
        }
    }
    
    updateUI();
    addSystemMessage(`Switched to ${getAgentInfo(agent).name}`);
}

function handleNewChat() {
    // Generate new session
    state.sessionId = generateSessionId();
    localStorage.setItem('sessionId', state.sessionId);
    state.messageCount = 0;
    state.sentiment = 0.5;
    state.autoRoute = false;
    state.tasks = {
        problem_statement_written: false,
        ceo_consulted: false,
        chro_consulted: false,
        competency_model_drafted: false,
        '360_program_designed': false,
        regional_manager_consulted: false,
        rollout_plan_built: false,
        kpi_table_defined: false
    };
    
    // Reset auto-route toggle
    if (elements.autoRouteToggle) {
        elements.autoRouteToggle.checked = false;
        elements.autoRouteToggle.closest('.auto-route-toggle')?.classList.remove('active');
        elements.autoRouteToggle.closest('.agent-section')?.classList.remove('auto-mode');
    }
    
    // Clear messages
    if (elements.messagesContainer) elements.messagesContainer.innerHTML = '';
    
    // Reset task items
    elements.taskItems.forEach(item => item.classList.remove('completed'));
    
    // Add welcome message
    addSystemMessage(`New conversation started`);
    addMessage(
        `Xin chào! Tôi là ${getAgentInfo(state.currentAgent).name}. Hôm nay tôi có thể giúp gì cho bạn?`,
        'agent',
        state.currentAgent
    );
    
    updateUI();
}

async function handleExport() {
    await exportChat();
}

// ══════════════════════════════════════════════════════════
// Event Listeners
// ══════════════════════════════════════════════════════════

// Send button
if (elements.sendBtn) elements.sendBtn.addEventListener('click', handleSend);

// Enter to send
if (elements.messageInput) {
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Auto-resize textarea
    elements.messageInput.addEventListener('input', () => {
        elements.messageInput.style.height = 'auto';
        elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 150) + 'px';
        // Enable/disable send button
        if (elements.sendBtn) elements.sendBtn.disabled = !elements.messageInput.value.trim();
    });
}

// Agent cards
elements.agentCards.forEach(card => {
    card.addEventListener('click', () => {
        handleAgentSwitch(card.dataset.agent);
    });
});

// Auto-route toggle
if (elements.autoRouteToggle) {
    elements.autoRouteToggle.addEventListener('change', (e) => {
        state.autoRoute = e.target.checked;
        const toggleContainer = elements.autoRouteToggle.closest('.auto-route-toggle');
        const agentSection = elements.autoRouteToggle.closest('.agent-section');
        
        if (state.autoRoute) {
            toggleContainer.classList.add('active');
            agentSection?.classList.add('auto-mode');
            // Deselect all agent cards visually
            elements.agentCards.forEach(card => card.classList.remove('active'));
            addSystemMessage('🤖 Auto-Route enabled — AI will decide which agent responds based on your message');
        } else {
            toggleContainer.classList.remove('active');
            agentSection?.classList.remove('auto-mode');
            // Re-select current agent
            elements.agentCards.forEach(card => {
                card.classList.toggle('active', card.dataset.agent === state.currentAgent);
            });
            addSystemMessage(`🎯 Manual mode — chatting with ${state.currentAgent}`);
        }
    });
}

// New chat button
if (elements.newChatBtn) elements.newChatBtn.addEventListener('click', handleNewChat);

// Export button
if (elements.exportBtn) elements.exportBtn.addEventListener('click', handleExport);

// ══════════════════════════════════════════════════════════
// Initialize
// ══════════════════════════════════════════════════════════

async function init() {
    showLoading(true);
    
    try {
        // Try to load existing history
        const history = await loadChatHistory();
        
        if (history && history.length > 0) {
            // Restore conversation
            history.forEach(msg => {
                if (msg.role === 'user') {
                    addMessage(msg.content, 'user');
                } else if (msg.role === 'assistant') {
                    addMessage(msg.content, 'agent', msg.agent || state.currentAgent);
                }
            });
        } else {
            // New conversation
            addSystemMessage(`Welcome to AI Co-Worker Engine`);
            addMessage(
                `Xin chào! Tôi là ${getAgentInfo(state.currentAgent).name}. Đây là buổi mô phỏng công việc của bạn. Hãy hỏi tôi bất kỳ điều gì về chiến lược công ty, ngân sách, hoặc kế hoạch phát triển!`,
                'agent',
                state.currentAgent
            );
        }
        
        updateUI();
    } catch (error) {
        console.error('Init error:', error);
        addSystemMessage('Welcome to AI Co-Worker Engine');
    } finally {
        showLoading(false);
    }
}

// Start app
init();
