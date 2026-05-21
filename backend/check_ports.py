import socket

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except socket.error:
            return False

print("Port 8000 (Backend) is open:", check_port(8000))
print("Port 3000 (Frontend) is open:", check_port(3000))
