/**
 * Cold Data Dashboard Frontend Logic
 * Connects index.html elements with Flask REST endpoints.
 */

// Load data on page launch
document.addEventListener("DOMContentLoaded", () => {
    loadStatus();
    loadRuns();
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
    toast.className = `p-3.5 rounded-2xl border backdrop-blur-md shadow-lg shadow-slate-100/30 transition duration-300 transform translate-x-full opacity-0 flex justify-between items-center gap-3 max-w-sm pointer-events-auto`;
    
    let bgClass = "bg-white/95 border-slate-200 text-slate-800";
    let icon = '<i class="fa-solid fa-info-circle text-blue-500 text-sm"></i>';
    
    if (type === "success") {
        bgClass = "bg-emerald-50/95 border-emerald-200/60 text-emerald-900";
        icon = '<i class="fa-solid fa-circle-check text-emerald-600 text-sm"></i>';
    } else if (type === "error") {
        bgClass = "bg-rose-50/95 border-rose-200/60 text-rose-900";
        icon = '<i class="fa-solid fa-circle-exclamation text-rose-600 text-sm"></i>';
    }
    
    toast.className += ` ${bgClass}`;
    toast.innerHTML = `
        <div class="flex items-center gap-2.5">
            ${icon}
            <span class="font-sans text-[11px] font-semibold tracking-tight">${message}</span>
        </div>
        <button class="text-slate-400 hover:text-slate-900 transition flex items-center justify-center p-1 hover:bg-slate-100 rounded-full" onclick="this.parentElement.remove()">
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
                    <button onclick="event.stopPropagation(); deleteRun(${run.id})" class="text-rose-500 hover:text-rose-700 font-bold hover:underline transition duration-150">
                        <i class="fa-solid fa-trash-can mr-1"></i>Delete
                    </button>
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
    if (!confirm(`Are you sure you want to delete Run #${runId} and all its associated leads data?`)) {
        return;
    }
    
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

// Fetch leads list
let currentLeads = [];
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
        
        const tbody = document.getElementById("leads-tbody");
        document.getElementById("lead-count").textContent = `${currentLeads.length} items`;
        tbody.innerHTML = "";
        
        if (currentLeads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-neutral-400 font-mono">No matching records found.</td></tr>';
            return;
        }
        
        currentLeads.forEach((lead, index) => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-50/60 cursor-pointer transition-colors duration-150";
            tr.onclick = () => openModal(index);
            
            const phoneBadge = lead.phone ? `<span class="inline-flex items-center text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-[9px] border border-emerald-100/80 font-bold font-mono"><i class="fa-solid fa-phone mr-1 text-[8px]"></i>Phone</span>` : `<span class="text-slate-300 font-mono">-</span>`;
            const emailBadge = lead.email ? `<span class="inline-flex items-center text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full text-[9px] border border-blue-100/80 font-bold font-mono"><i class="fa-solid fa-envelope mr-1 text-[8px]"></i>Email</span>` : `<span class="text-slate-300 font-mono">-</span>`;
            
            const webLink = lead.website ? `<a href="${lead.website}" target="_blank" onclick="event.stopPropagation();" class="text-slate-800 hover:text-indigo-600 font-mono font-semibold transition duration-150 flex items-center gap-1"><i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i>Link</a>` : '<span class="text-slate-300">-</span>';
            
            let socialBadges = [];
            if (lead.instagram) socialBadges.push(`<i class="fa-brands fa-instagram text-indigo-500 text-sm" title="Instagram present"></i>`);
            if (lead.facebook) socialBadges.push(`<i class="fa-brands fa-facebook text-blue-600 text-sm" title="Facebook present"></i>`);
            if (lead.whatsapp) socialBadges.push(`<i class="fa-brands fa-whatsapp text-emerald-500 text-sm" title="WhatsApp link active"></i>`);
            const socialString = socialBadges.length > 0 ? `<div class="flex gap-2">${socialBadges.join("")}</div>` : '<span class="text-slate-300">-</span>';
            
            tr.innerHTML = `
                <td class="p-3 font-semibold text-slate-900 border-b border-slate-100">
                    ${escapeHtml(lead.name)}
                    ${lead.duplicate_of ? `<span class="ml-2 px-2 py-0.5 bg-slate-100 text-[9px] font-bold font-mono text-slate-500 rounded-full border border-slate-200/60">Dup of #${lead.duplicate_of}</span>` : ''}
                </td>
                <td class="p-3 border-b border-slate-100 capitalize font-mono text-[10px] text-slate-500">${escapeHtml(lead.category)}</td>
                <td class="p-3 border-b border-slate-100"><div class="flex gap-1.5">${phoneBadge}${emailBadge}</div></td>
                <td class="p-3 border-b border-slate-100">${webLink}</td>
                <td class="p-3 border-b border-slate-100">${socialString}</td>
                <td class="p-3 border-b border-slate-100 font-mono text-[10px]">
                    <button class="text-slate-900 hover:underline uppercase tracking-wider font-bold transition">View</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load leads:", e);
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
    
    try {
        const response = await fetch("/api/trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, region, limit: limit ? parseInt(limit) : null })
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
    
    document.getElementById("detail-modal").classList.remove("hidden");
}

function closeModal() {
    document.getElementById("detail-modal").classList.add("hidden");
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
