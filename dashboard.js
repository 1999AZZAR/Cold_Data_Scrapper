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
        console.error("Failed to load status status: ", e);
    }
}

// Fetch scraper runs history
async function loadRuns() {
    try {
        const response = await fetch("/api/runs");
        const runs = await response.json();
        
        const tbody = document.getElementById("runs-tbody");
        const runFilter = document.getElementById("run-filter");
        
        // Preserve selected run filter value
        const selectedFilterVal = runFilter.value;
        
        tbody.innerHTML = "";
        runFilter.innerHTML = '<option value="">All Scraper Runs</option>';
        
        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-neutral-400">No runs triggered yet.</td></tr>';
            return;
        }
        
        runs.forEach(run => {
            // Update table row
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="p-3 border-b border-neutral-100 font-bold">#${run.id}</td>
                <td class="p-3 border-b border-neutral-100 font-semibold">${escapeHtml(run.query)}</td>
                <td class="p-3 border-b border-neutral-100">${escapeHtml(run.region)}</td>
                <td class="p-3 border-b border-neutral-100">
                    <span class="px-2 py-0.5 text-[10px] uppercase font-semibold rounded ${
                        run.status === 'completed' ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' :
                        run.status === 'running' ? 'bg-blue-100 text-blue-800 border border-blue-200 animate-pulse' :
                        'bg-rose-100 text-rose-800 border border-rose-200'
                    }">${run.status}</span>
                </td>
                <td class="p-3 border-b border-neutral-100">${run.results_count} leads</td>
                <td class="p-3 border-b border-neutral-100 text-neutral-400 font-sans">${run.created_at}</td>
            `;
            tbody.appendChild(tr);
            
            // Update dropdown filter
            const option = document.createElement("option");
            option.value = run.id;
            option.textContent = `Run #${run.id}: ${run.query} in ${run.region}`;
            runFilter.appendChild(option);
        });
        
        // Restore selection
        runFilter.value = selectedFilterVal;
    } catch (e) {
        console.error("Failed to load runs history: ", e);
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
            tr.className = "hover:bg-neutral-50 cursor-pointer transition-colors";
            tr.onclick = () => openModal(index);
            
            // Format phone & email display badges
            const phoneBadge = lead.phone ? `<span class="inline-flex items-center text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded text-[10px] border border-emerald-100 font-semibold font-mono"><i class="fa-solid fa-phone mr-1"></i>Yes</span>` : `<span class="text-neutral-300 font-mono">-</span>`;
            const emailBadge = lead.email ? `<span class="inline-flex items-center text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded text-[10px] border border-blue-100 font-semibold font-mono"><i class="fa-solid fa-envelope mr-1"></i>Yes</span>` : `<span class="text-neutral-300 font-mono">-</span>`;
            
            // Format website display links
            const webLink = lead.website ? `<a href="${lead.website}" target="_blank" onclick="event.stopPropagation();" class="text-neutral-800 hover:text-black font-mono underline"><i class="fa-solid fa-link mr-1"></i>Website</a>` : '<span class="text-neutral-300">-</span>';
            
            // Social badges
            let socialBadges = [];
            if (lead.instagram) socialBadges.push(`<i class="fa-brands fa-instagram text-indigo-500 text-sm" title="Instagram present"></i>`);
            if (lead.facebook) socialBadges.push(`<i class="fa-brands fa-facebook text-blue-600 text-sm" title="Facebook present"></i>`);
            if (lead.whatsapp) socialBadges.push(`<i class="fa-brands fa-whatsapp text-emerald-500 text-sm" title="WhatsApp link active"></i>`);
            const socialString = socialBadges.length > 0 ? `<div class="flex gap-1.5">${socialBadges.join("")}</div>` : '<span class="text-neutral-300">-</span>';
            
            tr.innerHTML = `
                <td class="p-3 font-semibold text-neutral-900 border-b border-neutral-100">
                    ${escapeHtml(lead.name)}
                    ${lead.duplicate_of ? `<span class="ml-1 px-1 py-0.5 bg-neutral-100 border text-[9px] font-semibold font-mono text-neutral-500 rounded">Dup of #${lead.duplicate_of}</span>` : ''}
                </td>
                <td class="p-3 border-b border-neutral-100 capitalize font-mono text-[11px] text-neutral-500">${escapeHtml(lead.category)}</td>
                <td class="p-3 border-b border-neutral-100"><div class="flex gap-1">${phoneBadge}${emailBadge}</div></td>
                <td class="p-3 border-b border-neutral-100">${webLink}</td>
                <td class="p-3 border-b border-neutral-100">${socialString}</td>
                <td class="p-3 border-b border-neutral-100 font-mono text-[10px]">
                    <button class="text-black hover:underline uppercase tracking-wider font-semibold">View Detail</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load leads: ", e);
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
            alert(`POI Scraper Run ID #${res.run_id} started in the background! Refresh status to track.`);
            document.getElementById("extract-query").value = "";
            document.getElementById("extract-region").value = "";
            loadRuns();
            loadStatus();
        } else {
            alert(`Error: ${res.error}`);
        }
    } catch (err) {
        alert(`Error triggering scraper: ${err}`);
    } finally {
        btn.disabled = false;
        btnText.textContent = "Extract POI Data";
        btn.classList.remove("opacity-50", "cursor-not-allowed");
    }
}

// Trigger separate utilities
async function triggerAction(actionName) {
    try {
        const response = await fetch("/api/action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: actionName })
        });
        const res = await response.json();
        
        if (res.status === "started") {
            alert(`Action '${actionName.toUpperCase()}' started in the background!`);
            // Poll for refreshes
            setTimeout(() => {
                loadStatus();
                loadLeads();
            }, 3000);
        } else {
            alert(`Error: ${res.error}`);
        }
    } catch (err) {
        alert(`Failed to trigger action: ${err}`);
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
    
    // Render meta/cuisine info
    let metaString = "-";
    if (lead.cuisine) metaString = `Cuisine: ${lead.cuisine}`;
    if (lead.brand) metaString = lead.cuisine ? `${metaString} | Brand: ${lead.brand}` : `Brand: ${lead.brand}`;
    document.getElementById("modal-meta").textContent = metaString;
    
    // Social Links
    const instaLink = document.getElementById("modal-instagram-link");
    if (lead.instagram) {
        instaLink.innerHTML = `<a href="${lead.instagram}" target="_blank" class="text-indigo-600 hover:underline font-mono"><i class="fa-brands fa-instagram mr-1"></i>Instagram Profile</a>`;
    } else {
        instaLink.textContent = "Instagram: Not Enriched";
    }
    
    const fbLink = document.getElementById("modal-facebook-link");
    if (lead.facebook) {
        fbLink.innerHTML = `<a href="${lead.facebook}" target="_blank" class="text-blue-600 hover:underline font-mono"><i class="fa-brands fa-facebook mr-1"></i>Facebook Page</a>`;
    } else {
        fbLink.textContent = "Facebook: Not Enriched";
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
