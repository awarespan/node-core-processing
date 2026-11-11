import os
import sys
import paramiko
from paramiko import SSHClient, AutoAddPolicy
import dotenv

# Load operator environment if present
OPERATOR_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.operator")
if os.path.exists(OPERATOR_ENV):
    dotenv.load_dotenv(OPERATOR_ENV)

def run_ssh(host, user, pwd, command):
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(host, username=user, password=pwd, timeout=10)
    
    stdin, stdout, stderr = client.exec_command(command)
    
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    
    with open("ssh_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Exit status: {exit_status}\n")
        if out:
            f.write("STDOUT:\n")
            f.write(out)
        if err:
            f.write("STDERR:\n")
            f.write(err)
        
    client.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Provide a command")
        sys.exit(1)
    
    host = os.getenv("PI_SSH_HOST", os.getenv("IP_ADDRESS", "192.168.0.125"))
    user = os.getenv("PI_SSH_USER", os.getenv("USERNAME", "benjamin"))
    pwd = os.getenv("PI_SSH_PASS", os.getenv("PASSWORD"))
    
    if not pwd:
        print("Error: PI_SSH_PASS or PASSWORD environment variable must be set", file=sys.stderr)
        sys.exit(1)
        
    cmd = " ".join(sys.argv[1:])
    run_ssh(host, user, pwd, cmd)
