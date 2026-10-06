const fileInput = document.getElementById("fileInput");
const uploadCard = document.getElementById("uploadCard");
const chatContainer = document.getElementById("chatContainer");
const messages = document.getElementById("messages");
const questionForm = document.getElementById("questionForm");
const questionInput = document.getElementById("questionInput");
const askButton = document.getElementById("askButton");
const documentInfo = document.getElementById("documentInfo");
const newDocumentButton = document.getElementById("newDocumentButton");
const dropzone = document.getElementById("dropzone");
const uploadStatus = document.getElementById("uploadStatus");
const sessionTitle = document.getElementById("sessionTitle");
const summaryStats = document.getElementById("summaryStats");
const toast = document.getElementById("toast");
const mobileMenuButton = document.getElementById("mobileMenuButton");
const sidebar = document.getElementById("sidebar");

let currentDocument = null;
let toastTimer = null;

/* ============================================================
   UPLOAD
   ============================================================ */

fileInput.addEventListener("change", async () => {
    const files = Array.from(fileInput.files || []);

    if (files.length === 0) {
        return;
    }

    await uploadDocuments(files);
});

["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add("dragover");
    });
});

["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("dragover");
    });
});

dropzone.addEventListener("drop", async (event) => {
    const files = Array.from(event.dataTransfer?.files || []);

    if (files.length === 0) {
        return;
    }

    await uploadDocuments(files);
});

async function uploadDocuments(files) {
    const invalidFile = files.find((file) => {
        const typeLooksPdf = file.type === "application/pdf";
        const nameLooksPdf = file.name.toLowerCase().endsWith(".pdf");
        return !typeLooksPdf && !nameLooksPdf;
    });

    if (invalidFile) {
        showToast(`"${invalidFile.name}" is not a PDF file.`, true);
        fileInput.value = "";
        return;
    }

    setUploadProcessing(files.length);

    const formData = new FormData();

    files.forEach((file) => {
        formData.append("files", file);
    });

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await parseJsonResponse(response);

        if (!response.ok || !data.success) {
            throw new Error(
                data.error || "Document upload failed."
            );
        }

        currentDocument = data;

        renderDocumentList(data);
        renderSessionSummary(data);

        uploadCard.classList.add("hidden");
        chatContainer.classList.remove("hidden");

        messages.innerHTML = createWelcomeMessage(data);

        questionInput.focus();

        showToast(
            `${data.document_count || files.length} document${
                (data.document_count || files.length) !== 1 ? "s" : ""
            } processed successfully.`
        );

    } catch (error) {
        setUploadError(error.message);
        showToast(error.message, true);
    } finally {
        fileInput.value = "";
        closeMobileSidebar();
    }
}

function setUploadProcessing(count) {
    uploadStatus.hidden = false;
    uploadStatus.innerHTML = `
        <div class="loading-indicator">
            <span>Processing ${count} PDF${count !== 1 ? "s" : ""}…</span>
            <span class="loading-dots" aria-hidden="true">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
            </span>
        </div>
    `;
}

function setUploadError(message) {
    uploadStatus.hidden = false;
    uploadStatus.textContent = message;
    uploadStatus.style.color = "#a43c3c";
    uploadStatus.style.background = "#fff2f2";
}

/* ============================================================
   DOCUMENT UI
   ============================================================ */

function renderDocumentList(data) {
    const filenames = Array.isArray(data.filenames)
        ? data.filenames
        : data.filename
            ? [data.filename]
            : [];

    if (filenames.length === 0) {
        documentInfo.innerHTML = `
            <div class="document-empty">
                <span>No documents uploaded</span>
            </div>
        `;
        return;
    }

    documentInfo.innerHTML = filenames.map((filename) => `
        <div class="document-card">
            <div class="document-card-name">
                ${escapeHtml(filename)}
            </div>
            <div class="document-card-meta">
                Processed and searchable
            </div>
        </div>
    `).join("");
}

function renderSessionSummary(data) {
    const documentCount = Number(data.document_count || 0);
    const pages = Number(data.pages || 0);
    const chunks = Number(data.chunks || 0);

    sessionTitle.textContent =
        documentCount === 1
            ? "1 document ready for questions"
            : `${documentCount} documents ready for questions`;

    summaryStats.innerHTML = `
        <span class="stat-pill">
            ${documentCount} document${documentCount !== 1 ? "s" : ""}
        </span>
        <span class="stat-pill">
            ${pages} page${pages !== 1 ? "s" : ""}
        </span>
        <span class="stat-pill">
            ${chunks} chunk${chunks !== 1 ? "s" : ""}
        </span>
    `;
}

