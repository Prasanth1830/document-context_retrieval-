document.addEventListener('DOMContentLoaded', () => {
    // Tab Switching Logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all
            tabBtns.forEach(b => {
                b.classList.remove('active');
                b.style.borderBottom = '2px solid transparent';
                b.style.color = 'var(--text-secondary)';
            });
            tabPanes.forEach(p => p.style.display = 'none');

            // Add active class to clicked
            btn.classList.add('active');
            btn.style.borderBottom = '2px solid var(--accent-primary)';
            btn.style.color = 'var(--text-primary)';
            
            const targetId = btn.getAttribute('data-tab');
            document.getElementById(targetId).style.display = 'block';
            
            // Refresh data if specific tabs are opened
            if (targetId === 'tab-logs') window.fetchLogs();
            if (targetId === 'tab-kb') window.fetchKB();
        });
    });

    // Populate Target Document Dropdown periodically
    setInterval(() => {
        const fileListItems = document.querySelectorAll('#file-list .file-item-name span');
        const docSelect = document.getElementById('orch-doc');
        if (!docSelect) return;
        
        const currentFiles = Array.from(fileListItems).map(el => el.textContent);
        const existingOptions = Array.from(docSelect.options).map(opt => opt.value).filter(val => val !== "");
        
        currentFiles.forEach(file => {
            if (!existingOptions.includes(file)) {
                const opt = document.createElement('option');
                opt.value = file;
                opt.textContent = file;
                docSelect.appendChild(opt);
            }
        });
    }, 2000);

    // Orchestrator Chat Logic
    const btnOrchSend = document.getElementById('btn-orch-send');
    const orchInput = document.getElementById('orch-input');
    const orchMessages = document.getElementById('orch-messages');
    let currentPendingPlan = null;
    let currentPendingInput = null;
    let currentPendingDoc = null;

    function appendMessage(role, text, flagged = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        const avatarStr = role === 'user' 
            ? '<i class="fa-solid fa-user"></i>' 
            : '<i class="fa-solid fa-robot"></i>';
            
        let contentHtml = `<p>${text}</p>`;
        if (flagged) {
            contentHtml += `<div style="margin-top:8px; padding:6px; background:rgba(239, 68, 68, 0.1); border:1px solid var(--color-danger); border-radius:4px; font-size:11px; color:var(--color-danger);"><i class="fa-solid fa-triangle-exclamation"></i> Flagged for Low Confidence</div>`;
        }

        msgDiv.innerHTML = `
            <div class="avatar">${avatarStr}</div>
            <div class="message-content">${contentHtml}</div>
        `;
        orchMessages.appendChild(msgDiv);
        orchMessages.scrollTop = orchMessages.scrollHeight;
    }

    btnOrchSend.addEventListener('click', async () => {
        const text = orchInput.value.trim();
        if (!text) return;
        
        const mode = document.getElementById('orch-mode').value;
        const docId = document.getElementById('orch-doc').value;
        
        appendMessage('user', text);
        orchInput.value = '';
        btnOrchSend.disabled = true;
        
        // Hide plan container if open
        document.getElementById('orch-plan-container').style.display = 'none';

        try {
            const res = await fetch('/api/orchestrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_input: text, document_id: docId || null, mode: mode })
            });
            const data = await res.json();
            
            if (!res.ok) {
                appendMessage('system', 'Server Error: ' + (data.detail || res.statusText));
                return;
            }
            
            if (data.status === 'plan_proposed') {
                document.getElementById('orch-plan-container').style.display = 'block';
                document.getElementById('orch-plan-text').textContent = JSON.stringify(data.plan, null, 2);
                currentPendingPlan = data.plan;
                currentPendingInput = text;
                currentPendingDoc = docId;
            } else if (data.status === 'error') {
                appendMessage('system', 'Agent Error: ' + data.message);
            } else {
                appendMessage('system', data.final_response || "Finished.", data.flagged);
            }
        } catch (e) {
            appendMessage('system', 'Error: ' + e.message);
        } finally {
            btnOrchSend.disabled = false;
        }
    });
    
    document.getElementById('btn-orch-confirm').addEventListener('click', async () => {
        if (!currentPendingPlan) return;
        
        const btn = document.getElementById('btn-orch-confirm');
        btn.disabled = true;
        btn.textContent = "Executing...";
        
        try {
            const res = await fetch('/api/orchestrate/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_input: currentPendingInput, document_id: currentPendingDoc || null, plan: currentPendingPlan })
            });
            const data = await res.json();
            document.getElementById('orch-plan-container').style.display = 'none';
            appendMessage('system', data.final_response, data.flagged);
        } catch (e) {
            appendMessage('system', 'Execution Error: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Confirm & Run";
        }
    });

    // Global fetch functions for tabs
    window.fetchLogs = async () => {
        const tbody = document.querySelector('#logs-table tbody');
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">Loading logs...</td></tr>';
        try {
            const res = await fetch('/api/logs');
            const data = await res.json();
            tbody.innerHTML = '';
            
            if (!data.logs || data.logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px;">No logs found.</td></tr>';
                return;
            }
            
            data.logs.forEach(log => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                
                const d = new Date(log.timestamp);
                const timeStr = `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
                
                let statusStr = log.status;
                if (log.status === "Blocked") statusStr = '<span style="color:var(--color-warning);"><i class="fa-solid fa-ban"></i> Blocked</span>';
                else if (log.status === "Flagged") statusStr = '<span style="color:var(--color-danger);"><i class="fa-solid fa-flag"></i> Flagged</span>';
                else statusStr = '<span style="color:var(--color-success);"><i class="fa-solid fa-check"></i> Success</span>';
                
                tr.innerHTML = `
                    <td style="padding:12px; font-size:12px; color:var(--text-muted);">${timeStr}</td>
                    <td style="padding:12px; font-size:13px;">${log.user_query}</td>
                    <td style="padding:12px; font-size:13px; font-weight:bold;">${(log.faithfulness_score).toFixed(2)}</td>
                    <td style="padding:12px; font-size:13px; font-weight:bold;">${(log.answer_relevance_score).toFixed(2)}</td>
                    <td style="padding:12px; font-size:13px; font-weight:bold;">${(log.context_recall_score).toFixed(2)}</td>
                    <td style="padding:12px;">${statusStr}</td>
                    <td style="padding:12px;">
                        <button class="btn btn-secondary btn-trace" data-id="${log.id}" style="padding:4px 8px; font-size:11px;">Trace</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            // Bind trace buttons
            document.querySelectorAll('.btn-trace').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const logId = e.target.getAttribute('data-id');
                    await showTraceModal(logId);
                });
            });

        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:red; padding:20px;">Error: ${e.message}</td></tr>`;
        }
    };

    async function showTraceModal(logId) {
        const modal = document.getElementById('trace-modal');
        const body = document.getElementById('trace-modal-body');
        modal.style.display = 'flex';
        body.innerHTML = 'Loading...';
        
        try {
            const res = await fetch(`/api/logs/${logId}`);
            const data = await res.json();
            if (data.status === "success") {
                const log = data.log;
                let chunksHtml = '';
                if (log.source_citations) {
                    log.source_citations.forEach((c, idx) => {
                        chunksHtml += `<div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:4px; margin-bottom:10px; border:1px solid var(--border-color);">
                            <strong>[${c.document_name}, Page ${c.page_number}]</strong> Score: ${c.score}<br>
                            <span style="font-style:italic;">"${c.text}"</span>
                        </div>`;
                    });
                }
                
                body.innerHTML = `
                    <div style="margin-bottom:15px;">
                        <h4 style="color:var(--text-primary); margin-bottom:5px;">User Query</h4>
                        <div style="background:var(--bg-primary); padding:10px; border-radius:4px; border:1px solid var(--border-color);">${log.user_query}</div>
                    </div>
                    <div style="margin-bottom:15px;">
                        <h4 style="color:var(--text-primary); margin-bottom:5px;">Final Answer</h4>
                        <div style="background:var(--bg-primary); padding:10px; border-radius:4px; border:1px solid var(--border-color);">${log.answer_text}</div>
                    </div>
                    <div style="margin-bottom:15px; display:flex; gap:20px;">
                        <div><strong>Faithfulness:</strong> ${log.faithfulness_score.toFixed(2)}</div>
                        <div><strong>Relevance:</strong> ${log.answer_relevance_score.toFixed(2)}</div>
                        <div><strong>Recall:</strong> ${log.context_recall_score.toFixed(2)}</div>
                        <div><strong>Status:</strong> ${log.status}</div>
                    </div>
                    <div>
                        <h4 style="color:var(--text-primary); margin-bottom:10px;">Retrieved Context (Citations)</h4>
                        ${chunksHtml || 'No context retrieved.'}
                    </div>
                `;
            } else {
                body.innerHTML = 'Error loading trace details.';
            }
        } catch(e) {
            body.innerHTML = `Error: ${e.message}`;
        }
    }

    let allKBRows = [];

    window.fetchKB = async () => {
        const tbody = document.querySelector('#kb-table tbody');
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px;">Loading knowledge base...</td></tr>';
        try {
            const res = await fetch('/api/kb-explorer');
            const data = await res.json();
            
            if (!data.answers || data.answers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px;">No answers cached yet.</td></tr>';
                allKBRows = [];
                return;
            }
            
            allKBRows = data.answers;
            renderKBTable(allKBRows);
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:red; padding:20px;">Error: ${e.message}</td></tr>`;
        }
    };
    
    window.filterKB = () => {
        const term = document.getElementById('kb-search').value.toLowerCase();
        if (!term) {
            renderKBTable(allKBRows);
            return;
        }
        const filtered = allKBRows.filter(r => 
            (r.document_id || '').toLowerCase().includes(term) ||
            (r.query_pattern || '').toLowerCase().includes(term) ||
            (r.user_query || '').toLowerCase().includes(term) ||
            (r.answer_text || '').toLowerCase().includes(term)
        );
        renderKBTable(filtered);
    };
    
    function renderKBTable(rows) {
        const tbody = document.querySelector('#kb-table tbody');
        tbody.innerHTML = '';
        
        if (rows.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:20px;">No matches found.</td></tr>';
            return;
        }
        
        rows.forEach(ans => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
            if (ans.frozen) tr.style.backgroundColor = 'rgba(0,255,0,0.02)';
            
            const d = new Date(ans.created_at);
            const timeStr = `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
            
            let btnHtml = '';
            if (ans.frozen) {
                btnHtml = `<button class="btn btn-secondary btn-freeze" data-id="${ans.id}" data-action="unfreeze" style="padding:4px 8px; font-size:11px; background:var(--color-warning); color:white; border-color:var(--color-warning);">Unfreeze</button>`;
            } else {
                btnHtml = `<button class="btn btn-secondary btn-freeze" data-id="${ans.id}" data-action="freeze" style="padding:4px 8px; font-size:11px; ${ans.faithfulness_score < 0.95 ? 'opacity:0.5; cursor:not-allowed;' : 'color:var(--color-success); border-color:var(--color-success);'}">Freeze</button>`;
            }
            
            const shortResp = ans.answer_text.length > 60 ? ans.answer_text.substring(0, 60) + '...' : ans.answer_text;
            
            tr.innerHTML = `
                <td style="padding:12px; font-size:12px; color:var(--text-muted);">${timeStr}</td>
                <td style="padding:12px; font-size:13px;">${ans.document_id}</td>
                <td style="padding:12px; font-size:12px; color:var(--accent-primary);"><span style="background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">${ans.query_pattern}</span></td>
                <td style="padding:12px; font-size:13px;">${ans.user_query}</td>
                <td style="padding:12px; font-size:13px; color:var(--text-secondary);">${shortResp}</td>
                <td style="padding:12px; display:flex; gap:5px;">
                    ${btnHtml}
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        document.querySelectorAll('.btn-freeze').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const action = e.target.getAttribute('data-action');
                const id = e.target.getAttribute('data-id');
                
                try {
                    const res = await fetch(`/api/kb-explorer/${id}/toggle`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ freeze: action === 'freeze' })
                    });
                    
                    if (!res.ok) {
                        const err = await res.json();
                        alert('Error: ' + err.detail);
                        return;
                    }
                    
                    window.fetchKB(); // refresh
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            });
        });
    }

    function getScoreColor(score) {
        if (score >= 0.95) return 'var(--color-success)';
        if (score >= 0.85) return 'var(--color-warning)';
        return 'var(--color-danger)';
    }

    function getErrorRateColor(rate) {
        if (rate <= 5) return 'var(--color-success)';
        if (rate <= 15) return 'var(--color-warning)';
        return 'var(--color-danger)';
    }

    window.fetchDashboard = async () => {
        try {
            const res = await fetch('/api/dashboard');
            const data = await res.json();
            
            if (data.status !== 'success' || !data.stats) return;
            const stats = data.stats;
            
            // Update cards
            document.getElementById('dash-faithfulness').textContent = stats.avg_faithfulness_score.all_time.toFixed(2);
            document.getElementById('dash-faithfulness').style.color = getScoreColor(stats.avg_faithfulness_score.all_time);
            document.getElementById('dash-faithfulness-24h').textContent = stats.avg_faithfulness_score['24h'].toFixed(2);
            
            document.getElementById('dash-relevance').textContent = stats.avg_answer_relevance_score.all_time.toFixed(2);
            document.getElementById('dash-relevance').style.color = getScoreColor(stats.avg_answer_relevance_score.all_time);
            document.getElementById('dash-relevance-24h').textContent = stats.avg_answer_relevance_score['24h'].toFixed(2);
            
            document.getElementById('dash-recall').textContent = stats.avg_context_recall_score.all_time.toFixed(2);
            document.getElementById('dash-recall').style.color = getScoreColor(stats.avg_context_recall_score.all_time);
            document.getElementById('dash-recall-24h').textContent = stats.avg_context_recall_score['24h'].toFixed(2);
            
            document.getElementById('dash-error').textContent = stats.error_rate.all_time.toFixed(1) + '%';
            document.getElementById('dash-error').style.color = getErrorRateColor(stats.error_rate.all_time);
            document.getElementById('dash-error-24h').textContent = stats.error_rate['24h'].toFixed(1) + '%';
            
            document.getElementById('dash-queries-today').textContent = stats.total_queries_today;
            document.getElementById('dash-queries-all').textContent = stats.total_queries_all_time;
            
            document.getElementById('dash-corrections').textContent = stats.corrections_applied_count;
            
            const topDoc = stats.top_document_by_query_volume;
            document.getElementById('dash-top-doc').textContent = topDoc.document_id === 'N/A' ? '--' : topDoc.document_id;
            document.getElementById('dash-top-doc-queries').textContent = topDoc.count;
            
            // Update table
            const tbody = document.querySelector('#dashboard-table tbody');
            tbody.innerHTML = '';
            
            if (stats.per_document_breakdown.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:20px;">No data available.</td></tr>';
            } else {
                stats.per_document_breakdown.forEach(doc => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    
                    tr.innerHTML = `
                        <td style="padding:12px; font-size:13px;">${doc.document_id}</td>
                        <td style="padding:12px; font-size:13px;">${doc.query_count}</td>
                        <td style="padding:12px; font-size:13px; font-weight:bold; color:${getScoreColor(doc.avg_faithfulness_score)}">${doc.avg_faithfulness_score.toFixed(2)}</td>
                        <td style="padding:12px; font-size:13px; font-weight:bold; color:${getErrorRateColor(doc.error_rate)}">${doc.error_rate.toFixed(1)}%</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (e) {
            console.error("Failed to fetch dashboard", e);
        }
    };

    // Initial fetch of logs and kb
    window.fetchLogs();
    window.fetchKB();
    window.fetchDashboard();
    
    // Auto-refresh Dashboard every 30s
    setInterval(() => {
        const dashTab = document.getElementById('tab-dashboard');
        if (dashTab && dashTab.style.display !== 'none') {
            window.fetchDashboard();
        }
    }, 30000);
});
