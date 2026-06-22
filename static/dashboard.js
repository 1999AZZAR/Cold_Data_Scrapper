/*
Copyright (c) 2026 Azzar Budiyanto / LilyOpenCMS.
All rights reserved.

Contact: azzar.mr.zs@gmail.com for inquiries.
*/
/**
 * Cold Data Scrapper (CDS) Frontend Logic
 * Connects index.html elements with Flask REST endpoints.
 */

// Load data on page launch
document.addEventListener("DOMContentLoaded", () => {
    loadStatus();
    loadRuns();
    
    // Initialize page size from DOM
    const sizeSelect = document.getElementById("page-size-select");
    if (sizeSelect) {
        const val = sizeSelect.value;
        pageSize = val === "all" ? 999999 : parseInt(val);
    }
    
    loadLeads();
    
    // Poll system status every 10 seconds
    setInterval(loadStatus, 10000);
    
    // Bind search bar filter
    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", debounce(loadLeads, 400));
    
    // Bind form submission
    const extractForm = document.getElementById("extract-form");
    extractForm.addEventListener("submit", triggerExtraction);
});

// Debounce helper for search filtering
function debounce(func, delay) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

// Custom Toast notification system
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    
    const toast = document.createElement("div");
    toast.className = `p-3.5 rounded border shadow-md transition duration-300 transform translate-x-full opacity-0 flex justify-between items-center gap-3 max-w-sm pointer-events-auto`;
    
    let bgClass = "bg-white border-[#babfc3] text-[#202223]";
    let icon = '<i class="fa-solid fa-info-circle text-[#006fbb] text-sm"></i>';
    
    if (type === "success") {
        bgClass = "bg-[#e3f1df] border-[#aee9d1] text-[#108043]";
        icon = '<i class="fa-solid fa-circle-check text-[#108043] text-sm"></i>';
    } else if (type === "error") {
        bgClass = "bg-[#fedcdb] border-[#ffc4c2] text-[#bf0711]";
        icon = '<i class="fa-solid fa-circle-exclamation text-[#bf0711] text-sm"></i>';
    }
    
    toast.className += ` ${bgClass}`;
    toast.innerHTML = `
        <div class="flex items-center gap-2.5">
            ${icon}
            <span class="font-sans text-[11px] font-bold tracking-tight">${message}</span>
        </div>
        <button class="text-slate-400 hover:text-slate-900 transition flex items-center justify-center p-1 hover:bg-slate-100 rounded" onclick="this.parentElement.remove()">
            <i class="fa-solid fa-times text-[10px]"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // Trigger entrance animation
    setTimeout(() => {
        toast.classList.remove("translate-x-full", "opacity-0");
    }, 10);
    
    // Automatically remove after 4 seconds
    setTimeout(() => {
        toast.classList.add("translate-x-full", "opacity-0");
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Fetch system health & counts
async function loadStatus() {
    try {
        const response = await fetch("/api/status");
        const status = await response.json();
        
        if (status.db_healthy) {
            document.getElementById("stat-clean").textContent = status.total_clean_leads;
            document.getElementById("stat-duplicates").textContent = status.total_duplicates;
            document.getElementById("stat-runs").textContent = status.total_runs;
            document.getElementById("sys-load").textContent = `Load: ${status.cpu_load.toFixed(2)}`;
        }
    } catch (e) {
        console.error("Failed to load status:", e);
    }
}

// Fetch scraper runs history
async function loadRuns() {
    try {
        const response = await fetch("/api/runs");
        const runs = await response.json();
        
        const tbody = document.getElementById("runs-tbody");
        const runFilter = document.getElementById("run-filter");
        
        const selectedFilterVal = runFilter.value;
        
        tbody.innerHTML = "";
        runFilter.innerHTML = '<option value="">All Scraper Runs</option>';
        
        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-neutral-400">No runs triggered yet.</td></tr>';
            return;
        }
        
        runs.forEach(run => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50/50 transition-colors duration-150";
            tr.innerHTML = `
                <td class="p-3 border-b border-slate-100 font-bold text-slate-800">#${run.id}</td>
                <td class="p-3 border-b border-slate-100 font-semibold text-slate-900">${escapeHtml(run.query)}</td>
                <td class="p-3 border-b border-slate-100 text-slate-600">${escapeHtml(run.region)}</td>
                <td class="p-3 border-b border-slate-100">
                    <span class="px-2.5 py-0.5 text-[9px] tracking-wide uppercase font-bold rounded-full border ${
                        run.status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-200/50' :
                        run.status === 'running' ? 'bg-blue-50 text-blue-700 border-blue-200/50 animate-pulse' :
                        'bg-rose-50 text-rose-700 border-rose-200/50'
                    }">${run.status}</span>
                </td>
                <td class="p-3 border-b border-slate-100 text-slate-700 font-semibold">${run.results_count} leads</td>
                <td class="p-3 border-b border-slate-100 text-slate-400 font-sans">${run.created_at}</td>
                <td class="p-3 border-b border-slate-100 font-mono text-[10px]">
                    <div class="flex items-center gap-2">
                        <button onclick="event.stopPropagation(); rerunRun(${run.id})" class="text-indigo-600 hover:text-indigo-800 font-bold hover:underline transition duration-150">
                            <i class="fa-solid fa-rotate-right mr-0.5"></i>Rerun
                        </button>
                        <span class="text-slate-300">|</span>
                        <a href="/api/export?run_id=${run.id}&format=csv" onclick="event.stopPropagation();" class="text-emerald-600 hover:text-emerald-800 font-bold hover:underline transition duration-150">
                            <i class="fa-solid fa-file-csv mr-0.5"></i>CSV
                        </a>
                        <span class="text-slate-300">|</span>
                        <a href="/api/export?run_id=${run.id}&format=xml" onclick="event.stopPropagation();" class="text-blue-600 hover:text-blue-800 font-bold hover:underline transition duration-150">
                            <i class="fa-solid fa-code mr-0.5"></i>XML
                        </a>
                        <span class="text-slate-300">|</span>
                        <button onclick="event.stopPropagation(); deleteRun(${run.id})" class="text-rose-500 hover:text-rose-700 font-bold hover:underline transition duration-150">
                            <i class="fa-solid fa-trash-can mr-0.5"></i>Delete
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
            
            const option = document.createElement("option");
            option.value = run.id;
            option.textContent = `Run #${run.id}: ${run.query} in ${run.region}`;
            runFilter.appendChild(option);
        });
        
        runFilter.value = selectedFilterVal;
    } catch (e) {
        console.error("Failed to load runs history:", e);
    }
}

