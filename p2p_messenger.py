# p2p_messenger.py
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
        self.peers = {}  # {ip: {"socket": socket, "last_seen": timestamp}}
        
        # История сообщений
        self.chat_history = {
            "group": {
                "Общий чат": [],
                "Техподдержка": []
            },
            "private": {}  # {ip: [messages]}
        }
        
        self.group_chats = {
            "Общий чат": set(),
            "Техподдержка": set()
        }
        self.current_chat = "Общий чат"
        self.chat_type = "group"  # "group" или "private"
        
        # Сетевые настройки
        self.listening_port = 8888
        self.broadcast_port = 8889
        self.broadcast_ip = "255.255.255.255"
        
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
        self.root.title(f"P2P Мессенджер - {self.username}")
        self.root.geometry("900x600")
        
        # Основной фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Левая панель (чаты и пользователи)
        left_frame = ttk.Frame(main_frame, width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        # Информация о пользователе
        user_frame = ttk.LabelFrame(left_frame, text="Мой профиль")
        user_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(user_frame, text=f"IP: {self.username}").pack(anchor=tk.W)
        ttk.Label(user_frame, text=f"Порт: {self.listening_port}").pack(anchor=tk.W)
        
        # Групповые чаты
        group_frame = ttk.LabelFrame(left_frame, text="Групповые чаты")
        group_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.group_listbox = tk.Listbox(group_frame, height=4)
        self.group_listbox.pack(fill=tk.BOTH, expand=True)
        for group in self.group_chats:
            self.group_listbox.insert(tk.END, group)
        self.group_listbox.bind('<<ListboxSelect>>', self.on_group_select)
        
        # Пользователи онлайн
        users_frame = ttk.LabelFrame(left_frame, text="Пользователи онлайн")
        users_frame.pack(fill=tk.BOTH, expand=True)
        
        self.users_listbox = tk.Listbox(users_frame)
        self.users_listbox.pack(fill=tk.BOTH, expand=True)
        self.users_listbox.bind('<<ListboxSelect>>', self.on_user_select)
        
        # Правая панель (чат)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Заголовок чата
        self.chat_header = ttk.Label(right_frame, text="Общий чат", 
                                   font=('Arial', 12, 'bold'))
        self.chat_header.pack(fill=tk.X, pady=(0, 5))
        
        # Область сообщений
        self.chat_area = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, 
                                                 state=tk.DISABLED)
        self.chat_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Панель ввода сообщения
        input_frame = ttk.Frame(right_frame)
        input_frame.pack(fill=tk.X)
        
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', self.send_message)
        
        self.send_button = ttk.Button(input_frame, text="Отправить", 
                                    command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Кнопка обновления списка пользователей
        ttk.Button(left_frame, text="Найти пользователей", 
                  command=self.broadcast_presence).pack(fill=tk.X, pady=5)
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
    def start_network(self):
        """Запуск сетевых функций"""
        # Запуск прослушивания входящих сообщений
        self.listening_thread = threading.Thread(target=self.start_listening, daemon=True)
        self.listening_thread.start()
        
        # Запуск широковещательного оповещения
        self.broadcast_thread = threading.Thread(target=self.broadcast_presence_loop, daemon=True)
        self.broadcast_thread.start()
        
        # Начальное широковещательное сообщение
        self.broadcast_presence()
        self.update_status("Поиск пользователей в сети...")
        
    def start_listening(self):
        """Прослушивание входящих сообщений"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', self.listening_port))
            
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    message = json.loads(data.decode('utf-8'))
                    self.handle_message(message, addr)
                except Exception as e:
                    print(f"Ошибка при получении сообщения: {e}")
    
    def handle_message(self, message, addr):
        """Обработка входящих сообщений"""
        msg_type = message.get('type')
        sender_ip = addr[0]
        
        if msg_type == 'presence':
            self.handle_presence(sender_ip, message)
        elif msg_type == 'message':
            self.handle_chat_message(sender_ip, message)
    
    def handle_presence(self, sender_ip, message):
        """Обработка сообщения о присутствии"""
        if sender_ip != self.username:  # Игнорируем свои сообщения
            self.peers[sender_ip] = {
                "last_seen": time.time(),
                "username": sender_ip
            }
            
            # Инициализируем историю приватного чата если ее нет
            if sender_ip not in self.chat_history["private"]:
                self.chat_history["private"][sender_ip] = []
            
            # Добавляем в список пользователей если его нет
            self.root.after(0, self.update_users_list)
            
            # Отправляем ответное присутствие
            self.send_presence(sender_ip)
    
    def handle_chat_message(self, sender_ip, message):
        """Обработка сообщения чата"""
        chat_type = message.get('chat_type')
        content = message.get('content')
        timestamp = message.get('timestamp')
        
        # Сохраняем сообщение в историю
        self.save_message(sender_ip, content, timestamp, chat_type, message.get('group_name', ''))
        
        # Отображаем сообщение если открыт соответствующий чат
        if chat_type == 'group':
            group_name = message.get('group_name')
            if self.chat_type == 'group' and self.current_chat == group_name:
                self.display_message(sender_ip, content, timestamp, 'group', group_name)
        elif chat_type == 'private':
            if (self.chat_type == 'private' and self.current_chat == sender_ip) or \
               (self.chat_type == 'private' and self.current_chat == message.get('target')):
                self.display_message(sender_ip, content, timestamp, 'private', sender_ip)
    
    def save_message(self, sender, content, timestamp, chat_type, group_name=""):
        """Сохранение сообщения в историю"""
        if chat_type == 'group':
            if group_name in self.chat_history["group"]:
                self.chat_history["group"][group_name].append({
                    'sender': sender,
                    'content': content,
                    'timestamp': timestamp,
                    'type': 'group'
                })
        elif chat_type == 'private':
            target_ip = sender
            if target_ip in self.chat_history["private"]:
                self.chat_history["private"][target_ip].append({
                    'sender': sender,
                    'content': content,
                    'timestamp': timestamp,
                    'type': 'private'
                })
    
    def broadcast_presence_loop(self):
        """Цикл широковещательного оповещения"""
        while True:
            self.broadcast_presence()
            time.sleep(10)  # Каждые 10 секунд
    
    def broadcast_presence(self):
        """Широковещательное оповещение о присутствии"""
        message = {
            'type': 'presence',
            'username': self.username,
            'timestamp': time.time()
        }
        self.broadcast_message(message)
    
    def send_presence(self, target_ip):
        """Отправка присутствия конкретному пользователю"""
        message = {
            'type': 'presence',
            'username': self.username,
            'timestamp': time.time()
        }
        self.send_direct_message(target_ip, message)
    
    def send_message(self, event=None):
        """Отправка сообщения"""
        content = self.message_entry.get().strip()
        if not content:
            return
            
        self.message_entry.delete(0, tk.END)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if self.chat_type == 'group':
            self.send_group_message(content, self.current_chat, timestamp)
        elif self.chat_type == 'private':
            self.send_private_message(content, self.current_chat, timestamp)
        
        # Сохраняем и отображаем свое сообщение
        self.save_message(self.username, content, timestamp, self.chat_type, self.current_chat)
        self.display_message(self.username, content, timestamp, self.chat_type, self.current_chat)
    
    def send_group_message(self, content, group_name, timestamp):
        """Отправка сообщения в групповой чат"""
        message = {
            'type': 'message',
            'chat_type': 'group',
            'group_name': group_name,
            'content': content,
            'sender': self.username,
            'timestamp': timestamp
        }
        self.broadcast_message(message)
    
    def send_private_message(self, content, target_ip, timestamp):
        """Отправка приватного сообщения"""
        message = {
            'type': 'message',
            'chat_type': 'private',
            'content': content,
            'sender': self.username,
            'timestamp': timestamp,
            'target': target_ip
        }
        self.send_direct_message(target_ip, message)
    
    def broadcast_message(self, message):
        """Широковещательная рассылка сообщения"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(json.dumps(message).encode('utf-8'), 
                           (self.broadcast_ip, self.broadcast_port))
        except Exception as e:
            self.update_status(f"Ошибка отправки: {e}")
    
    def send_direct_message(self, target_ip, message):
        """Отправка сообщения конкретному пользователю"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(json.dumps(message).encode('utf-8'), 
                           (target_ip, self.listening_port))
        except Exception as e:
            self.update_status(f"Ошибка отправки {target_ip}: {e}")
    
    def display_message(self, sender, content, timestamp, chat_type, chat_name):
        """Отображение сообщения в чате"""
        self.root.after(0, self._display_message, sender, content, timestamp, chat_type, chat_name)
    
    def _display_message(self, sender, content, timestamp, chat_type, chat_name):
        """Внутренний метод для отображения сообщения (вызывается в основном потоке)"""
        # Проверяем, активен ли соответствующий чат
        if (chat_type == 'group' and self.current_chat == chat_name and self.chat_type == 'group') or \
           (chat_type == 'private' and self.current_chat == sender and self.chat_type == 'private'):
            
            self.chat_area.config(state=tk.NORMAL)
            
            # Форматируем сообщение
            if sender == self.username:
                display_text = f"[{timestamp}] Вы: {content}\n"
                tag = "own_message"
            else:
                display_text = f"[{timestamp}] {sender}: {content}\n"
                tag = "other_message"
            
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
                    sender = "Вы" if msg['sender'] == self.username else msg['sender']
                    display_text = f"[{msg['timestamp']}] {sender}: {msg['content']}\n"
                    tag = "own_message" if msg['sender'] == self.username else "other_message"
                    self.chat_area.insert(tk.END, display_text, tag)
        
        elif self.chat_type == 'private':
            if self.current_chat in self.chat_history["private"]:
                for msg in self.chat_history["private"][self.current_chat]:
                    sender = "Вы" if msg['sender'] == self.username else msg['sender']
                    display_text = f"[{msg['timestamp']}] {sender}: {msg['content']}\n"
                    tag = "own_message" if msg['sender'] == self.username else "other_message"
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
            self.update_status(f"Выбран чат: {group_name}")
    
    def on_user_select(self, event):
        """Обработка выбора пользователя для приватного чата"""
        selection = self.users_listbox.curselection()
        if selection:
            user_ip = self.users_listbox.get(selection[0])
            if user_ip != self.username:
                self.current_chat = user_ip
                self.chat_type = "private"
                self.chat_header.config(text=f"Приватный чат с {user_ip}")
                
                # Инициализируем историю чата если ее нет
                if user_ip not in self.chat_history["private"]:
                    self.chat_history["private"][user_ip] = []
                
                self.load_chat_history()
                self.update_status(f"Чат с {user_ip}")
    
    def update_users_list(self):
        """Обновление списка пользователей"""
        self.users_listbox.delete(0, tk.END)
        
        # Добавляем себя в начало
        self.users_listbox.insert(tk.END, f"{self.username} (Вы)")
        
        # Добавляем других пользователей
        current_time = time.time()
        expired_peers = []
        
        for ip, info in self.peers.items():
            # Проверяем актуальность (30 секунд)
            if current_time - info['last_seen'] < 30:
                self.users_listbox.insert(tk.END, ip)
            else:
                expired_peers.append(ip)
        
        # Удаляем устаревших пользователей
        for ip in expired_peers:
            del self.peers[ip]
            # Не удаляем историю чата при отключении пользователя
        
        self.update_status(f"Найдено пользователей: {len(self.peers)}")
    
    def update_status(self, message):
        """Обновление статусной строки"""
        self.status_var.set(message)
    
    def run(self):
        """Запуск приложения"""
        # Настраиваем теги для цветного отображения сообщений
        self.chat_area.tag_config("own_message", foreground="blue")
        self.chat_area.tag_config("other_message", foreground="green")
        
        self.root.mainloop()

if __name__ == "__main__":
    app = P2PMessenger()
    app.run()