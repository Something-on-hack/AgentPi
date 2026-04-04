import socket
import threading
import paramiko
import subprocess
import base64
import os


KEYS_DIR = 'keys'
# --- КОНФИГУРАЦИЯ ДЛЯ ФЕРМЫ СЕРВЕРОВ ---
# 1. Приватный ключ ЭТОГО сервера (Host Key - нужен для работы протокола SSH)
SERVER_HOST_KEY_FILE = os.path.join('keys', 'server_host_rsa')

# 2. Файл с публичным ключом админа (раскопируйте этот файл на все серверы)
ADMIN_PUB_KEY_FILE = os.path.join('keys', 'admin_public_key.pub')


# ---------------------------------------

class FleetSSHServer(paramiko.ServerInterface):
    def __init__(self, allowed_admin_key):
        self.event = threading.Event()
        self.allowed_admin_key = allowed_admin_key

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return 'publickey'

    def check_auth_publickey(self, username, key):
        print(f"[!] Попытка подключения админа (пользователь: {username})...")
        # Сверяем ключ, которым авторизуется клиент, с нашим разрешенным
        if key == self.allowed_admin_key:
            print("[+] Доступ разрешен: публичный ключ админа совпал.")
            return paramiko.AUTH_SUCCESSFUL

        print("[-] В доступе отказано: чужой ключ.")
        return paramiko.AUTH_FAILED

    def check_channel_shell_request(self, channel):
        print('Check channel shell')
        self.event.set()
        return True

    def check_pty_request(self, term, width, height, pixelwidth, pixelheight, modes):
        # Разрешаем запрос на выделение псевдо-терминала
        print('Check pty')
        return True

    def check_shell_request(self, channel):
        print('Check shell')
        self.event.set()
        return True

    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        print("[+] PTY request accepted")
        return True


def ensure_keys():
    if not os.path.exists(KEYS_DIR):
        print("[!] Папка 'keys' не найдена. Создаю..")

        os.makedirs(KEYS_DIR)

    if not os.path.exists(SERVER_HOST_KEY_FILE):
        print("[!] Генерация host key (RSA 4096)...")
        host_key = paramiko.RSAKey.generate(4096)

        host_key.write_private_key_file(SERVER_HOST_KEY_FILE)
        print(f"[+] Host key сохранён: {SERVER_HOST_KEY_FILE}")

    try:
        with open("admin_public_key.pub", "x") as f:
            print("Add the public key to the admin_public_key.pub")
            pass
    except FileExistsError:
        print("Check the correctness of the public key")

def load_admin_public_key(filepath):
    """Считывает открытый ключ админа из файла"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл публичного ключа админа не найден: {filepath}")

    with open(filepath, 'r') as f:
        key_string = f.read().strip()

    # Парсим строку вида "ssh-rsa AAAAB3..."
    key_type, key_data = key_string.split()[:2]
    return paramiko.RSAKey(data=base64.b64decode(key_data))


def start_node_server():

    # 1. Загружаем Host-ключ СЕРВЕРА (закрытый ключ узла)
    try:
        host_key = paramiko.RSAKey(filename=SERVER_HOST_KEY_FILE)
    except Exception as e:
        print(f"[-] Критическая ошибка: Не найден Host-ключ сервера ({SERVER_HOST_KEY_FILE}): {e}")
        return

    # 2. Загружаем разрешенный публичный ключ АДМИНА
    try:
        allowed_admin_key = load_admin_public_key(ADMIN_PUB_KEY_FILE)
    except Exception as e:
        print(f"[-] Критическая ошибка: {e}")
        return

    # Запускаем сокет
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', 2222))
        sock.listen(5)  # Готовы слушать входящие TCP соединения
        print("[*] Сервер-узел готов к приему команд от админа (Порт: 2222)...")
    except Exception as e:
        print(f"[-] Ошибка сети: {e}")
        return

    while True:  # Цикл для принятия новых подключений от админа
        try:
            client_sock, client_addr = sock.accept()
            print(f"\n[+] Входящее соединение от админа: {client_addr}")

            # Обрабатываем каждое подключение в отдельном потоке (для отказоустойчивости)
            t = threading.Thread(target=handle_admin_connection, args=(client_sock, host_key, allowed_admin_key))
            t.daemon = True
            t.start()
        except KeyboardInterrupt:
            print("\n[*] Остановка сервера.")
            break
        except Exception as e:
            print(f"[-] Ошибка принятия соединения: {e}")


def handle_admin_connection(client_sock, host_key, allowed_admin_key):
    try:
        client_addr = client_sock.getpeername()

        transport = paramiko.Transport(client_sock)
        #transport.auth_timeout(180.0)
        transport.add_server_key(host_key)
        server_interface = FleetSSHServer(allowed_admin_key)
        #server_interface.event.wait(30)

        try:
            transport.start_server(server=server_interface)
        except paramiko.SSHException as e:
            print(f"[-] Ошибка SSH: {e}")
            return

        channel = transport.accept(10)

        if channel is None:
            return

        server_interface.event.wait(5)
        if not server_interface.event.is_set():
            return

        channel.send(b"Connected to Node.\r\n> ")

        # Исполнение команд
        while True:
            if channel.closed:  # Проверка состояния канала
                print("Канал был закрыт.")
                break

            command = channel.recv(1024).decode('utf-8').strip()
            if not command:
                continue

            if command.lower() in ['exit', 'quit']:
                channel.send(b"Connection closed.\r\n")
                break

            print(f"[>] Исполнение команды: {command}")

            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()

                if stdout:
                    channel.send(stdout.replace(b'\n', b'\r\n'))
                if stderr:
                    channel.send(stderr.replace(b'\n', b'\r\n'))
            except Exception as e:
                channel.send(f"Command Error: {e}\r\n".encode('utf-8'))

            channel.send(b"> ")

    finally:
        print(f"[+] Клиент {client_addr} отключился.")
        try:
            channel.close()
        except:
            pass
        transport.close()


if __name__ == "__main__":
    start_node_server()