// Delete a specific run and its leads
async function deleteRun(runId) {
    showConfirm(
        "Delete Scraper Run",
        `Are you sure you want to delete Run #${runId} and all its associated leads data? This cannot be undone.`,
        async () => {
            try {
                const response = await fetch(`/api/runs/${runId}`, {
                    method: "DELETE"
                });
                const res = await response.json();
                
                if (res.status === "success") {
                    showToast(`Run #${runId} and its data deleted successfully.`, "success");
                    loadStatus();
                    loadRuns();
                    loadLeads();
                } else {
                    showToast(`Error: ${res.error}`, "error");
                }
            } catch (err) {
                showToast(`Failed to delete run: ${err}`, "error");
            }
        }
    );
}

// Rerun a specific run
function rerunRun(runId) {
    const rerunModal = document.getElementById("rerun-modal");
    const rerunLimit = document.getElementById("rerun-limit");
    const submitBtn = document.getElementById("rerun-submit-btn");
    
    if (rerunModal && rerunLimit && submitBtn) {
        rerunLimit.value = "";
        
        submitBtn.onclick = async () => {
            const limitVal = rerunLimit.value;
            const limit = limitVal ? parseInt(limitVal) : null;
            const reuseSearch = document.getElementById("rerun-reuse-search").checked;
            
            try {
                const response = await fetch(`/api/runs/${runId}/rerun`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ limit, reuse_search: reuseSearch })
                });
                const res = await response.json();
                
                if (res.status === "started") {
                    showToast(`Scraper rerun (ID #${res.run_id}) started in the background!`, "success");
                    loadRuns();
                    loadStatus();
                    
                    const currentFilter = document.getElementById("run-filter").value;
                    if (currentFilter == runId) {
                        loadLeads();
                    }
                } else {
                    showToast(`Error: ${res.error}`, "error");
                }
            } catch (err) {
                showToast(`Failed to trigger rerun: ${err}`, "error");
            }
        };
        
        rerunModal.classList.remove("hidden");
    }
}

