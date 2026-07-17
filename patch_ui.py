import re

with open("static/bot.html", "r") as f:
    content = f.read()

# Add tabs to header
tabs_html = """
            <div class="nav-tabs" style="display:flex; gap:20px; align-items:center;">
                <button class="tab-btn active" data-tab="tab-classic" style="background:transparent; color:var(--text-primary); border:none; border-bottom:2px solid var(--accent-primary); font-weight:600; padding:10px; cursor:pointer;">Classic Q&A</button>
                <button class="tab-btn" data-tab="tab-orchestrator" style="background:transparent; color:var(--text-secondary); border:none; padding:10px; cursor:pointer;">Agent Orchestrator</button>
                <button class="tab-btn" data-tab="tab-logs" style="background:transparent; color:var(--text-secondary); border:none; padding:10px; cursor:pointer;">Logs</button>
                <button class="tab-btn" data-tab="tab-kb" style="background:transparent; color:var(--text-secondary); border:none; padding:10px; cursor:pointer;">Knowledge Base</button>
            </div>
"""
content = content.replace(
    '<div class="config-status-badge" id="config-status-badge">',
    tabs_html + '\n            <div class="config-status-badge" id="config-status-badge">'
)

# Wrap main layout
content = content.replace(
    '<div class="main-layout">',
    '<div class="tab-content-wrapper" style="height: calc(100vh - 70px); overflow: hidden;">\n        <div id="tab-classic" class="tab-pane active" style="height: 100%;">\n            <div class="main-layout">'
)

# Add other tabs
tabs_panes = """
            </div>
        </div>
        
        <!-- NEW TABS -->
        <div id="tab-orchestrator" class="tab-pane" style="display:none; height: 100%; padding: 24px; overflow-y: auto;">
            <div class="chat-header"><h2>Agent Orchestrator</h2><p>Multi-tool AI execution with strict grounding</p></div>
            <div style="display:flex; gap: 20px; height: calc(100% - 70px);">
                <div style="flex:1; display:flex; flex-direction:column;">
                    <div class="chat-messages" id="orch-messages" style="flex-grow:1; background: var(--bg-secondary); border-radius: 8px; padding: 20px; border: 1px solid var(--border-color); overflow-y: auto;">
                        <div class="message system"><div class="avatar"><i class="fa-solid fa-robot"></i></div><div class="message-content"><p>Agent ready. Enter instructions or use a preset below.</p></div></div>
                    </div>
                    
                    <div id="orch-plan-container" style="display:none; background: rgba(245, 158, 11, 0.1); border: 1px solid var(--color-warning); padding: 15px; border-radius: 8px; margin-top: 15px;">
                        <h4 style="color: var(--color-warning); margin-bottom: 10px;">Proposed Plan (Semi-Auto)</h4>
                        <pre id="orch-plan-text" style="font-size:12px; color: var(--text-primary); margin-bottom: 10px;"></pre>
                        <button id="btn-orch-confirm" class="btn btn-primary">Confirm & Run</button>
                    </div>

                    <div class="input-container" style="margin-top:20px;">
                        <textarea id="orch-input" placeholder="Give the agent a complex instruction..." style="flex-grow:1; background:transparent; border:none; color:white; padding:10px; resize:none;" rows="2"></textarea>
                        <button id="btn-orch-send" class="btn-send"><i class="fa-solid fa-paper-plane"></i></button>
                    </div>
                    
                    <div style="margin-top:15px; display:flex; gap:10px; align-items:center;">
                        <span style="font-size:12px; color:var(--text-secondary);">Mode:</span>
                        <select id="orch-mode" style="background:var(--bg-secondary); color:white; border:1px solid var(--border-color); border-radius:4px; padding:4px;">
                            <option value="auto">Auto (Execute Full Plan)</option>
                            <option value="semi-auto">Semi-Auto (Review Plan First)</option>
                        </select>
                        <span style="font-size:12px; color:var(--text-secondary); margin-left: 15px;">Target Document:</span>
                        <select id="orch-doc" style="background:var(--bg-secondary); color:white; border:1px solid var(--border-color); border-radius:4px; padding:4px;">
                            <option value="">-- Global Search --</option>
                        </select>
                    </div>
                    
                    <div style="margin-top:15px; display:flex; gap:10px;">
                        <button class="btn btn-secondary" onclick="document.getElementById('orch-input').value='Summarize this document';">Summarize Doc</button>
                        <button class="btn btn-secondary" onclick="document.getElementById('orch-input').value='Check for gaps and flag them';">Check for Gaps</button>
                        <button class="btn btn-secondary" onclick="document.getElementById('orch-input').value='List all flagged low-confidence answers';">List Flags</button>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="tab-logs" class="tab-pane" style="display:none; height: 100%; padding: 24px; overflow:auto;">
            <div class="chat-header" style="display:flex; justify-content:space-between; align-items:center;">
                <div><h2>Orchestration Logs</h2><p>Audit trail of all agent tool runs</p></div>
                <button class="btn btn-secondary" onclick="fetchLogs()"><i class="fa-solid fa-rotate-right"></i> Refresh</button>
            </div>
            <table class="data-table" id="logs-table" style="width:100%; text-align:left; border-collapse:collapse; margin-top: 20px;">
                <thead><tr style="border-bottom: 1px solid var(--border-color); color: var(--text-muted);"><th style="padding:10px;">Time</th><th style="padding:10px;">User Input</th><th style="padding:10px;">Tools Used</th><th style="padding:10px;">Faithfulness</th><th style="padding:10px;">Flagged</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div id="tab-kb" class="tab-pane" style="display:none; height: 100%; padding: 24px; overflow:auto;">
            <div class="chat-header" style="display:flex; justify-content:space-between; align-items:center;">
                <div><h2>Knowledge Base Explorer</h2><p>Document-level metrics</p></div>
                <button class="btn btn-secondary" onclick="fetchKB()"><i class="fa-solid fa-rotate-right"></i> Refresh</button>
            </div>
            <table class="data-table" id="kb-table" style="width:100%; text-align:left; border-collapse:collapse; margin-top: 20px;">
                <thead><tr style="border-bottom: 1px solid var(--border-color); color: var(--text-muted);"><th style="padding:10px;">Document</th><th style="padding:10px;">Avg Faithfulness</th><th style="padding:10px;">Chunks</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
        </div> <!-- End tab-content-wrapper -->
"""
content = content.replace(
    '        </div>\n    </div>\n\n    <!-- Alert Banner',
    tabs_panes + '\n    </div>\n\n    <!-- Alert Banner'
)

# Add agent.js script tag
content = content.replace(
    '<script src="app.js"></script>',
    '<script src="app.js"></script>\n    <script src="agent.js"></script>'
)

with open("static/bot.html", "w") as f:
    f.write(content)

