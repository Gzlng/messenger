# messenger.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import threading
import json
import time
from datetime import datetime

class P2PMessenger:
    def __init__(self):
        self.username = self.get_local_ip()
        self.peers = {}  # {ip: {"socket": socket, "connected": bool}}
        self.connections = []  # Активные TCP соединения
        
        # История сообщений
        self.chat_history = {
            "group": {
                "Общий чат": [],
                "Техподдержка": []
            },
            "private": {}
        }
        
        self.current_chat = "Общий чат"
        self.chat_type = "group"
        
        # Сетевые настройки
        self.port = 8888
        self.broadcast_port = 8889
        
        self.setup_gui()
        self.start_network()
        
    def get_local_ip(self):
        """Получение локального IP-адреса"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root = tk.Tk()
        self.root.title(f"Мессенджер - {self.username}")
        self.root.geometry("800x500")
        
        # Основной фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель
        left_frame = ttk.Frame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        # Информация о пользователе
        user_frame = ttk.LabelFrame(left_frame, text="Мой профиль")
        user_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(user_frame, text=f"IP: {self.username}").pack(anchor=tk.W)
        
        # Групповые чаты
        group_frame = ttk.LabelFrame(left_frame, text="Групповые чаты")
        group_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.group_listbox = tk.Listbox(group_frame, height=4)
        self.group_listbox.pack(fill=tk.BOTH, expand=True)
        for group in self.chat_history["group"]:
            self.group_listbox.insert(tk.END, group)
        self.group_listbox.bind('<<ListboxSelect>>', self.on_group_select)
        self.group_listbox.selection_set(0)  # Выбираем первый чат по умолчанию
        
        # Пользователи
        users_frame = ttk.LabelFrame(left_frame, text="Пользователи")
        users_frame.pack(fill=tk.BOTH, expand=True)
        
        self.users_listbox = tk.Listbox(users_frame)
        self.users_listbox.pack(fill=tk.BOTH, expand=True)
        self.users_listbox.bind('<<ListboxSelect>>', self.on_user_select)
        
        # Правая панель
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Заголовок чата
        self.chat_header = ttk.Label(right_frame, text="Общий чат", 
                                   font=('Arial', 12, 'bold'))
        self.chat_header.pack(fill=tk.X, pady=(0, 5))
        
        # Область сообщений
        self.chat_area = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD)
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.chat_area.config(state=tk.DISABLED)
        
        # Панель ввода
        input_frame = ttk.Frame(right_frame)
        input_frame.pack(fill=tk.X)
        
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', self.send_message)
        
        ttk.Button(input_frame, text="Отправить", 
                  command=self.send_message).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Панель управления
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame, text="Добавить IP", 
                  command=self.add_ip_dialog).pack(fill=tk.X)
        ttk.Button(control_frame, text="Обновить", 
                  command=self.manual_discovery).pack(fill=tk.X, pady=2)
        
        # Статус
        self.status_var = tk.StringVar(value="Готов к работе")
        ttk.Label(self.root, textvariable=self.status_var, 
                 relief=tk.SUNKEN).pack(fill=tk.X, side=tk.BOTTOM)
    
    def add_ip_dialog(self):
        """Диалог для ручного добавления IP"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить пользователя")
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите IP-адрес:").pack(pady=5)
        ip_entry = ttk.Entry(dialog, width=20)
        ip_entry.pack(pady=5)
        ip_entry.focus()
        
        def add_ip():
            ip = ip_entry.get().strip()
            if ip and ip != self.username:
                self.connect_to_peer(ip)
            dialog.destroy()
        
        ttk.Button(dialog, text="Добавить", command=add_ip).pack(pady=5)
        ip_entry.bind('<Return>', lambda e: add_ip())
    
    def start_network(self):
        """Запуск сетевых функций"""
        # Запуск TCP сервера для входящих соединений
        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()
        
        # Запуск обнаружения в сети
        self.discovery_thread = threading.Thread(target=self.network_discovery, daemon=True)
        self.discovery_thread.start()
        
        self.update_status("Сервер запущен. Ищу пользователей...")
    
    def start_server(self):
        """Запуск TCP сервера"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', self.port))
            server_socket.listen(5)
            
            while True:
                client_socket, addr = server_socket.accept()
                ip = addr[0]
                
                if ip != self.username:
                    self.peers[ip] = {"socket": client_socket, "connected": True}
                    self.connections.append(client_socket)
                    
                    # Запускаем обработчик сообщений для этого клиента
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, ip),
                        daemon=True
                    )
                    client_thread.start()
                    
                    self.root.after(0, self.update_users_list)
                    self.update_status(f"Подключен: {ip}")
                    
        except Exception as e:
            self.update_status(f"Ошибка сервера: {e}")
    
    def handle_client(self, client_socket, ip):
        """Обработка сообщений от клиента"""
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                    
                try:
                    message = json.loads(data)
                    self.process_message(message, ip)
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            print(f"Ошибка с клиентом {ip}: {e}")
        finally:
            client_socket.close()
            if ip in self.peers:
                self.peers[ip]["connected"] = False
            self.root.after(0, self.update_users_list)
    
    def process_message(self, message, sender_ip):
        """Обработка входящего сообщения"""
        msg_type = message.get('type')
        
        if msg_type == 'discovery':
            # Ответ на обнаружение - устанавливаем соединение
            self.connect_to_peer(sender_ip)
            
        elif msg_type == 'message':
            content = message.get('content', '')
            timestamp = message.get('timestamp', '')
            chat_type = message.get('chat_type', 'group')
            target = message.get('target', '')
            
            # Сохраняем сообщение
            self.save_message(sender_ip, content, timestamp, chat_type, target)
            
            # Отображаем если открыт соответствующий чат
            if chat_type == 'group':
                if self.chat_type == 'group' and self.current_chat == target:
                    self.display_message(sender_ip, content, timestamp)
            elif chat_type == 'private':
                if (self.chat_type == 'private' and self.current_chat == sender_ip):
                    self.display_message(sender_ip, content, timestamp)
    
    def save_message(self, sender, content, timestamp, chat_type, target=""):
        """Сохранение сообщения в историю"""
        if chat_type == 'group':
            if target in self.chat_history["group"]:
                self.chat_history["group"][target].append({
                    'sender': sender,
                    'content': content,
                    'timestamp': timestamp,
                    'type': 'group'
                })
        elif chat_type == 'private':
            if sender not in self.chat_history["private"]:
                self.chat_history["private"][sender] = []
            self.chat_history["private"][sender].append({
                'sender': sender,
                'content': content,
                'timestamp': timestamp,
                'type': 'private'
            })
    
    def network_discovery(self):
        """Обнаружение пользователей в сети"""
        time.sleep(1)  # Даем время серверу запуститься
        
        # Сканируем локальную сеть
        base_ip = '.'.join(self.username.split('.')[:-1]) + '.'
        
        for i in range(1, 255):
            ip = base_ip + str(i)
            if ip != self.username:
                self.connect_to_peer(ip)
    
    def connect_to_peer(self, ip):
        """Подключение к другому пользователю"""
        if ip in self.peers and self.peers[ip].get("connected"):
            return
            
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(2)
            client_socket.connect((ip, self.port))
            
            self.peers[ip] = {"socket": client_socket, "connected": True}
            self.connections.append(client_socket)
            
            # Запускаем обработчик
            client_thread = threading.Thread(
                target=self.handle_client, 
                args=(client_socket, ip),
                daemon=True
            )
            client_thread.start()
            
            # Отправляем сообщение обнаружения
            discovery_msg = {
                'type': 'discovery',
                'sender': self.username
            }
            self.send_to_peer(ip, discovery_msg)
            
            self.root.after(0, self.update_users_list)
            self.update_status(f"Подключен к: {ip}")
            
        except:
            pass  # Пользователь недоступен - это нормально
    
    def send_to_peer(self, ip, message):
        """Отправка сообщения конкретному пользователю"""
        try:
            if ip in self.peers and self.peers[ip]["connected"]:
                data = json.dumps(message).encode('utf-8')
                self.peers[ip]["socket"].send(data)
        except:
            self.peers[ip]["connected"] = False
            self.root.after(0, self.update_users_list)
    
    def broadcast_message(self, message):
        """Отправка сообщения всем подключенным пользователям"""
        for ip in list(self.peers.keys()):
            if self.peers[ip]["connected"]:
                self.send_to_peer(ip, message)
    
    def send_message(self, event=None):
        """Отправка сообщения"""
        content = self.message_entry.get().strip()
        if not content:
            return
            
        self.message_entry.delete(0, tk.END)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if self.chat_type == 'group':
            message = {
                'type': 'message',
                'chat_type': 'group',
                'content': content,
                'sender': self.username,
                'timestamp': timestamp,
                'target': self.current_chat
            }
            self.broadcast_message(message)
            
        elif self.chat_type == 'private':
            message = {
                'type': 'message', 
                'chat_type': 'private',
                'content': content,
                'sender': self.username,
                'timestamp': timestamp,
                'target': self.current_chat
            }
            self.send_to_peer(self.current_chat, message)
        
        # Сохраняем и отображаем свое сообщение
        self.save_message(self.username, content, timestamp, self.chat_type, self.current_chat)
        self.display_message(self.username, content, timestamp)
    
    def display_message(self, sender, content, timestamp):
        """Отображение сообщения в чате"""
        self.chat_area.config(state=tk.NORMAL)
        
        if sender == self.username:
            display_text = f"[{timestamp}] Вы: {content}\n"
            tag = "own"
        else:
            display_text = f"[{timestamp}] {sender}: {content}\n"
            tag = "other"
        
        self.chat_area.insert(tk.END, display_text, tag)
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)
    
    def load_chat_history(self):
        """Загрузка истории текущего чата"""
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.delete(1.0, tk.END)
        
        if self.chat_type == 'group':
            if self.current_chat in self.chat_history["group"]:
                for msg in self.chat_history["group"][self.current_chat]:
                    sender_display = "Вы" if msg['sender'] == self.username else msg['sender']
                    display_text = f"[{msg['timestamp']}] {sender_display}: {msg['content']}\n"
                    tag = "own" if msg['sender'] == self.username else "other"
                    self.chat_area.insert(tk.END, display_text, tag)
        
        elif self.chat_type == 'private':
            if self.current_chat in self.chat_history["private"]:
                for msg in self.chat_history["private"][self.current_chat]:
                    sender_display = "Вы" if msg['sender'] == self.username else msg['sender']
                    display_text = f"[{msg['timestamp']}] {sender_display}: {msg['content']}\n"
                    tag = "own" if msg['sender'] == self.username else "other"
                    self.chat_area.insert(tk.END, display_text, tag)
        
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)
    
    def on_group_select(self, event):
        """Обработка выбора группового чата"""
        selection = self.group_listbox.curselection()
        if selection:
            group_name = self.group_listbox.get(selection[0])
            self.current_chat = group_name
            self.chat_type = "group"
            self.chat_header.config(text=f"Групповой чат: {group_name}")
            self.load_chat_history()
    
    def on_user_select(self, event):
        """Обработка выбора пользователя"""
        selection = self.users_listbox.curselection()
        if selection:
            user_info = self.users_listbox.get(selection[0])
            if "(Вы)" not in user_info:
                ip = user_info.split(" ")[0]  # Извлекаем IP из строки
                self.current_chat = ip
                self.chat_type = "private"
                self.chat_header.config(text=f"Приватный чат с {ip}")
                
                if ip not in self.chat_history["private"]:
                    self.chat_history["private"][ip] = []
                
                self.load_chat_history()
    
    def update_users_list(self):
        """Обновление списка пользователей"""
        self.users_listbox.delete(0, tk.END)
        
        # Добавляем себя
        self.users_listbox.insert(tk.END, f"{self.username} (Вы)")
        
        # Добавляем подключенных пользователей
        for ip, info in self.peers.items():
            if info.get("connected"):
                status = "✓" if info["connected"] else "✗"
                self.users_listbox.insert(tk.END, f"{ip} {status}")
        
        self.update_status(f"Пользователей: {len([p for p in self.peers.values() if p.get('connected')])}")
    
    def manual_discovery(self):
        """Ручное обновление списка пользователей"""
        threading.Thread(target=self.network_discovery, daemon=True).start()
        self.update_status("Поиск пользователей...")
    
    def update_status(self, message):
        """Обновление статуса"""
        def update():
            self.status_var.set(message)
        self.root.after(0, update)
    
    def run(self):
        """Запуск приложения"""
        # Настраиваем цвета сообщений
        self.chat_area.tag_config("own", foreground="blue")
        self.chat_area.tag_config("other", foreground="green")
        
        # Загружаем историю начального чата
        self.load_chat_history()
        
        self.root.mainloop()

if __name__ == "__main__":
    print("Запуск мессенджера...")
    print("Для подключения других пользователей:")
    print("1. Запустите программу на других компьютерах в той же сети")
    print("2. Или используйте кнопку 'Добавить IP' для ручного ввода")
    app = P2PMessenger()
    app.run()