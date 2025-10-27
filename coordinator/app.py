from flask import Flask, request, jsonify, render_template_string, send_file, redirect, url_for
import os, requests, uuid, json
from io import BytesIO

app = Flask(__name__)
DATA_DIR = '/data'
META_FILE = os.path.join(DATA_DIR, 'metadata.json')
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(META_FILE):
    with open(META_FILE, 'w') as f:
        json.dump({}, f)

def load_meta():
    with open(META_FILE, 'r') as f:
        return json.load(f)

def save_meta(m):
    with open(META_FILE, 'w') as f:
        json.dump(m, f)

NODES = os.environ.get('NODE_URLS', 'http://node1:5100,http://node2:5100,http://node3:5100').split(',')

@app.route('/')
def index():
    meta = load_meta()
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fault-Tolerant File Storage System</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
        <style>
            body {{ background-color: #f8f9fa; }}
            .container {{ margin-top: 50px; }}
            h2 {{ color: #2E86C1; }}
            table {{ background: white; border-radius: 10px; }}
            th {{ background-color: #3498db; color: white; }}
            footer {{ margin-top: 40px; text-align: center; color: gray; }}
        </style>
    </head>
    <body>
    <div class="container">
        <h2 class="mb-4 text-center">💾 Fault-Tolerant File Storage Dashboard</h2>
        
        <div class="card shadow p-4 mb-4">
            <h5>Upload a File</h5>
            <form action="/files" method="post" enctype="multipart/form-data">
                <div class="input-group">
                    <input type="file" class="form-control" name="file" required>
                    <button type="submit" class="btn btn-primary">Upload</button>
                </div>
            </form>
        </div>
        
        <div class="card shadow p-4 mb-4">
            <h5>System Actions</h5>
            <form action="/checkpoint" method="post" style="display:inline;">
                <button class="btn btn-success me-2">Create Checkpoint</button>
            </form>
            <button class="btn btn-warning" onclick="recoverPrompt()">Trigger Node Recovery</button>
        </div>

        <div class="card shadow p-4">
            <h5>📂 Uploaded Files</h5>
            {generate_file_table(meta)}
        </div>

        <footer>
            <p>Developed by <b>Tushar</b> | Fault Tolerant Systems (21CSE479T)</p>
        </footer>
    </div>

    <script>
        function recoverPrompt() {{
            var node = prompt("Enter node name to recover (e.g., node2):");
            if(node) {{
                fetch(`/recover/${{node}}`, {{method:'POST'}})
                .then(res => res.text())
                .then(msg => alert(msg))
                .catch(err => alert("Recovery failed: " + err));
            }}
        }}
    </script>
    </body>
    </html>
    """
    return render_template_string(html)

def generate_file_table(meta):
    if not meta:
        return "<p>No files uploaded yet.</p>"
    rows = ""
    for fid, info in meta.items():
        replicas = "<br>".join(info["nodes"])
        rows += f"<tr><td>{fid}</td><td>{info['filename']}</td><td>{replicas}</td><td><a class='btn btn-sm btn-outline-primary' href='/files/{fid}'>Download</a></td></tr>"
    return f"""
    <table class="table table-striped table-bordered mt-3">
        <thead><tr><th>File ID</th><th>Filename</th><th>Replicas</th><th>Action</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
    """

@app.route('/files', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f:
        return redirect(url_for('index'))
    file_id = str(uuid.uuid4())
    filename = f.filename
    content = f.read()
    stored_nodes = []
    for node in NODES:
        try:
            files = {'file': (filename, BytesIO(content))}
            data = {'file_id': file_id}
            r = requests.post(f"{node}/store", files=files, data=data, timeout=8)
            if r.status_code == 200:
                stored_nodes.append(node)
        except Exception as e:
            app.logger.warning("store failed on %s: %s", node, e)
    meta = load_meta()
    meta[file_id] = {'filename': filename, 'nodes': stored_nodes}
    save_meta(meta)
    return redirect(url_for('index'))

@app.route('/files/<file_id>')
def download(file_id):
    meta = load_meta()
    if file_id not in meta:
        return "<h3 style='color:red;'>File not found!</h3>"
    for node in meta[file_id]['nodes']:
        try:
            r = requests.get(f"{node}/store/{file_id}", stream=True, timeout=8)
            if r.status_code == 200:
                return send_file(BytesIO(r.content), as_attachment=True, download_name=meta[file_id]['filename'])
        except Exception as e:
            app.logger.warning("fetch failed from %s: %s", node, e)
    return "<h3 style='color:red;'>File unavailable on any node!</h3>"

@app.route('/checkpoint', methods=['POST'])
def checkpoint_all():
    results = {}
    for node in NODES:
        try:
            r = requests.post(f"{node}/checkpoint", timeout=10)
            results[node] = r.json()
        except:
            results[node] = "failed"
    summary = "<br>".join([f"{k}: {v}" for k, v in results.items()])
    return f"<h3 style='color:green;'>Checkpoint created on all nodes</h3><p>{summary}</p><a href='/'>⬅ Back</a>"

@app.route('/recover/<node_name>', methods=['POST'])
def recover_node(node_name):
    meta = load_meta()
    target_url = f"http://{node_name}:5100"
    for file_id, info in meta.items():
        if target_url not in info['nodes']:
            for donor in info['nodes']:
                try:
                    r = requests.get(f"{donor}/store/{file_id}", timeout=10)
                    if r.status_code == 200:
                        files = {'file': (info['filename'], BytesIO(r.content))}
                        data = {'file_id': file_id}
                        pr = requests.post(f"{target_url}/store", files=files, data=data, timeout=10)
                        if pr.status_code == 200:
                            info['nodes'].append(target_url)
                            break
                except:
                    continue
    save_meta(meta)
    return f"Recovery completed for {node_name}"

@app.route('/status')
def status():
    return jsonify({'nodes': NODES, 'files': load_meta()})

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
