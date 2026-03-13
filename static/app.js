/* ═══════════════════════════════════════════════════════════════════
   RETRO CODE BUILDER — Frontend (two-page spread + modal OCR)
   ═══════════════════════════════════════════════════════════════════ */

// ── State ────────────────────────────────────────────────────────

const state = {
    view: 'browser',
    issues: [],
    totalIssues: 0,
    searchQuery: '',
    searchPage: 1,
    issuesPerPage: 50,

    currentIssue: null,
    issueInfo: null,
    currentPage: 0,        // left page number (even)
    pageCount: 0,
    lastExtraction: null,
    editMode: false,
    showingRawText: false,
    modalOpen: false,
};

// ── DOM refs ─────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);

const dom = {
    browserView:    $('#browser-view'),
    viewerView:     $('#viewer-view'),
    issuesGrid:     $('#issues-grid'),
    pagination:     $('#pagination'),
    searchInput:    $('#search-input'),
    searchBtn:      $('#search-btn'),
    resetBtn:       $('#reset-btn'),
    backBtn:        $('#back-btn'),
    issueTitle:     $('#issue-title'),
    prevPage:       $('#prev-page'),
    nextPage:       $('#next-page'),
    pageInfo:       $('#page-info'),
    pageJump:       $('#page-jump'),
    jumpBtn:        $('#jump-btn'),
    ocrBtn:         $('#ocr-btn'),
    // Spread pages
    pageImageLeft:  $('#page-image-left'),
    pageLoadLeft:   $('#page-loading-left'),
    pageLabelLeft:  $('#page-left-label'),
    pageImageRight: $('#page-image-right'),
    pageLoadRight:  $('#page-loading-right'),
    pageLabelRight: $('#page-right-label'),
    // Modal
    modal:          $('#ocr-modal'),
    modalTitle:     $('#modal-title'),
    modalClose:     $('#modal-close'),
    modalBody:      $('#modal-body'),
    extractBtn:     $('#extract-btn'),
    rawTextBtn:     $('#raw-text-btn'),
    copyBtn:        $('#copy-btn'),
    editBtn:        $('#edit-btn'),
    extractPages:   $('#extract-pages'),
    codeEditor:     $('#code-editor'),
    status:         $('#status'),
};

// ── API helpers ──────────────────────────────────────────────────

async function api(path) {
    const resp = await fetch(path);
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`API ${resp.status}: ${text}`);
    }
    return resp.json();
}

function setStatus(msg) {
    dom.status.textContent = msg;
}

function showToast(msg, isError = false) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' error' : '');
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ── View switching ───────────────────────────────────────────────

function showView(name) {
    state.view = name;
    dom.browserView.classList.toggle('active', name === 'browser');
    dom.viewerView.classList.toggle('active', name === 'viewer');
}

// ── Issue Browser ────────────────────────────────────────────────

async function loadIssues(query = '', page = 1) {
    setStatus('SEARCHING INTERNET ARCHIVE...');
    dom.issuesGrid.innerHTML = '<div class="loading">SEARCHING ARCHIVE...</div>';

    try {
        const data = await api(
            `/api/issues?q=${encodeURIComponent(query)}&page=${page}&limit=${state.issuesPerPage}`
        );
        state.issues = data.issues;
        state.totalIssues = data.total;
        state.searchQuery = query;
        state.searchPage = page;

        renderIssues();
        renderPagination();
        setStatus(`FOUND ${data.total} ISSUES`);
    } catch (err) {
        dom.issuesGrid.innerHTML = `<div class="loading" style="color:var(--red)">
            ERROR: ${err.message}</div>`;
        setStatus('ERROR');
    }
}

