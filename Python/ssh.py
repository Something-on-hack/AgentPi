import paramiko
import matplotlib

#creating ssh-client
client = paramiko.SSHClient()

# need change
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

