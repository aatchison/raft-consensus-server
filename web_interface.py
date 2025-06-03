#!/usr/bin/env python3
"""
Web Interface for Raft Cluster

A simple web interface to interact with and monitor the Raft cluster.
"""

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import json
from typing import List, Dict, Any
import uvicorn


class RaftWebInterface:
    """Web interface for Raft cluster monitoring and interaction."""
    
    def __init__(self, cluster_nodes: List[str]):
        self.cluster_nodes = cluster_nodes
        self.app = FastAPI(title="Raft Cluster Web Interface")
        self.setup_routes()
    
    def setup_routes(self):
        """Setup web interface routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard."""
            cluster_status = self.get_cluster_status()
            state_machine = self.get_state_machine()
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Raft Cluster Dashboard</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
                    .section {{ background-color: white; padding: 20px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .node {{ display: inline-block; margin: 10px; padding: 15px; border-radius: 5px; min-width: 200px; }}
                    .leader {{ background-color: #e8f5e8; border: 2px solid #4caf50; }}
                    .follower {{ background-color: #e3f2fd; border: 2px solid #2196f3; }}
                    .candidate {{ background-color: #fff3e0; border: 2px solid #ff9800; }}
                    .unreachable {{ background-color: #ffebee; border: 2px solid #f44336; }}
                    .form-group {{ margin-bottom: 15px; }}
                    .form-group label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                    .form-group input, .form-group textarea {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
                    .btn {{ background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }}
                    .btn:hover {{ background-color: #0056b3; }}
                    .state-machine {{ background-color: #f8f9fa; padding: 15px; border-radius: 4px; }}
                    .key-value {{ margin: 5px 0; padding: 8px; background-color: white; border-radius: 3px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f8f9fa; }}
                    .refresh-btn {{ float: right; }}
                </style>
                <script>
                    function refreshPage() {{
                        location.reload();
                    }}
                    setInterval(refreshPage, 5000); // Auto-refresh every 5 seconds
                </script>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🗳️ Raft Cluster Dashboard</h1>
                        <p>Real-time monitoring and interaction with the Raft consensus cluster</p>
                        <button class="btn refresh-btn" onclick="refreshPage()">🔄 Refresh</button>
                    </div>
                    
                    <div class="section">
                        <h2>📊 Cluster Status</h2>
                        <div class="cluster-nodes">
                            {self.render_cluster_status(cluster_status)}
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>📝 Operations</h2>
                        <div style="display: flex; gap: 20px;">
                            <div style="flex: 1;">
                                <h3>Set Key-Value</h3>
                                <form method="post" action="/set">
                                    <div class="form-group">
                                        <label for="key">Key:</label>
                                        <input type="text" id="key" name="key" required>
                                    </div>
                                    <div class="form-group">
                                        <label for="value">Value:</label>
                                        <input type="text" id="value" name="value" required>
                                    </div>
                                    <button type="submit" class="btn">Set Value</button>
                                </form>
                            </div>
                            <div style="flex: 1;">
                                <h3>Get Value</h3>
                                <form method="get" action="/get">
                                    <div class="form-group">
                                        <label for="get_key">Key:</label>
                                        <input type="text" id="get_key" name="key" required>
                                    </div>
                                    <button type="submit" class="btn">Get Value</button>
                                </form>
                            </div>
                            <div style="flex: 1;">
                                <h3>Delete Key</h3>
                                <form method="post" action="/delete">
                                    <div class="form-group">
                                        <label for="delete_key">Key:</label>
                                        <input type="text" id="delete_key" name="key" required>
                                    </div>
                                    <button type="submit" class="btn">Delete Key</button>
                                </form>
                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>💾 State Machine</h2>
                        <div class="state-machine">
                            {self.render_state_machine(state_machine)}
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>📋 Detailed Node Information</h2>
                        {self.render_detailed_status(cluster_status)}
                    </div>
                </div>
            </body>
            </html>
            """
            return html_content
        
        @self.app.post("/set")
        async def set_value(key: str = Form(...), value: str = Form(...)):
            """Set a key-value pair."""
            leader = self.find_leader()
            if not leader:
                raise HTTPException(status_code=503, detail="No leader available")
            
            try:
                # Try to parse value as JSON, otherwise treat as string
                try:
                    parsed_value = json.loads(value)
                except:
                    parsed_value = value
                
                response = requests.post(
                    f"http://{leader}/api/set",
                    json={"key": key, "value": parsed_value},
                    timeout=5
                )
                
                if response.status_code == 200:
                    return RedirectResponse(url="/", status_code=303)
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/get")
        async def get_value(key: str):
            """Get a value by key."""
            for node in self.cluster_nodes:
                try:
                    response = requests.get(f"http://{node}/api/get/{key}", timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("found"):
                            return {"key": key, "value": data["value"], "found": True}
                        break
                except:
                    continue
            return {"key": key, "value": None, "found": False}
        
        @self.app.post("/delete")
        async def delete_value(key: str = Form(...)):
            """Delete a key."""
            leader = self.find_leader()
            if not leader:
                raise HTTPException(status_code=503, detail="No leader available")
            
            try:
                response = requests.post(
                    f"http://{leader}/api/delete",
                    json={"key": key},
                    timeout=5
                )
                
                if response.status_code == 200:
                    return RedirectResponse(url="/", status_code=303)
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def find_leader(self) -> str:
        """Find the current leader."""
        for node in self.cluster_nodes:
            try:
                response = requests.get(f"http://{node}/api/status", timeout=2)
                if response.status_code == 200:
                    status = response.json()
                    if status.get("state") == "leader":
                        return node
            except:
                continue
        return None
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get status of all nodes in the cluster."""
        status = {}
        for node in self.cluster_nodes:
            try:
                response = requests.get(f"http://{node}/api/status", timeout=2)
                if response.status_code == 200:
                    status[node] = response.json()
                else:
                    status[node] = {"error": f"HTTP {response.status_code}"}
            except Exception as e:
                status[node] = {"error": str(e)}
        return status
    
    def get_state_machine(self) -> Dict[str, Any]:
        """Get the state machine from any available node."""
        for node in self.cluster_nodes:
            try:
                response = requests.get(f"http://{node}/api/state_machine", timeout=2)
                if response.status_code == 200:
                    return response.json().get("state_machine", {})
            except:
                continue
        return {}
    
    def render_cluster_status(self, cluster_status: Dict[str, Any]) -> str:
        """Render cluster status HTML."""
        html = ""
        for node, status in cluster_status.items():
            if "error" in status:
                css_class = "unreachable"
                state = "UNREACHABLE"
                term = "N/A"
            else:
                state = status.get("state", "unknown").upper()
                css_class = status.get("state", "unreachable")
                term = status.get("current_term", 0)
            
            html += f"""
            <div class="node {css_class}">
                <strong>{node}</strong><br>
                State: {state}<br>
                Term: {term}
            </div>
            """
        return html
    
    def render_state_machine(self, state_machine: Dict[str, Any]) -> str:
        """Render state machine HTML."""
        if not state_machine:
            return "<p>State machine is empty</p>"
        
        html = ""
        for key, value in state_machine.items():
            html += f"""
            <div class="key-value">
                <strong>{key}:</strong> {json.dumps(value) if isinstance(value, (dict, list)) else value}
            </div>
            """
        return html
    
    def render_detailed_status(self, cluster_status: Dict[str, Any]) -> str:
        """Render detailed status table."""
        html = """
        <table>
            <tr>
                <th>Node</th>
                <th>State</th>
                <th>Term</th>
                <th>Voted For</th>
                <th>Log Size</th>
                <th>Commit Index</th>
                <th>Last Applied</th>
            </tr>
        """
        
        for node, status in cluster_status.items():
            if "error" in status:
                html += f"""
                <tr>
                    <td>{node}</td>
                    <td colspan="6" style="color: red;">ERROR: {status['error']}</td>
                </tr>
                """
            else:
                html += f"""
                <tr>
                    <td>{node}</td>
                    <td>{status.get('state', 'unknown')}</td>
                    <td>{status.get('current_term', 'N/A')}</td>
                    <td>{status.get('voted_for', 'None')}</td>
                    <td>{status.get('log_size', 'N/A')}</td>
                    <td>{status.get('commit_index', 'N/A')}</td>
                    <td>{status.get('last_applied', 'N/A')}</td>
                </tr>
                """
        
        html += "</table>"
        return html


def main():
    """Main entry point."""
    # Default cluster nodes
    cluster_nodes = ["localhost:12000", "localhost:12001", "localhost:12002"]
    
    web_interface = RaftWebInterface(cluster_nodes)
    
    print("Starting Raft Web Interface on http://localhost:8080")
    print("Cluster nodes:", cluster_nodes)
    
    uvicorn.run(
        web_interface.app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )


if __name__ == "__main__":
    main()