function renderIssues() {
    if (!state.issues.length) {
        dom.issuesGrid.innerHTML = '<div class="loading">NO ISSUES FOUND</div>';
        return;
    }

    dom.issuesGrid.innerHTML = state.issues.map(issue => {
        const id = issue.identifier;
        const title = issue.title || id;
        const date = formatDate(issue.date);
        const thumb = `https://archive.org/services/img/${id}`;

        return `
            <div class="issue-card" data-id="${id}" onclick="openIssue('${id}')">
                <img src="${thumb}" alt="${title}" loading="lazy">
                <div class="issue-date">${date}</div>
                <div class="issue-name">${title}</div>
            </div>
        `;
    }).join('');
}

function renderPagination() {
    const totalPages = Math.ceil(state.totalIssues / state.issuesPerPage);
    if (totalPages <= 1) {
        dom.pagination.innerHTML = '';
        return;
    }

    let html = '';
    const current = state.searchPage;

    if (current > 1) {
        html += `<button class="retro-btn" onclick="loadIssues('${state.searchQuery}', ${current - 1})">&lt; PREV</button>`;
    }
    html += `<span class="page-info">PAGE ${current}/${totalPages}</span>`;
    if (current < totalPages) {
        html += `<button class="retro-btn" onclick="loadIssues('${state.searchQuery}', ${current + 1})">NEXT &gt;</button>`;
    }

    dom.pagination.innerHTML = html;
}

function formatDate(dateStr) {
    if (!dateStr) return '???';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
    } catch {
        return dateStr.substring(0, 7);
    }
}

// ── Issue Viewer (two-page spread) ───────────────────────────────

async function openIssue(identifier) {
    setStatus(`LOADING ${identifier}...`);
    state.currentIssue = identifier;
    state.currentPage = 0;
    state.lastExtraction = null;
    state.editMode = false;
    state.showingRawText = false;

    try {
        const info = await api(`/api/issue/${identifier}`);
        state.issueInfo = info;
        state.pageCount = info.page_count;

        dom.issueTitle.textContent = info.title;
        dom.pageJump.max = info.page_count - 1;

        showView('viewer');
        loadSpread(0);
        setStatus('READY');
    } catch (err) {
        showToast('Failed to load issue: ' + err.message, true);
        setStatus('ERROR');
    }
}

// Book spread logic:
//   Page 0 = cover, displayed solo on the right
//   Then pairs: 1-2, 3-4, 5-6, ...
// We store state.currentPage as the first page shown in the spread.

function spreadFor(page) {
    // Given any page number, return [leftPage, rightPage] for the spread.
    // Cover (page 0): left=null, right=0
    // After that, odd pages are left: 1-2, 3-4, 5-6, ...
    if (page <= 0) return [null, 0];
    // Snap to the odd page that starts the pair
    const left = (page % 2 === 1) ? page : page - 1;
    const right = left + 1;
    return [left, right];
}

function prevSpread() {
    if (state.currentPage <= 0) return;
    if (state.currentPage <= 1) {
        // Go back to cover
        loadSpread(0);
    } else {
        // Current left is an odd number; previous pair's left is currentPage - 2
        loadSpread(state.currentPage - 2);
    }
}

function nextSpread() {
    if (state.currentPage === 0) {
        // From cover, go to first pair (1-2)
        loadSpread(1);
    } else {
        loadSpread(state.currentPage + 2);
    }
}

