import json

log_file = r"C:\Users\Admin\.gemini\antigravity-ide\brain\fc12ac2f-f926-459e-8b54-362e3c5b61f4\.system_generated\logs\transcript.jsonl"

with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        if 'git ' in line.lower() or 'push' in line.lower() or 'deploy' in line.lower():
            try:
                data = json.loads(line)
                tool_calls = data.get('tool_calls', [])
                for tc in tool_calls:
                    cmd = tc.get('args', {}).get('CommandLine', '')
                    if cmd:
                        print("FOUND COMMAND:", cmd)
            except Exception:
                pass
