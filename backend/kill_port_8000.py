import subprocess
import re
import os
import signal

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
                pids.add(parts[-1])
        return list(pids)
    except Exception:
        return []

pids = get_pids_for_port(8000)
print("Found PIDs on port 8000:", pids)
for pid in pids:
    pid_int = int(pid)
    try:
        print(f"Terminating PID {pid_int}...")
        os.kill(pid_int, signal.SIGTERM)
        print(f"Successfully killed PID {pid_int}")
    except Exception as e:
        print(f"Failed to kill PID {pid_int} using SIGTERM: {e}")
        try:
            # Fallback to taskkill on Windows
            subprocess.check_call(f'taskkill /F /PID {pid_int}', shell=True)
            print(f"Successfully killed PID {pid_int} using taskkill")
        except Exception as e2:
            print(f"Failed to kill PID {pid_int} using taskkill: {e2}")
