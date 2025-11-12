from flask import Flask, request, jsonify
from transformers import MarianMTModel, MarianTokenizer
import threading
import logging
import socket
import threading
import time
import json
from datetime import datetime
import sys

# Отключаем лишние логи
logging.getLogger("transformers").setLevel(logging.ERROR)

app = Flask(__name__)

# Словарь моделей: (src_lang, tgt_lang) -> (tokenizer, model)
MODELS = {}
MODEL_LOCK = threading.Lock()

def get_translator(src_lang, tgt_lang):
    key = (src_lang, tgt_lang)
    if key not in MODELS:
        with MODEL_LOCK:
            if key not in MODELS:
                print(f"Загрузка модели {src_lang} → {tgt_lang}...")
                model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}"
                tokenizer = MarianTokenizer.from_pretrained(model_name)
                model = MarianMTModel.from_pretrained(model_name)
                MODELS[key] = (tokenizer, model)
                print(f"Модель {src_lang} → {tgt_lang} загружена.")
    return MODELS[key]

def translate_text(text, src, tgt):
    """Возвращает переведённый текст или raise Exception."""
    if not text.strip():
        return ""

    supported_pairs = {('ru', 'en'), ('en', 'ru')}
    if (src, tgt) not in supported_pairs:
        raise ValueError(f"Неподдерживаемая языковая пара: {src} → {tgt}")

    tokenizer, model = get_translator(src, tgt)
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    translated = model.generate(**inputs)
    result = tokenizer.decode(translated[0], skip_special_tokens=True)
    return result


def setup_sockets():
        global multicast_socket
        global multicast_group
        global multicast_port
        global udp_socket
        """Инициализация сокетов с улучшенной обработкой ошибок"""
        try:
            multicast_group = '224.1.1.1'
            multicast_port = 5007
            # Multicast сокет для группового чата
            multicast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            multicast_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.multicast_ttl)
        
          # Таймаут для неблокирующей работы
            
            # Подписка на multicast группу
            
        except:
            pass    

def send_group_message(message):
    """Отправка сообщения в групповой чат"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    data = {
        'type': 'group_message',
        'username': "переводичик",
        'message': message,
        'timestamp': timestamp
    }
        
    json_data = json.dumps(data).encode('utf-8')
    multicast_socket.sendto(json_data, (multicast_group, multicast_port))


def contains_english_letters(text):
    return any('a' <= c <= 'z' or 'A' <= c <= 'Z' for c in text)

def listen_group_messages():
        global udp_socket
        """Прослушивание групповых сообщений с улучшенной стабильностью"""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(('', multicast_port))
        udp_socket.settimeout(0.5)
        group = socket.inet_aton(multicast_group)
        mreq = group + socket.inet_aton('0.0.0.0')
        udp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        udp_socket.settimeout(100.0)

        while True:
            data, address = udp_socket.recvfrom(1024)
            message_data = json.loads(data.decode('utf-8'))
            print(data)
            
            if message_data['type'] == 'group_message':
                mess = message_data['message']
                if contains_english_letters(mess):
                    i = translate_text(mess, "en", 'ru')
                    if i != mess:
                        send_group_message(i)



if __name__ == "__main__":
    print("Запуск сервера перевода...")
    print("Поддерживаемые пары: ru↔en")
    print("Сервер будет доступен по адресу: http://<IP>:5000/translate")
    setup_sockets()     
    listen_group_messages()
    app.run(host='192.168.0.49', port=5007, threaded=True)
