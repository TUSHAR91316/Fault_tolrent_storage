# node/app.py
from flask import Flask, request, jsonify, send_file
import os, json
from io import BytesIO

app = Flask(__name__)
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

META_FILE = os.path.join(DATA_DIR, "node_meta.json")
if not os.path.exists(META_FILE):
    with open(META_FILE, "w") as f:
        json.dump({}, f)

def load_meta():
    with open(META_FILE, "r") as f:
        return json.load(f)

def save_meta(m):
    with open(META_FILE, "w") as f:
        json.dump(m, f)

# Store file on node
@app.route('/store', methods=['POST'])
def store():
    file = request.files.get('file')
    file_id = request.form.get('file_id')
    if not file or not file_id:
        return jsonify({'error': 'Missing file or file_id'}), 400

    filepath = os.path.join(DATA_DIR, f"{file_id}_{file.filename}")
    file.save(filepath)

    meta = load_meta()
    meta[file_id] = {'filename': file.filename, 'path': filepath}
    save_meta(meta)

    return jsonify({'status': 'stored', 'file': file.filename}), 200

# Retrieve file
@app.route('/store/<file_id>', methods=['GET'])
def retrieve(file_id):
    meta = load_meta()
    if file_id not in meta:
        return jsonify({'error': 'File not found'}), 404
    file_info = meta[file_id]
    with open(file_info['path'], 'rb') as f:
        return send_file(BytesIO(f.read()), download_name=file_info['filename'], as_attachment=True)

# Create checkpoint
@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    meta = load_meta()
    ckpt_file = os.path.join(DATA_DIR, f"checkpoint_{len(meta)}.json")
    with open(ckpt_file, 'w') as f:
        json.dump(meta, f)
    return jsonify({'status': 'checkpoint saved', 'file': ckpt_file})

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5100)