function createWelcomeMessage(data) {
    const count = Number(data.document_count || 0);

    return `
        <div class="welcome-message">
            <div class="assistant-avatar">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M7 8.5a5 5 0 0 1 10 0v3.7a5 5 0 0 1-10 0z"></path>
                    <path d="M5 12.5v-1a2 2 0 0 1 2-2M19 12.5v-1a2 2 0 0 0-2-2"></path>
                    <path d="M9 18.5h6M10 21h4"></path>
                </svg>
            </div>

            <div class="message-body">
                <div class="message-author">DocQuery</div>
                <h3>
                    ${count} document${count !== 1 ? "s are" : " is"} ready.
                </h3>
                <p>
                    Ask about facts, tables, comparisons, or specific sections.
                    Every answer is grounded in the uploaded documents.
                </p>
            </div>
        </div>
    `;
}

/* ============================================================
   NEW SESSION
   ============================================================ */

newDocumentButton.addEventListener("click", resetSession);

function resetSession() {
    currentDocument = null;

    fileInput.value = "";
    uploadStatus.hidden = true;
    uploadStatus.textContent = "";
    uploadStatus.style.color = "";
    uploadStatus.style.background = "";

    uploadCard.classList.remove("hidden");
    chatContainer.classList.add("hidden");

    documentInfo.innerHTML = `
        <div class="document-empty">
            <div class="document-empty-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 3.5h8.6L19 7.9V20.5H6z"></path>
                    <path d="M14 3.5v4.8h4.8"></path>
                </svg>
            </div>
            <span>No documents uploaded</span>
        </div>
    `;

    messages.innerHTML = "";
    sessionTitle.textContent = "Documents ready";

    summaryStats.innerHTML = `
        <span class="stat-pill">0 documents</span>
        <span class="stat-pill">0 pages</span>
        <span class="stat-pill">0 chunks</span>
    `;

    questionInput.value = "";

    closeMobileSidebar();
}

/* ============================================================
   ASK QUESTION
   ============================================================ */

questionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await askQuestion();
});

questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        questionForm.requestSubmit();
    }
});

questionInput.addEventListener("input", autoResizeTextarea);

async function askQuestion() {
    const question = questionInput.value.trim();

    if (!question) {
        return;
    }

    addUserMessage(question);
    questionInput.value = "";
    autoResizeTextarea();

    askButton.disabled = true;

    const loadingMessage = addLoadingMessage();

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question
            })
        });

        const data = await parseJsonResponse(response);

        loadingMessage.remove();

        if (!response.ok || !data.success) {
            addAIMessage(
                data.error || "The document assistant could not answer that question.",
                [],
                true
            );
            return;
        }

        addAIMessage(
            data.answer || "The model returned no answer.",
            Array.isArray(data.sources) ? data.sources : []
        );

    } catch (error) {
        loadingMessage.remove();

        addAIMessage(
            "Unable to connect to the document assistant. Make sure the server is running.",
            [],
            true
        );

    } finally {
        askButton.disabled = false;
        questionInput.focus();
    }
}

async function parseJsonResponse(response) {
    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
        throw new Error(
            `Server returned an unexpected response (${response.status}).`
        );
    }

    return await response.json();
}

/* ============================================================
   CHAT MESSAGES
   ============================================================ */

function addUserMessage(question) {
    const message = document.createElement("div");
    message.className = "user-message";

    message.innerHTML = `
        <div class="user-avatar">YOU</div>

        <div class="message-body">
            <div class="message-author">You</div>
            <div class="ai-answer">
                ${escapeHtml(question).replace(/\n/g, "<br>")}
            </div>
        </div>
    `;

    messages.appendChild(message);
    scrollToBottom();
}

function addAIMessage(answer, sources = [], isError = false) {
    const message = document.createElement("div");
    message.className = "ai-message";

    const answerClass = isError
        ? "ai-answer error-answer"
        : "ai-answer";

    const sourceHTML = sources.length > 0
        ? renderSources(sources)
        : "";

    message.innerHTML = `
        <div class="assistant-avatar">
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 8.5a5 5 0 0 1 10 0v3.7a5 5 0 0 1-10 0z"></path>
                <path d="M5 12.5v-1a2 2 0 0 1 2-2M19 12.5v-1a2 2 0 0 0-2-2"></path>
                <path d="M9 18.5h6M10 21h4"></path>
            </svg>
        </div>

        <div class="message-body">
            <div class="message-author">DocQuery</div>

            <div class="${answerClass}">
                ${formatAnswer(answer)}
            </div>

            ${sourceHTML}
        </div>
    `;

    messages.appendChild(message);
    scrollToBottom();
}

