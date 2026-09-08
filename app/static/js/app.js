document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const bookListEl = document.getElementById('book-list');
    const uploadForm = document.getElementById('upload-form');
    const bookTitleInput = document.getElementById('book-title');
    const bookFileInput = document.getElementById('book-file');
    const uploadBtn = document.getElementById('upload-button');
    const uploadStatus = document.getElementById('upload-status');
    
    const chatArea = document.querySelector('.main-content');
    const chatInputArea = document.querySelector('.chat-input-area');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const rulebookBtn = document.getElementById('rulebook-btn');
    const currentBookTitle = document.getElementById('current-book-title');
    const clearChat = document.getElementById('clear-chat');

    // State
    let currentBookId = null;
    let books = [];
    let isGenerating = false;
    let generatingBookId = null;

    function getChatContainer(bookId) {
        let container = document.getElementById('chat-messages-' + bookId);
        if (!container) {
            container = document.createElement('div');
            container.id = 'chat-messages-' + bookId;
            container.className = 'chat-container';
            container.style.display = 'none';
            chatArea.insertBefore(container, chatInputArea);
        }
        return container;
    }
    
    function getActiveContainer() {
        return getChatContainer(currentBookId);
    }

    // --- Phase 9: Error Handling (Toasts) ---
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = '';
        if (type === 'error') icon = '[Error]';
        if (type === 'success') icon = '[Success]';
        if (type === 'info') icon = '[Info]';

        toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
        container.appendChild(toast);

        // Auto remove
        setTimeout(() => {
            toast.classList.add('fade-out');
            toast.addEventListener('animationend', () => toast.remove());
        }, 5000);
    }

    // --- Phase 7: Library Management ---

    async function loadBooks() {
        try {
            const response = await fetch('/api/books');
            const data = await response.json();
            books = data.books || [];
            renderBookList();
            
            // Auto-select global chat if none selected
            if (!currentBookId) {
                if (books.length > 0) {
                    selectBook('global');
                } else {
                    currentBookId = null;
                    currentBookTitle.textContent = 'Upload a tome to seek wisdom';
                    chatInput.disabled = true;
                    sendButton.disabled = true;
                    // Wipe default container manually if needed
                    const defaultContainer = document.getElementById('chat-messages');
                    if (defaultContainer) {
                        defaultContainer.innerHTML = `
                            <div class="message system-message">
                                <div class="message-content">
                                    <h3>Welcome to The Maester!</h3>
                                    <p>Offer a tome or scroll to the Citadel, that I may study its contents and answer your inquiries.</p>
                                </div>
                            </div>
                        `;
                    }
                }
            } else {
                // Refresh selection state in UI
                renderBookList();
            }
        } catch (error) {
            console.error('Failed to load books:', error);
            bookListEl.innerHTML = `<div class="empty-state" style="color:var(--punch-red)">Error loading library.</div>`;
        }
    }

    function renderBookList() {
        if (books.length === 0) {
            bookListEl.innerHTML = '<div class="empty-state">No tomes in the archives. Add one above.</div>';
            return;
        }

        bookListEl.innerHTML = '';
        books.forEach(book => {
            const item = document.createElement('div');
            item.className = 'book-item';
            if (book.id === currentBookId) {
                item.classList.add('active');
            }
            item.onclick = () => selectBook(book.id);

            const info = document.createElement('div');
            info.className = 'book-info';
            info.innerHTML = `
                <h4>${escapeHtml(book.title)}</h4>
                <p>${book.total_pages} pages • ${book.total_chunks} chunks</p>
            `;

            const delBtn = document.createElement('button');
            delBtn.className = 'book-delete';
            delBtn.title = "Delete Book";
            delBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            `;
            delBtn.onclick = (e) => {
                e.stopPropagation();
                deleteBook(book.id);
            };

            item.appendChild(info);
            item.appendChild(delBtn);
            bookListEl.appendChild(item);
        });
    }

    async function selectBook(bookId) {
        if (!bookId) return;
        currentBookId = bookId;
        let title = '';
        
        // Hide all containers
        document.querySelectorAll('.chat-container').forEach(el => {
            el.style.display = 'none';
        });
        // Show current container
        const container = getActiveContainer();
        container.style.display = 'flex';
        
        const globalEl = document.getElementById('global-chat-item');
        
        if (bookId === 'global') {
            title = 'Global Knowledge Base';
            if (globalEl) globalEl.classList.add('active');
        } else {
            const book = books.find(b => b.id === bookId);
            if (!book) return;
            title = book.title;
            if (globalEl) globalEl.classList.remove('active');
        }

        // Update UI
        currentBookTitle.textContent = title;
        chatInput.disabled = false;
        sendButton.disabled = false;
        renderBookList(); // refresh active class
        
        const exportBtn = document.getElementById('export-chat');
        const previewBtn = document.getElementById('inspect-scroll');
        
        if (exportBtn) {
            exportBtn.style.display = 'inline-block';
            exportBtn.onclick = () => {
                if (bookId === 'global') {
                    exportGlobalChat();
                } else {
                    window.location.href = `/api/books/${bookId}/export`;
                }
            };
        }
        
        if (clearChat) {
            clearChat.style.display = 'inline-block';
        }
        
        if (previewBtn) {
            previewBtn.style.display = bookId === 'global' ? 'none' : 'inline-block';
            if (bookId !== 'global') {
                previewBtn.onclick = () => {
                    if (typeof openPdfModal === 'function') {
                        openPdfModal(bookId, 1, null);
                    }
                };
            }
        }
        
        await loadChatHistory(bookId);
    }
    
    // Expose for HTML onclick
    window.selectBook = selectBook;

    async function deleteBook(bookId) {
        if (!confirm('Are you sure you want to delete this book? This will erase the PDF, embeddings, and chat history permanently.')) {
            return;
        }

        try {
            const btn = document.querySelector(`.book-item[onclick="selectBook(${bookId})"] .book-delete`);
            if (btn) {
                btn.innerHTML = '...';
                btn.disabled = true;
            }

            const response = await fetch(`/api/books/${bookId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                if (currentBookId === bookId) {
                    location.reload();
                    return;
                }
                showToast('Book deleted successfully.', 'success');
                await loadBooks(); // Refresh list and auto-select
            } else {
                const data = await response.json();
                showToast('Error deleting book: ' + (data.error || 'Unknown error'), 'error');
                await loadBooks();
            }
        } catch (error) {
            console.error('Delete error:', error);
            showToast('Network error deleting book.', 'error');
            await loadBooks();
        }
    }

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const title = bookTitleInput.value.trim();
        const file = bookFileInput.files[0];
        
        if (!title || !file) return;

        const formData = new FormData();
        formData.append('title', title);
        formData.append('file', file);

        // UI Loading State
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading & Indexing...';
        bookTitleInput.disabled = true;
        bookFileInput.disabled = true;
        uploadStatus.style.display = 'block';
        uploadStatus.textContent = 'This may take a minute or two as AI extracts text and images...';
        uploadStatus.style.color = 'var(--cerulean)';

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.status === 202) {
                // Background processing started, begin polling
                const bookId = data.book.id;
                pollUploadStatus(bookId, title);
            } else if (response.ok) {
                // Synchronous fallback just in case
                uploadStatus.textContent = `Success! Processed ${data.book.total_pages} pages.`;
                uploadStatus.style.color = 'var(--light-gold)';
                showToast(`Successfully processed "${title}"`, 'success');
                uploadForm.reset();
                await loadBooks();
                selectBook(data.book.id);
                
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Store Scroll';
                bookTitleInput.disabled = false;
                bookFileInput.disabled = false;
            } else {
                uploadStatus.textContent = 'Error: ' + (data.error || 'Upload failed');
                uploadStatus.style.color = 'var(--punch-red)';
                showToast(data.error || 'Upload failed', 'error');
                
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload PDF';
                bookTitleInput.disabled = false;
                bookFileInput.disabled = false;
            }
        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = 'Network error during upload.';
            uploadStatus.style.color = 'var(--punch-red)';
            showToast('Network error during upload.', 'error');
            
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload PDF';
            bookTitleInput.disabled = false;
            bookFileInput.disabled = false;
        }
    });

    function pollUploadStatus(bookId, title) {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/books/${bookId}`);
                if (!res.ok) return;
                const data = await res.json();
                if (data.book) {
                    const b = data.book;
                    
                    let text = 'Preparing your document';
                    let isTyping = false;
                    
                    if (b.processing_status === 'text_extracted' || b.processing_status === 'indexing') {
                        isTyping = true;
                        let progress = 0;
                        if (b.total_chunks > 0) {
                            progress = Math.round((b.processed_chunks / b.total_chunks) * 100);
                        }
                        text = `Indexing knowledge: ${progress}% (${b.processed_chunks} of ${b.total_chunks} chunks)`;
                    } else if (b.total_pages > 0 && b.processing_status === 'processing') {
                        isTyping = true;
                        text = `Reading pages: ${b.processed_pages} of ${b.total_pages}`;
                    } else if (b.processing_status === 'processing') {
                        isTyping = true;
                        text = 'Extracting text from document';
                    }
                    
                    uploadStatus.textContent = text;
                    if (isTyping) {
                        uploadStatus.classList.add('typing-text');
                    } else {
                        uploadStatus.classList.remove('typing-text');
                    }
                    
                    if (b.processing_status === 'completed') {
                        clearInterval(interval);
                        uploadStatus.textContent = `Success! Processed ${b.total_pages} pages.`;
                        uploadStatus.style.color = 'var(--light-gold)';
                        showToast(`Successfully processed "${title}"`, 'success');
                        uploadForm.reset();
                        await loadBooks();
                        selectBook(b.id);
                        
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = 'Store Scroll';
                        bookTitleInput.disabled = false;
                        bookFileInput.disabled = false;
                    } else if (b.processing_status === 'failed') {
                        clearInterval(interval);
                        uploadStatus.textContent = 'Error: Processing failed on the server.';
                        uploadStatus.style.color = 'var(--punch-red)';
                        showToast('Processing failed', 'error');
                        
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = 'Upload PDF';
                        bookTitleInput.disabled = false;
                        bookFileInput.disabled = false;
                    }
                }
            } catch (e) {
                 console.error('Polling error:', e);
            }
        }, 2000);
    }

    // --- Phase 6: Chat Interfaces ---

    async function loadChatHistory(bookId) {
        const targetContainer = getChatContainer(bookId);
        // Skip fetching if we already have messages in the DOM
        if (targetContainer.children.length > 0) {
            scrollToBottom();
            return;
        }

        try {
            const response = await fetch(`/api/books/${bookId}/chat`);
            const data = await response.json();
            
            targetContainer.innerHTML = '';
            
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    appendMessage(msg.role, msg.content, false, null, targetContainer);
                });
            } else {
                appendSystemMessage(`Started a new session with "${currentBookTitle.textContent}"`, targetContainer);
            }
            scrollToBottom();
        } catch (error) {
            console.error('Failed to load chat history:', error);
            appendSystemMessage('Error loading chat history.', targetContainer);
        }
    }

    if (rulebookBtn) {
        rulebookBtn.addEventListener('click', () => {
            document.getElementById('rulebook-modal').style.display = 'block';
        });
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const text = chatInput.value.trim();
        if (!text || !currentBookId) return;
        if (isGenerating) {
            appendSystemMessage('A Maester is currently answering a question. Please wait.', getChatContainer(currentBookId));
            showToast('A Maester is currently answering a question. Please wait.', 'error');
            return;
        }
        
        const questionBookId = currentBookId;
        const targetContainer = getChatContainer(questionBookId);
        
        isGenerating = true;
        generatingBookId = questionBookId;

        appendMessage('user', text, true, null, targetContainer);
        chatInput.value = '';
        chatInput.disabled = true;
        sendButton.disabled = true;

        // Show typing dots while waiting for server
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant-message chat-typing-indicator';
        typingDiv.innerHTML = `<div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
        targetContainer.appendChild(typingDiv);
        scrollToBottom();
        
        try {
            const response = await fetch(`/api/books/${questionBookId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            
            // We will delay removing the typing indicator until we receive the first chunk from the stream.
            
            if (response.ok) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let msgDiv = null;
                let contentDiv = null;
                let accumulatedText = "";
                
                let sourcesPayload = null;

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    
                    const chunkStr = decoder.decode(value, { stream: true });
                    const lines = chunkStr.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const dataStr = line.slice(6).trim();
                            if (!dataStr) continue;
                            try {
                                const data = JSON.parse(dataStr);
                                
                                // Create msgDiv and remove typing indicator on first valid chunk
                                if (!msgDiv) {
                                    const typingEl = targetContainer.querySelector('.chat-typing-indicator');
                                    if (typingEl) typingEl.remove();
                                    
                                    msgDiv = document.createElement('div');
                                    msgDiv.className = `message assistant-message`;
                                    contentDiv = document.createElement('div');
                                    contentDiv.className = 'message-content';
                                    msgDiv.appendChild(contentDiv);
                                    targetContainer.appendChild(msgDiv);
                                }
                                if (data.type === 'sources') {
                                    sourcesPayload = data.sources;
                                } else if (data.type === 'chunk') {
                                    accumulatedText += data.text;
                                    contentDiv.innerHTML = marked.parse(accumulatedText);
                                    if (currentBookId === questionBookId) scrollToBottom();
                                } else if (data.type === 'done') {
                                    // Finalize
                                    if (window.renderMathInElement) {
                                        renderMathInElement(contentDiv, {
                                            delimiters: [
                                                {left: '$$', right: '$$', display: true},
                                                {left: '$', right: '$', display: false},
                                                {left: '\\(', right: '\\)', display: false},
                                                {left: '\\[', right: '\\]', display: true}
                                            ],
                                            throwOnError: false
                                        });
                                    }
                                    if (sourcesPayload && sourcesPayload.length > 0) {
                                        appendCitationBadges(contentDiv, sourcesPayload);
                                    }
                                    if (currentBookId === questionBookId) scrollToBottom();
                                }
                            } catch (e) {
                                console.error("Error parsing stream data", e);
                            }
                        }
                    }
                }
            } else {
                const data = await response.json();
                appendMessage('assistant', 'Error: ' + (data.error || 'Failed to generate answer.'), true, null, targetContainer);
                showToast(data.error || 'Failed to generate answer', 'error');
            }
        } catch (error) {
            console.error('Chat error:', error);
            const typingEl = targetContainer.querySelector('.chat-typing-indicator');
            if (typingEl) typingEl.remove();
            appendMessage('assistant', 'Network error while generating answer.', true, null, targetContainer);
            showToast('Network error while generating answer.', 'error');
        } finally {
            isGenerating = false;
            generatingBookId = null;
            if (currentBookId) {
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            }
        }
    });

    function appendMessage(role, content, smoothScroll = true, sources = null, targetContainer = getActiveContainer()) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (role === 'assistant') {
            contentDiv.innerHTML = marked.parse(content);
            
            // Render Math using KaTeX auto-render
            if (window.renderMathInElement) {
                renderMathInElement(contentDiv, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '\\[', right: '\\]', display: true}
                    ],
                    throwOnError: false
                });
            }
            
            // Render citation badges if sources exist
            if (sources && sources.length > 0) {
                appendCitationBadges(contentDiv, sources);
            }
        } else {
            contentDiv.textContent = content;
        }
        
        msgDiv.appendChild(contentDiv);
        targetContainer.appendChild(msgDiv);
        
        if (smoothScroll) {
            scrollToBottom();
        }
    }

    function appendCitationBadges(contentDiv, sources) {
        const badgesDiv = document.createElement('div');
        badgesDiv.className = 'citation-badges';
        
        sources.forEach((source, index) => {
            const badge = document.createElement('button');
            badge.className = 'citation-badge';
            
            let label = `Source ${index + 1}`;
            let pageNum = source.metadata && source.metadata.page ? source.metadata.page : null;
            if (!pageNum && source.metadata && source.metadata.pages) {
                pageNum = source.metadata.pages.split(',')[0]; // pick first page
            }
            
            if (pageNum) {
                label += ` (Pg ${pageNum})`;
            }
            
            badge.textContent = label;
            badge.onclick = () => {
                let bookId = currentBookId;
                if (source.metadata && source.metadata.book_id) {
                    bookId = source.metadata.book_id;
                }
                
                if (bookId === 'global' || !bookId) {
                    // Fallback to text citation modal if we don't know the exact book
                    let title = 'Source Context';
                    if (source.metadata && source.metadata.book_title) {
                        title = source.metadata.book_title;
                    }
                    openCitationModal(title, source.content);
                } else {
                    // Extract first few words of the content as a search snippet for the PDF viewer
                    let searchSnippet = null;
                    if (source.content) {
                        // Get first ~10 words to use as a search highlight
                        searchSnippet = source.content.split(/\s+/).slice(0, 10).join(' ');
                    }
                    openPdfModal(bookId, pageNum, searchSnippet);
                }
            };
            
            badgesDiv.appendChild(badge);
        });
        
        contentDiv.appendChild(badgesDiv);
    }


    function appendSystemMessage(content, targetContainer = getActiveContainer()) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system-message';
        msgDiv.innerHTML = `<div class="message-content"><p>${content}</p></div>`;
        targetContainer.appendChild(msgDiv);
    }

    function appendLoadingIndicator(targetContainer = getActiveContainer()) {
        const id = 'loading-' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.id = id;
        msgDiv.className = 'message assistant-message';
        msgDiv.innerHTML = `<div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
        targetContainer.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        const targetContainer = getActiveContainer();
        targetContainer.scrollTop = targetContainer.scrollHeight;
    }

    // Modal functions
    window.openCitationModal = function(title, content) {
        document.getElementById('citation-title').textContent = title;
        const contentEl = document.getElementById('citation-content');
        contentEl.textContent = content;
        
        if (window.renderMathInElement) {
            renderMathInElement(contentEl, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError: false
            });
        }
        
        document.getElementById('citation-modal').style.display = 'block';
    };

    window.closeCitationModal = function() {
        document.getElementById('citation-modal').style.display = 'none';
    };

    window.openPdfModal = function(bookId, pageNum, searchQuery = null) {
        const modal = document.getElementById('pdf-modal');
        const iframe = document.getElementById('pdf-viewer');
        
        let url = `/api/books/${bookId}/file`;
        let hashParams = [];
        if (pageNum) {
            hashParams.push(`page=${pageNum}`);
        }
        if (searchQuery) {
            hashParams.push(`search="${encodeURIComponent(searchQuery)}"`);
        }
        if (hashParams.length > 0) {
            url += '#' + hashParams.join('&');
        }
        
        iframe.src = url;
        modal.classList.add('active');
    };

    window.closePdfModal = function() {
        const modal = document.getElementById('pdf-modal');
        const iframe = document.getElementById('pdf-viewer');
        modal.classList.remove('active');
        // Clear src to stop video/audio if any, and free memory
        setTimeout(() => {
            iframe.src = '';
        }, 300);
    };

    window.closeRulebookModal = function() {
        document.getElementById('rulebook-modal').style.display = 'none';
    }

    window.onclick = function(event) {
        const citationModal = document.getElementById('citation-modal');
        const rulebookModal = document.getElementById('rulebook-modal');
        if (event.target == citationModal) {
            closeCitationModal();
        }
        if (event.target == rulebookModal) {
            closeRulebookModal();
        }
    };

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    function exportGlobalChat() {
        let mdContent = "# Chat History: Global Wisdom\n\n";
        const targetContainer = getChatContainer('global');
        const messages = targetContainer.querySelectorAll('.message');
        
        messages.forEach(msg => {
            if (msg.classList.contains('system-message')) return;
            const isUser = msg.classList.contains('user-message');
            const role = isUser ? 'User' : 'AI';
            // Extract text content carefully to avoid getting HTML tags
            const contentDiv = msg.querySelector('.message-content');
            if (contentDiv) {
                // Simple innerText extraction
                let text = contentDiv.innerText;
                // Exclude sources container if present
                const sources = contentDiv.querySelector('.sources-container');
                if (sources) {
                    text = text.replace(sources.innerText, '').trim();
                }
                if (text) {
                    mdContent += `**${role}**:\n${text}\n\n---\n\n`;
                }
            }
        });

        const blob = new Blob([mdContent], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'chat_export_global.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // Clear Chat logic
    clearChat.addEventListener('click', async () => {
        if (!currentBookId) return;
        
        if (confirm("Are you sure you want to clear the chronicle? This cannot be undone.")) {
            if (currentBookId === 'global') {
                const targetContainer = getChatContainer('global');
                targetContainer.innerHTML = '';
                appendSystemMessage('Started a new global session.', targetContainer);
                showToast('Global chronicle cleared.', 'success');
                return;
            }
            
            try {
                const response = await fetch(`/api/books/${currentBookId}/chat`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const targetContainer = getChatContainer(currentBookId);
                    targetContainer.innerHTML = '';
                    appendSystemMessage(`Started a new session with "${currentBookTitle.textContent}"`, targetContainer);
                    showToast('Chronicle cleared successfully.', 'success');
                } else {
                    const data = await response.json();
                    showToast(data.error || 'Failed to clear chat.', 'error');
                }
            } catch (error) {
                console.error('Error clearing chat:', error);
                showToast('Network error while clearing chat.', 'error');
            }
        }
    });

    // Initialize
    loadBooks();
});
