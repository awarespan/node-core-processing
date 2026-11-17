import os
import paramiko
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.operator"))

PI_HOST = os.environ.get("PI_HOST", "10.42.0.1")
PI_USER = os.environ.get("PI_USER", "benjamin")
PI_PASS = os.environ.get("PI_PASSWORD")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS)

cmd = """/home/benjamin/edge-ai/pi/.venv/bin/python3 -c "
import sys
sys.path.append('/home/benjamin/SIP')
from shared.config.settings import get_settings
s = get_settings()
print('BOT_TOKEN:', s.bot_token[:10] if s.bot_token else 'EMPTY')
print('PRIMARY_CHAT_ID:', s.primary_chat_id)
" """

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()