function addLoadingMessage() {
    const message = document.createElement("div");
    message.className = "ai-message";

    message.innerHTML = `
        <div class="assistant-avatar">
            <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 8.5a5 5 0 0 1 10 0v3.7a5 5 0 0 1-10 0z"></path>
                <path d="M5 12.5v-1a2 2 0 0 1 2-2M19 12.5v-1a2 2 0 0 0-2-2"></path>
                <path d="M9 18.5h6M10 21h4"></path>
            </svg>
        </div>

        <div class="message-body">
            <div class="message-author">DocQuery</div>

            <div class="loading-indicator">
                <span>Working with your documents</span>
                <span class="loading-dots" aria-hidden="true">
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                </span>
            </div>
        </div>
    `;

    messages.appendChild(message);
    scrollToBottom();

    return message;
}

/* ============================================================
   SOURCES
   ============================================================ */

function renderSources(sources) {
    const cards = sources.map((source) => {
        const type = source.type || "text";
        const documentName =
            source.document ||
            currentDocument?.filename ||
            "Unknown document";

        const page =
            source.page !== undefined &&
            source.page !== null
                ? String(source.page)
                : "N/A";

        const chunk =
            source.chunk_id !== undefined &&
            source.chunk_id !== null
                ? String(source.chunk_id)
                : "N/A";

        const hasScore =
            typeof source.score === "number" &&
            Number.isFinite(source.score);

        const relevance = hasScore
            ? `${(source.score * 100).toFixed(1)}%`
            : "N/A";

        return `
            <div class="source">
                <div class="source-main">
                    <span class="source-icon">
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M6 3.5h8.6L19 7.9V20.5H6z"></path>
                            <path d="M14 3.5v4.8h4.8"></path>
                            <path d="M8.7 13h6.6M8.7 16h5"></path>
                        </svg>
                    </span>

                    <div class="source-info">
                        <div class="source-document">
                            ${escapeHtml(documentName)}
                        </div>

                        <div class="source-page">
                            Page ${escapeHtml(page)}
                        </div>

                        <div class="source-meta">
                            <span>${escapeHtml(type)}</span>
                            <span>•</span>
                            <span>Chunk ${escapeHtml(chunk)}</span>
                        </div>
                    </div>
                </div>

                <div class="source-score">
                    <div class="score-label">Relevance</div>
                    <div class="score-value">${relevance}</div>
                </div>
            </div>
        `;
    }).join("");

    return `
        <div class="sources-title">
            <span>Sources &amp; citations</span>
            <span class="source-count">${sources.length}</span>
        </div>

        <div class="sources">
            ${cards}
        </div>
    `;
}

/* ============================================================
   ANSWER FORMATTING
   ============================================================ */

function formatAnswer(text) {
    const safe = escapeHtml(String(text || ""));

    const blocks = safe.split(/\n{2,}/);

    return blocks.map((block) => {
        const lines = block.split("\n");

        const isBulleted = lines.every((line) =>
            line.trim() === "" ||
            /^[-*]\s+/.test(line.trim())
        );

        if (isBulleted) {
            const items = lines
                .filter((line) => line.trim() !== "")
                .map((line) =>
                    `<li>${formatInline(
                        line.trim().replace(/^[-*]\s+/, "")
                    )}</li>`
                )
                .join("");

            return `<ul class="answer-list">${items}</ul>`;
        }

        const isNumbered = lines.every((line) =>
            line.trim() === "" ||
            /^\d+[.)]\s+/.test(line.trim())
        );

        if (isNumbered) {
            const items = lines
                .filter((line) => line.trim() !== "")
                .map((line) =>
                    `<li>${formatInline(
                        line.trim().replace(/^\d+[.)]\s+/, "")
                    )}</li>`
                )
                .join("");

            return `<ol class="answer-list">${items}</ol>`;
        }

        return lines
            .filter((line) => line.trim() !== "")
            .map((line) =>
                `<div class="answer-line">${formatInline(line)}</div>`
            )
            .join("");
    }).join("");
}

function formatInline(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
}

/* ============================================================
   HELPERS
   ============================================================ */

function autoResizeTextarea() {
    questionInput.style.height = "auto";

    const nextHeight = Math.min(
        questionInput.scrollHeight,
        150
    );

    questionInput.style.height = `${nextHeight}px`;
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        messages.scrollTop = messages.scrollHeight;
    });
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
}

function showToast(message, isError = false) {
    window.clearTimeout(toastTimer);

    toast.hidden = false;
    toast.textContent = message;
    toast.classList.toggle("error", Boolean(isError));

    toastTimer = window.setTimeout(() => {
        toast.hidden = true;
    }, 3500);
}

/* ============================================================
   MOBILE NAVIGATION
   ============================================================ */

mobileMenuButton.addEventListener("click", () => {
    sidebar.classList.toggle("open");
});

function closeMobileSidebar() {
    sidebar.classList.remove("open");
}

/* ============================================================
   INITIAL STATE
   ============================================================ */

autoResizeTextarea();
