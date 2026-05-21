import subprocess

def get_process_info_ps(pid):
    try:
        cmd = f'powershell -Command "Get-CimInstance Win32_Process -Filter \\"ProcessId = {pid}\\" | Select-Object CommandLine, Name | Format-List"'
        output = subprocess.check_output(cmd, shell=True).decode()
        return output.strip()
    except Exception as e:
        return str(e)

print("Process 15592 (Port 8000) Info:")
print(get_process_info_ps(15592))
print("\nProcess 30932 (Port 3000) Info:")
print(get_process_info_ps(30932))