function loadSpread(startPage) {
    startPage = Math.max(0, startPage);
    if (startPage >= state.pageCount) return;

    const [leftPage, rightPage] = spreadFor(startPage);
    state.currentPage = leftPage !== null ? leftPage : 0;

    // Update nav
    const maxPage = state.pageCount - 1;
    const atEnd = (rightPage !== null ? rightPage : 0) >= maxPage;
    dom.prevPage.disabled = (state.currentPage <= 0);
    dom.nextPage.disabled = atEnd;

    if (leftPage === null) {
        // Cover: solo right
        dom.pageInfo.textContent = `COVER (PAGE 0) / ${maxPage}`;
        dom.pageJump.value = 0;
    } else {
        const rp = Math.min(rightPage, maxPage);
        dom.pageInfo.textContent = `PAGES ${leftPage}-${rp} / ${maxPage}`;
        dom.pageJump.value = leftPage;
    }

    const leftPanel = dom.pageImageLeft.closest('.spread-page');
    const rightPanel = dom.pageImageRight.closest('.spread-page');

    if (leftPage === null) {
        // Cover — hide left panel, show right with cover image
        leftPanel.style.display = 'none';
        rightPanel.style.display = '';
        loadPageImage(0, dom.pageImageRight, dom.pageLoadRight, dom.pageLabelRight);
        dom.pageLabelRight.textContent = 'COVER';
    } else {
        // Normal two-page spread
        leftPanel.style.display = '';
        loadPageImage(leftPage, dom.pageImageLeft, dom.pageLoadLeft, dom.pageLabelLeft);

        if (rightPage < state.pageCount) {
            rightPanel.style.display = '';
            loadPageImage(rightPage, dom.pageImageRight, dom.pageLoadRight, dom.pageLabelRight);
        } else {
            rightPanel.style.display = 'none';
        }
    }
}

function loadPageImage(pageNum, imgEl, loadingEl, labelEl) {
    labelEl.textContent = `PAGE ${pageNum}`;
    imgEl.classList.add('hidden');
    loadingEl.classList.remove('hidden');
    loadingEl.textContent = 'LOADING...';
    loadingEl.style.color = '';

    const imgUrl = `/api/issue/${state.currentIssue}/page/${pageNum}/image`;
    imgEl.onload = () => {
        imgEl.classList.remove('hidden');
        loadingEl.classList.add('hidden');
    };
    imgEl.onerror = () => {
        loadingEl.textContent = 'FAILED TO LOAD';
        loadingEl.style.color = 'var(--red)';
    };
    imgEl.src = imgUrl;
}

// ── Modal ────────────────────────────────────────────────────────

function openModal() {
    state.modalOpen = true;
    dom.modal.classList.remove('hidden');
    const [lp, rp] = spreadFor(state.currentPage);
    const label = lp === null ? 'COVER' : `PAGES ${lp}-${rp}`;
    dom.modalTitle.textContent = `CODE EXTRACTION — ${label}`;
    // Reset state
    dom.modalBody.classList.remove('hidden');
    dom.codeEditor.classList.add('hidden');
    state.editMode = false;
    state.showingRawText = false;

    if (!state.lastExtraction) {
        dom.modalBody.innerHTML = `<div class="placeholder">
PRESS EXTRACT CODE TO SCAN THE
CURRENT PAGES FOR BASIC LISTINGS.

ADJUST PAGE COUNT TO SCAN MORE
OR FEWER PAGES AT ONCE.</div>`;
    }
}

function closeModal() {
    state.modalOpen = false;
    dom.modal.classList.add('hidden');
}

// ── Code extraction ──────────────────────────────────────────────

async function extractCode() {
    if (!state.currentIssue) return;

    const numPages = parseInt(dom.extractPages.value, 10) || 3;
    setStatus('EXTRACTING CODE...');
    dom.modalBody.innerHTML = '<div class="loading">SCANNING FOR CODE LISTINGS...</div>';
    dom.modalBody.classList.remove('hidden');
    dom.codeEditor.classList.add('hidden');
    state.editMode = false;

    try {
        const data = await api(
            `/api/issue/${state.currentIssue}/page/${state.currentPage}/extract?num_pages=${numPages}`
        );
        state.lastExtraction = data;

        if (data.listings.length === 0) {
            dom.modalBody.innerHTML = `<div class="placeholder">
NO CODE LISTINGS DETECTED ON PAGES ${data.pages_scanned.join(', ')}

TRY NAVIGATING TO A PAGE WITH A
PROGRAM LISTING AND EXTRACT AGAIN.

PLATFORM DETECTED: ${data.platform}</div>`;
            setStatus(`NO LISTINGS FOUND (SCANNED ${data.pages_scanned.length} PAGES)`);
        } else {
            renderListings(data.listings);
            setStatus(`FOUND ${data.listings.length} LISTING(S) — ${data.platform}`);
        }
    } catch (err) {
        dom.modalBody.innerHTML = `<div class="loading" style="color:var(--red)">
            EXTRACTION ERROR: ${err.message}</div>`;
        setStatus('ERROR');
    }
}

