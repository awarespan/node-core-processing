import os
import sys
import paramiko
from stat import S_ISDIR
import dotenv

OPERATOR_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.operator")
if os.path.exists(OPERATOR_ENV):
    dotenv.load_dotenv(OPERATOR_ENV)

def upload_dir(sftp, local_dir, remote_dir):
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass
        
    for item in os.listdir(local_dir):
        if item == '__pycache__':
            continue
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        
        if os.path.isfile(local_path):
            sftp.put(local_path, remote_path)
            print(f"Uploaded {local_path} -> {remote_path}")
        elif os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path)

def main():
    host = os.getenv("PI_SSH_HOST", os.getenv("IP_ADDRESS", "192.168.0.125"))
    user = os.getenv("PI_SSH_USER", os.getenv("USERNAME", "benjamin"))
    pwd = os.getenv("PI_SSH_PASS", os.getenv("PASSWORD"))
    
    if not pwd:
        print("Error: PI_SSH_PASS or PASSWORD environment variable must be set", file=sys.stderr)
        sys.exit(1)
    
    transport = paramiko.Transport((host, 22))
    transport.connect(username=user, password=pwd)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    local_root = os.path.dirname(os.path.abspath(__file__))
    train_script = os.path.join(local_root, 'pi', 'train_autonomous.py')
    if os.path.exists(train_script):
        sftp.put(train_script, '/home/benjamin/edge-ai/train_autonomous.py')
        print("Uploaded train_autonomous.py")
        
    sftp.close()
    transport.close()

if __name__ == "__main__":
    main()
