import sys, json
from graphify.extract import collect_files, extract
from pathlib import Path

def run_ast():
    code_files = []
    detect_path = Path('.graphify_detect.json')
    if not detect_path.exists():
        print("Error: .graphify_detect.json not found")
        return

    detect = json.loads(detect_path.read_text(encoding='utf-8'))
    for f in detect.get('files', {}).get('code', []):
        p = Path(f)
        code_files.extend(collect_files(p) if p.is_dir() else [p])

    if code_files:
        print(f"Extracting AST from {len(code_files)} files...")
        result = extract(code_files)
        Path('.graphify_ast.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f"AST: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    else:
        Path('.graphify_ast.json').write_text(json.dumps({'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}), encoding='utf-8')
        print('No code files - skipping AST extraction')

if __name__ == "__main__":
    run_ast()