function renderListings(listings) {
    dom.modalBody.innerHTML = listings.map((listing, i) => `
        <div class="listing-block" data-index="${i}">
            <div class="listing-header">
                <span class="listing-title">LISTING ${i + 1} — LINES ${listing.first_line}-${listing.last_line}</span>
                <span class="listing-meta">${listing.line_count} lines | ${listing.platform}</span>
            </div>
            <div class="listing-code">${escapeHtml(listing.cleaned || listing.code)}</div>
            <div class="listing-actions">
                <button class="retro-btn" onclick="copyListing(${i})">COPY</button>
                <button class="retro-btn" onclick="editListing(${i})">EDIT</button>
                <button class="retro-btn" onclick="showOriginal(${i})">ORIGINAL</button>
            </div>
        </div>
    `).join('');
}

function copyListing(index) {
    if (!state.lastExtraction) return;
    const listing = state.lastExtraction.listings[index];
    const code = listing.cleaned || listing.code;
    navigator.clipboard.writeText(code).then(() => {
        showToast('CODE COPIED TO CLIPBOARD');
    }).catch(() => {
        showToast('COPY FAILED', true);
    });
}

function editListing(index) {
    if (!state.lastExtraction) return;
    const listing = state.lastExtraction.listings[index];
    dom.codeEditor.value = listing.cleaned || listing.code;
    dom.modalBody.classList.add('hidden');
    dom.codeEditor.classList.remove('hidden');
    state.editMode = true;
    dom.codeEditor.focus();
}

function showOriginal(index) {
    if (!state.lastExtraction) return;
    const listing = state.lastExtraction.listings[index];
    const block = document.querySelector(`.listing-block[data-index="${index}"] .listing-code`);
    if (block) {
        const isOriginal = block.dataset.showOriginal === 'true';
        block.textContent = isOriginal ? (listing.cleaned || listing.code) : listing.code;
        block.dataset.showOriginal = isOriginal ? 'false' : 'true';
    }
}

async function showRawText() {
    if (!state.currentIssue) return;

    if (state.showingRawText) {
        if (state.lastExtraction) {
            renderListings(state.lastExtraction.listings);
        } else {
            dom.modalBody.innerHTML = '<div class="placeholder">PRESS EXTRACT CODE TO BEGIN</div>';
        }
        state.showingRawText = false;
        dom.modalBody.classList.remove('hidden');
        dom.codeEditor.classList.add('hidden');
        return;
    }

    setStatus('LOADING OCR TEXT...');
    dom.modalBody.innerHTML = '<div class="loading">LOADING OCR TEXT...</div>';
    dom.modalBody.classList.remove('hidden');
    dom.codeEditor.classList.add('hidden');
    state.editMode = false;

    try {
        // Get text for both visible pages
        const left = await api(`/api/issue/${state.currentIssue}/page/${state.currentPage}/text`);
        let combined = left.text || '';

        const rightPage = state.currentPage + 1;
        if (rightPage < state.pageCount) {
            const right = await api(`/api/issue/${state.currentIssue}/page/${rightPage}/text`);
            if (right.text) {
                combined += '\n\n── PAGE ' + rightPage + ' ──\n\n' + right.text;
            }
        }

        if (combined.trim()) {
            dom.modalBody.innerHTML = `<div class="raw-text">${escapeHtml(combined)}</div>`;
            state.showingRawText = true;
            setStatus('SHOWING RAW OCR TEXT');
        } else {
            dom.modalBody.innerHTML = '<div class="placeholder">NO OCR TEXT AVAILABLE FOR THESE PAGES</div>';
            setStatus('NO OCR TEXT');
        }
    } catch (err) {
        dom.modalBody.innerHTML = `<div class="loading" style="color:var(--red)">
            ERROR: ${err.message}</div>`;
        setStatus('ERROR');
    }
}

