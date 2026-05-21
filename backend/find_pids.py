import subprocess
import re

def get_pids_for_port(port):
    try:
        output = subprocess.check_output(f'netstat -ano | findstr LISTENING | findstr :{port}', shell=True).decode()
        pids = set()
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'\s+', line)
            if len(parts) >= 5:
                # The PID is the last element
                pids.add(parts[-1])
        return list(pids)
    except Exception as e:
        return []

print("PIDs for port 8000 (Backend):", get_pids_for_port(8000))
print("PIDs for port 3000 (Frontend):", get_pids_for_port(3000))