function closeRerunModal() {
    const rerunModal = document.getElementById("rerun-modal");
    if (rerunModal) {
        rerunModal.classList.add("hidden");
    }
}

// Fetch leads list
let currentLeads = [];
let currentPage = 1;
let pageSize = 15;

async function loadLeads() {
    const runId = document.getElementById("run-filter").value;
    const search = document.getElementById("search-input").value;
    const showDuplicates = document.getElementById("dup-checkbox").checked;
    
    let url = `/api/leads?duplicates=${showDuplicates}`;
    if (runId) url += `&run_id=${runId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    
    try {
        const response = await fetch(url);
        currentLeads = await response.json();
        currentPage = 1; // Reset to first page when filter changes
        
        renderLeadsTable();
    } catch (e) {
        console.error("Failed to load leads:", e);
    }
}

function renderLeadsTable() {
    const tbody = document.getElementById("leads-tbody");
    const countSpan = document.getElementById("lead-count");
    
    if (!tbody || !countSpan) return;
    
    countSpan.textContent = `${currentLeads.length} items`;
    tbody.innerHTML = "";
    
    if (currentLeads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="p-8 text-center text-neutral-400 font-mono">No matching records found.</td></tr>';
        updatePaginationControls(0);
        return;
    }
    
    const totalItems = currentLeads.length;
    const totalPages = Math.ceil(totalItems / pageSize);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    
    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, totalItems);
    const pageLeads = currentLeads.slice(startIdx, endIdx);
    
    pageLeads.forEach((lead, index) => {
        const actualIndex = startIdx + index;
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50/60 cursor-pointer transition-colors duration-150";
        tr.onclick = () => openModal(actualIndex);
        
        const phoneBadge = lead.phone ? `<span class="inline-flex items-center text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-[9px] border border-emerald-100/80 font-bold font-mono"><i class="fa-solid fa-phone mr-1 text-[8px]"></i>Phone</span>` : `<span class="text-slate-300 font-mono">-</span>`;
        const emailBadge = lead.email ? `<span class="inline-flex items-center text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-[9px] border border-blue-100/80 font-bold font-mono"><i class="fa-solid fa-envelope mr-1 text-[8px]"></i>Email</span>` : `<span class="text-slate-300 font-mono">-</span>`;
        const webLink = lead.website ? `<a href="${lead.website}" target="_blank" onclick="event.stopPropagation();" class="text-slate-800 hover:text-indigo-600 font-mono font-semibold transition duration-150 flex items-center gap-1"><i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i>Link</a>` : '<span class="text-slate-300">-</span>';
        
        let ratingBadge = '-';
        if (lead.rating != null) {
            const stars = '★'.repeat(Math.round(lead.rating)) + '☆'.repeat(5 - Math.round(lead.rating));
            const reviewLabel = lead.review_count != null ? `<span class="text-slate-400 font-normal">(${lead.review_count})</span>` : '';
            ratingBadge = `<span class="inline-flex items-center gap-1 font-mono text-[10px]"><span class="text-amber-500">${stars}</span> <span class="font-bold">${lead.rating}</span> ${reviewLabel}</span>`;
        }
        
        let socialBadges = [];
        if (lead.instagram) socialBadges.push(`<i class="fa-brands fa-instagram text-indigo-500 text-sm" title="Instagram present"></i>`);
        if (lead.facebook) socialBadges.push(`<i class="fa-brands fa-facebook text-blue-600 text-sm" title="Facebook present"></i>`);
        if (lead.whatsapp) socialBadges.push(`<i class="fa-brands fa-whatsapp text-emerald-500 text-sm" title="WhatsApp link active"></i>`);
        const socialString = socialBadges.length > 0 ? `<div class="flex gap-2">${socialBadges.join("")}</div>` : '<span class="text-slate-300">-</span>';
        
        const score = lead.opportunity_score || 0;
        let scoreClass = "";
        if (score >= 70) {
            scoreClass = "bg-[#fedcdb] text-[#bf0711] border-[#ffc4c2]";
        } else if (score >= 40) {
            scoreClass = "bg-[#fcf1cd] text-[#9c6f1a] border-[#ffe5b4]";
        } else {
            scoreClass = "bg-[#e3f1df] text-[#108043] border-[#aee9d1]";
        }
        const scoreBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] border font-bold font-mono ${scoreClass}">${score}</span>`;

        const isMerged = lead.source && lead.source.includes(",");
        const sourceBadge = isMerged
            ? `<span class="px-1.5 py-0.5 bg-indigo-50 text-[8px] font-bold font-mono text-indigo-600 rounded border border-indigo-100/80 uppercase" title="Merged from OSM & GMaps">Merged</span>`
            : `<span class="px-1.5 py-0.5 bg-slate-50 text-[8px] font-bold font-mono text-slate-500 rounded border border-slate-200/60 uppercase">${lead.source || 'unknown'}</span>`;

        tr.innerHTML = `
            <td class="p-3 font-semibold text-slate-900 border-b border-slate-100">
                <div class="flex flex-wrap items-center gap-1.5">
                    <span>${escapeHtml(lead.name)}</span>
                    ${sourceBadge}
                    ${lead.duplicate_of ? `<span class="px-2 py-0.5 bg-slate-100 text-[9px] font-bold font-mono text-slate-500 rounded border border-slate-200/60">Dup of #${lead.duplicate_of}</span>` : ''}
                </div>
            </td>
            <td class="p-3 border-b border-slate-100 capitalize font-mono text-[10px] text-slate-500">${escapeHtml(lead.category)}</td>
            <td class="p-3 border-b border-slate-100"><div class="flex gap-1.5">${phoneBadge}${emailBadge}</div></td>
            <td class="p-3 border-b border-slate-100">${webLink}</td>
            <td class="p-3 border-b border-slate-100">${ratingBadge}</td>
            <td class="p-3 border-b border-slate-100">${socialString}</td>
            <td class="p-3 border-b border-slate-100">${scoreBadge}</td>
            <td class="p-3 border-b border-slate-100 font-mono text-[10px]">
                <button class="text-slate-900 hover:underline uppercase tracking-wider font-bold transition">View</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    
    updatePaginationControls(totalPages);
}