function copyCurrentCode() {
    let code = '';
    if (state.editMode) {
        code = dom.codeEditor.value;
    } else if (state.lastExtraction && state.lastExtraction.listings.length > 0) {
        code = state.lastExtraction.listings.map(l => l.cleaned || l.code).join('\n\n');
    }

    if (code) {
        navigator.clipboard.writeText(code).then(() => {
            showToast('COPIED TO CLIPBOARD');
        }).catch(() => {
            showToast('COPY FAILED', true);
        });
    } else {
        showToast('NOTHING TO COPY', true);
    }
}

function toggleEdit() {
    if (state.editMode) {
        dom.codeEditor.classList.add('hidden');
        dom.modalBody.classList.remove('hidden');
        state.editMode = false;
    } else {
        let code = '';
        if (state.lastExtraction && state.lastExtraction.listings.length > 0) {
            code = state.lastExtraction.listings.map(l => l.cleaned || l.code).join('\n\n');
        }
        dom.codeEditor.value = code;
        dom.modalBody.classList.add('hidden');
        dom.codeEditor.classList.remove('hidden');
        state.editMode = true;
        dom.codeEditor.focus();
    }
}

// ── Utilities ────────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Event wiring ─────────────────────────────────────────────────

function init() {
    // Search
    dom.searchBtn.addEventListener('click', () => {
        loadIssues(dom.searchInput.value.trim());
    });
    dom.searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loadIssues(dom.searchInput.value.trim());
    });
    dom.resetBtn.addEventListener('click', () => {
        dom.searchInput.value = '';
        loadIssues();
    });

    // Viewer navigation
    dom.backBtn.addEventListener('click', () => {
        showView('browser');
        setStatus('READY');
    });
    dom.prevPage.addEventListener('click', prevSpread);
    dom.nextPage.addEventListener('click', nextSpread);

    dom.jumpBtn.addEventListener('click', () => {
        const p = parseInt(dom.pageJump.value, 10);
        if (!isNaN(p)) loadSpread(p);
    });
    dom.pageJump.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const p = parseInt(dom.pageJump.value, 10);
            if (!isNaN(p)) loadSpread(p);
        }
    });

    // OCR modal
    dom.ocrBtn.addEventListener('click', openModal);
    dom.modalClose.addEventListener('click', closeModal);
    dom.modal.addEventListener('click', (e) => {
        if (e.target === dom.modal) closeModal();
    });

    // Modal tools
    dom.extractBtn.addEventListener('click', extractCode);
    dom.rawTextBtn.addEventListener('click', showRawText);
    dom.copyBtn.addEventListener('click', copyCurrentCode);
    dom.editBtn.addEventListener('click', toggleEdit);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Escape closes modal
        if (e.key === 'Escape' && state.modalOpen) {
            closeModal();
            return;
        }

        // Don't intercept when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        if (state.modalOpen) return; // no page nav while modal open

        if (state.view !== 'viewer') return;

        if (e.key === 'ArrowLeft' || e.key === 'a') {
            prevSpread();
        } else if (e.key === 'ArrowRight' || e.key === 'd') {
            nextSpread();
        } else if (e.key === 'e' || e.key === 'c') {
            openModal();
        }
    });

    // Load initial issues
    loadIssues();
}

// Globals for onclick handlers in rendered HTML
window.openIssue = openIssue;
window.copyListing = copyListing;
window.editListing = editListing;
window.showOriginal = showOriginal;
window.loadIssues = loadIssues;

document.addEventListener('DOMContentLoaded', init);
