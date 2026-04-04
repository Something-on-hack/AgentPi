import os
from datetime import time

import time
import paramiko

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
            pkey=key,
            port=2222,
            timeout=60
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

    def execute_command(self, command):
        """Отправляет команду через открытый shell-канал и возвращает вывод."""
        if not self.ssh_client:
            raise Exception("SSH connection not established")

        # Запрашиваем интерактивную оболочку
        channel = self.ssh_client.get_transport().open_session()
        # channel.settimeout(None)
        channel.get_pty()
        channel.invoke_shell()

        # Ждём приглашение (или просто небольшую паузу для инициализации)
        time.sleep(0.5)

        # Очищаем буфер (приветственное сообщение сервера)
        if channel.recv_ready():
            channel.recv(65535)

        # Отправляем команду + перевод строки
        channel.send(command)

        # Ждём выполнения и собираем вывод
        output = ""
        while True:
            time.sleep(0.1)
            if channel.recv_ready():
                data = channel.recv(1024).decode('utf-8', errors='ignore')
                output += data
                # Если появилось приглашение "> " – значит команда завершена
                if output.strip().endswith('>'):
                    break
            else:
                # Если ничего не пришло, но прошло достаточно времени – выходим
                time.sleep(0.5)
                if not channel.recv_ready():
                    break

        # Убираем из вывода последнее приглашение и саму команду (опционально)
        lines = output.splitlines()
        # Если первая строка содержит введённую команду, удаляем её
        if lines and command in lines[0]:
            lines.pop(0)
        # Удаляем последнее приглашение "> "
        while lines and lines[-1].strip() == '>':
            lines.pop()

        return "\n".join(lines)