function updatePaginationControls(totalPages) {
    const prevBtn = document.getElementById("prev-page-btn");
    const nextBtn = document.getElementById("next-page-btn");
    const pageInfo = document.getElementById("page-info");
    
    if (!prevBtn || !nextBtn || !pageInfo) return;
    
    if (totalPages <= 1) {
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        pageInfo.textContent = `Page 1 of ${totalPages || 1}`;
    } else {
        prevBtn.disabled = (currentPage === 1);
        nextBtn.disabled = (currentPage === totalPages);
        pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    }
}

function changePageSize() {
    const sizeSelect = document.getElementById("page-size-select");
    if (sizeSelect) {
        const val = sizeSelect.value;
        pageSize = val === "all" ? 999999 : parseInt(val);
        currentPage = 1;
        renderLeadsTable();
    }
}



function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderLeadsTable();
        const tableContainer = document.getElementById("leads-table-container");
        if (tableContainer) tableContainer.scrollTop = 0;
    }
}

function nextPage() {
    const totalPages = Math.ceil(currentLeads.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderLeadsTable();
        const tableContainer = document.getElementById("leads-table-container");
        if (tableContainer) tableContainer.scrollTop = 0;
    }
}

// Trigger new POI extraction
async function triggerExtraction(e) {
    e.preventDefault();
    
    const query = document.getElementById("extract-query").value;
    const region = document.getElementById("extract-region").value;
    const limit = document.getElementById("extract-limit").value;
    const btn = document.getElementById("extract-btn");
    const btnText = document.getElementById("btn-text");
    
    btn.disabled = true;
    btnText.textContent = "Launching Scraper...";
    btn.classList.add("opacity-50", "cursor-not-allowed");
    
    const reuseSearch = document.getElementById("extract-reuse-search").checked;
    
    try {
        const response = await fetch("/api/trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, region, limit: limit ? parseInt(limit) : null, reuse_search: reuseSearch })
        });
        const res = await response.json();
        
        if (res.status === "started") {
            showToast(`POI Scraper Run ID #${res.run_id} started in the background!`, "success");
            document.getElementById("extract-query").value = "";
            document.getElementById("extract-region").value = "";
            loadRuns();
            loadStatus();
        } else {
            showToast(`Error: ${res.error}`, "error");
        }
    } catch (err) {
        showToast(`Error triggering scraper: ${err}`, "error");
    } finally {
        btn.disabled = false;
        btnText.textContent = "Extract POI Data";
        btn.classList.remove("opacity-50", "cursor-not-allowed");
    }
}

