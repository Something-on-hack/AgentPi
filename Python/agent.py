import sys
import os

import paramiko
from paramiko import agent

def save_private_key(ip:str, key):
    with open(os.path.join("keys", "private", ip.replace('.', '_')), "w") as f:
        key.write_private_key(f)

def save_public_key(ip:str, key):
    with open(os.path.join("keys", "public", ip.replace('.', '_')), "w") as f:
        f.write(key.get_base64())

class Agent(object):
    def __init__(self, ip):
        self.ip = ip
        self.ssh_client = None

        key = paramiko.RSAKey.generate(4096)
        save_private_key(ip, key)
        save_public_key(ip, key)

    def open_ssh_connection(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key = paramiko.RSAKey.from_private_key_file(os.path.join("keys", "private", self.ip.replace('.', '_')))

        print("trying to connect to %s" % self.ip)
        self.ssh_client.connect(
            hostname=self.ip,
            username="AgentPi",
            pkey=key,
            port=22,
            timeout=10,
        )
        print("Successfully connected to %s" % self.ip)

