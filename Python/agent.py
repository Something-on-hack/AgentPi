import sys
import os

import paramiko
from paramiko import agent



class Agent(object):
    def __init__(self, ip):
        self.ip = ip
        self.ssh_client = None

        key = paramiko.RSAKey.generate(4096)
        if not os.path.exists(self.get_private_key_path()):
            self.save_private_key(key)
        if not os.path.exists(self.get_public_key_path()):
            self.save_public_key(key)

    def __del__(self):
        self.ssh_client.close()

    def open_ssh_connection(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.WarningPolicy())

        key=paramiko.RSAKey.from_private_key_file(self.get_private_key_path(), password=None)

        print("trying to connect to %s" % self.ip)
        self.ssh_client.connect(
            hostname=self.ip,
            username="vovan",
            # key_filename=self.get_public_key_path(),
            pkey=key,
            port=2222,
            timeout=10
        )
        print("Successfully connected to %s" % self.ip)

    def get_private_key_path(self):
        return os.path.join("keys", "private", self.ip.replace('.', '_'))

    def get_public_key_path(self):
        return os.path.join("keys", "public", self.ip.replace('.', '_') + ".pub")

    def save_private_key(self, key):
        with open(self.get_private_key_path(), "w") as f:
            key.write_private_key(f)

    def save_public_key(self, key):
        with open(self.get_public_key_path(), "w") as f:
            f.write("ssh-rsa " + key.get_base64())
