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
from node_runtime.monitoring.telegram_notify import send_message
ok = send_message('🧪 <b>AWARESPAN Pipeline Verification</b>: Edge-to-Telegram notification channel verified.')
print('Telegram test delivery status:', ok)
" """

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()