// Trigger separate utilities
async function triggerAction(actionName) {
    showToast(`Triggered pipeline stage: ${actionName.toUpperCase()}`, "info");
    try {
        const response = await fetch("/api/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: actionName })
        });
        const res = await response.json();
        
        if (res.status === "started") {
            showToast(`Action '${actionName.toUpperCase()}' running asynchronously!`, "success");
            setTimeout(() => {
                loadStatus();
                loadLeads();
            }, 3000);
        } else {
            showToast(`Error: ${res.error}`, "error");
        }
    } catch (err) {
        showToast(`Failed to trigger action: ${err}`, "error");
    }
}

// Modal open/close handlers
function openModal(index) {
    const lead = currentLeads[index];
    if (!lead) return;
    
    document.getElementById("modal-source").textContent = `${lead.source.toUpperCase()} ID: ${lead.source_id}`;
    document.getElementById("modal-name").textContent = lead.name;
    document.getElementById("modal-category").textContent = lead.category;
    document.getElementById("modal-address").textContent = lead.address || "No address tags available";
    document.getElementById("modal-phone").textContent = lead.phone || "-";
    document.getElementById("modal-email").textContent = lead.email || "-";
    document.getElementById("modal-hours").textContent = lead.opening_hours || "-";
    document.getElementById("modal-lat").textContent = lead.latitude || "-";
    document.getElementById("modal-lon").textContent = lead.longitude || "-";
    document.getElementById("modal-price").textContent = lead.price_range || "Not specified";
    
    // Rating
    const modalRating = document.getElementById("modal-rating");
    const modalReviewCount = document.getElementById("modal-review-count");
    if (lead.rating != null) {
        const stars = '★'.repeat(Math.round(lead.rating)) + '☆'.repeat(5 - Math.round(lead.rating));
        modalRating.textContent = `${stars} ${lead.rating}`;
        modalReviewCount.textContent = lead.review_count != null ? `(${lead.review_count} reviews)` : '';
    } else {
        modalRating.textContent = '-';
        modalReviewCount.textContent = '';
    }
    
    // Render map preview using OpenStreetMap embed
    const mapContainer = document.getElementById("modal-map-container");
    const mapIframe = document.getElementById("modal-map-iframe");
    if (mapContainer && mapIframe) {
        const lat = parseFloat(lead.latitude);
        const lon = parseFloat(lead.longitude);
        if (!isNaN(lat) && !isNaN(lon)) {
            const delta = 0.003;
            const bbox = `${lon - delta},${lat - delta},${lon + delta},${lat + delta}`;
            mapIframe.src = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${lat},${lon}`;
            mapContainer.classList.remove("hidden");
        } else {
            mapIframe.src = "";
            mapContainer.classList.add("hidden");
        }
    }
    
    // Render opportunity score badge in modal
    const score = lead.opportunity_score || 0;
    const modalScoreBadge = document.getElementById("modal-score-badge");
    if (modalScoreBadge) {
        let scoreClass = "";
        let scoreLabel = "";
        if (score >= 70) {
            scoreClass = "bg-[#fedcdb] text-[#bf0711] border-[#ffc4c2]";
            scoreLabel = "High Opportunity";
        } else if (score >= 40) {
            scoreClass = "bg-[#fcf1cd] text-[#9c6f1a] border-[#ffe5b4]";
            scoreLabel = "Medium Opportunity";
        } else {
            scoreClass = "bg-[#e3f1df] text-[#108043] border-[#aee9d1]";
            scoreLabel = "Low Opportunity";
        }
        modalScoreBadge.className = `inline-flex mt-1 text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${scoreClass}`;
        modalScoreBadge.textContent = `${score} pts - ${scoreLabel}`;
    }
    
    // Render phone verification status
    const phoneStatus = document.getElementById("modal-phone-status");
    if (lead.phone_verified === 1) {
        phoneStatus.innerHTML = `<span class="px-2 py-0.5 bg-emerald-50 border border-emerald-200/50 text-emerald-700 text-[9px] rounded-full font-bold font-mono">Valid</span>`;
    } else if (lead.phone_verified === -1) {
        phoneStatus.innerHTML = `<span class="px-2 py-0.5 bg-rose-50 border border-rose-200/50 text-rose-700 text-[9px] rounded-full font-bold font-mono">Invalid</span>`;
    } else {
        phoneStatus.innerHTML = ``;
    }

    // Render email verification status
    const emailStatus = document.getElementById("modal-email-status");
    if (lead.email_verified === 1) {
        emailStatus.innerHTML = `<span class="px-2 py-0.5 bg-emerald-50 border border-emerald-200/50 text-emerald-700 text-[9px] rounded-full font-bold font-mono">MX Verified</span>`;
    } else if (lead.email_verified === -1) {
        emailStatus.innerHTML = `<span class="px-2 py-0.5 bg-rose-50 border border-rose-200/50 text-rose-700 text-[9px] rounded-full font-bold font-mono">Domain Invalid</span>`;
    } else {
        emailStatus.innerHTML = ``;
    }

    // Render meta/cuisine info
    let metaString = "-";
    if (lead.cuisine) metaString = `Cuisine: ${lead.cuisine}`;
    if (lead.brand) metaString = lead.cuisine ? `${metaString} | Brand: ${lead.brand}` : `Brand: ${lead.brand}`;
    document.getElementById("modal-meta").textContent = metaString;
    
    // Social Links
    const instaLink = document.getElementById("modal-instagram-link");
    if (lead.instagram) {
        instaLink.innerHTML = `<a href="${lead.instagram}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200/60 text-indigo-700 font-semibold rounded-full transition duration-150"><i class="fa-brands fa-instagram text-sm"></i>Instagram</a>`;
    } else {
        instaLink.innerHTML = `<span class="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 border border-slate-200/60 text-slate-400 rounded-full cursor-not-allowed select-none font-semibold"><i class="fa-brands fa-instagram text-sm"></i>Instagram: N/A</span>`;
    }
    
    const fbLink = document.getElementById("modal-facebook-link");
    if (lead.facebook) {
        fbLink.innerHTML = `<a href="${lead.facebook}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-50 hover:bg-blue-100 border border-blue-200/60 text-blue-700 font-semibold rounded-full transition duration-150"><i class="fa-brands fa-facebook text-sm"></i>Facebook</a>`;
    } else {
        fbLink.innerHTML = `<span class="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 border border-slate-200/60 text-slate-400 rounded-full cursor-not-allowed select-none font-semibold"><i class="fa-brands fa-facebook text-sm"></i>Facebook: N/A</span>`;
    }
    
    // WhatsApp direct action button
    const waBtn = document.getElementById("modal-wa-btn");
    if (lead.whatsapp) {
        waBtn.href = lead.whatsapp;
        waBtn.classList.remove("opacity-50", "pointer-events-none");
    } else if (lead.phone && lead.phone.startsWith("+")) {
        const cleanedPhone = lead.phone.replace("+", "");
        waBtn.href = `https://wa.me/${cleanedPhone}`;
        waBtn.classList.remove("opacity-50", "pointer-events-none");
    } else {
        waBtn.href = "#";
        waBtn.classList.add("opacity-50", "pointer-events-none");
    }
    
    // Website button
    const webBtn = document.getElementById("modal-web-btn");
    if (lead.website) {
        webBtn.href = lead.website;
        webBtn.classList.remove("opacity-50", "pointer-events-none");
    } else {
        webBtn.href = "#";
        webBtn.classList.add("opacity-50", "pointer-events-none");
    }

    // Maps button
    const mapsBtn = document.getElementById("modal-maps-btn");
    if (mapsBtn) {
        let mapsLink = lead.maps_link;
        if (!mapsLink && lead.latitude && lead.longitude) {
            const nameQuery = encodeURIComponent(lead.name);
            mapsLink = `https://www.google.com/maps/search/?api=1&query=${nameQuery}+${lead.latitude},${lead.longitude}`;
        }
        if (mapsLink) {
            mapsBtn.href = mapsLink;
            mapsBtn.classList.remove("opacity-50", "pointer-events-none");
        } else {
            mapsBtn.href = "#";
            mapsBtn.classList.add("opacity-50", "pointer-events-none");
        }
    }
    
    document.getElementById("detail-modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("detail-modal").classList.add("hidden");
    const mapIframe = document.getElementById("modal-map-iframe");
    if (mapIframe) {
        mapIframe.src = "";
    }
}

// Utility to escape HTML output
function escapeHtml(text) {
    if (!text) return "";
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>'"]/g, m => map[m]);
}

// Dynamic exporter matching current UI filters, contact filters, and selected columns
function triggerExport() {
    const format = document.getElementById("export-format").value;
    const runId = document.getElementById("run-filter").value;
    const search = document.getElementById("search-input").value;
    const showDuplicates = document.getElementById("dup-checkbox").checked;
    
    // Filters
    const hasEmail = document.getElementById("export-has-email").checked;
    const hasPhone = document.getElementById("export-has-phone").checked;
    const hasWebsite = document.getElementById("export-has-website").checked;
    const minScore = document.getElementById("export-min-score").value;
    
    // Columns selection
    let colList = ["id", "name", "category", "address", "opportunity_score", "source", "source_id"];
    if (document.getElementById("export-col-contacts").checked) {
        colList.push("phone", "email", "website", "email_verified", "phone_verified");
    }
    if (document.getElementById("export-col-geo").checked) {
        colList.push("latitude", "longitude", "maps_link", "rating", "review_count");
    }
    if (document.getElementById("export-col-socials").checked) {
        colList.push("instagram", "facebook", "whatsapp");
    }
    if (document.getElementById("export-col-meta").checked) {
        colList.push("opening_hours", "cuisine", "brand", "price_range");
    }
    const columns = colList.join(",");
    
    let url = `/api/export?format=${format}&duplicates=${showDuplicates}&has_email=${hasEmail}&has_phone=${hasPhone}&has_website=${hasWebsite}&columns=${columns}`;
    if (runId) url += `&run_id=${runId}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (minScore) url += `&min_score=${minScore}`;
    
    window.location.href = url;
}

// Custom confirmation modal controller
let confirmCallback = null;

function showConfirm(title, message, onConfirm, okText = "Delete", okClass = "bg-rose-600 hover:bg-rose-700 text-white") {
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-message").textContent = message;
    
    const okBtn = document.getElementById("confirm-ok-btn");
    okBtn.textContent = okText;
    okBtn.className = `px-4 py-2 font-bold rounded transition ${okClass}`;
    
    confirmCallback = onConfirm;
    document.getElementById("confirm-modal").classList.remove("hidden");
}

function closeConfirm() {
    document.getElementById("confirm-modal").classList.add("hidden");
    confirmCallback = null;
}

// Bind confirmation modal events
document.addEventListener("DOMContentLoaded", () => {
    const cancelBtn = document.getElementById("confirm-cancel-btn");
    const okBtn = document.getElementById("confirm-ok-btn");
    
    if (cancelBtn) cancelBtn.onclick = closeConfirm;
    if (okBtn) {
        okBtn.onclick = () => {
            if (confirmCallback) confirmCallback();
            closeConfirm();
        };
    }
});
