from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
import threading
import socket
import json
import os
import hashlib
import time
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

class EliabyCryptApp(App):
    def build(self):
        self.title = 'EliabyCrypt'
        layout = BoxLayout(orientation='vertical', padding=10, spacing=8)
        self.label = Label(
            text='EliabyCrypt\nDigite seu apelido para começar',
            halign='center', size_hint_y=0.15, color=(1,1,1,1)
        )
        layout.add_widget(self.label)
        self.nome_input = TextInput(
            hint_text='Seu apelido',
            multiline=False, size_hint_y=0.1,
            background_color=(0.1,0.1,0.1,1),
            foreground_color=(1,1,1,1)
        )
        layout.add_widget(self.nome_input)
        btn_iniciar = Button(
            text='Iniciar Nó 🔐',
            size_hint_y=0.1,
            background_color=(0.2,0.2,0.2,1)
        )
        btn_iniciar.bind(on_press=self.iniciar)
        layout.add_widget(btn_iniciar)
        scroll = ScrollView(size_hint_y=0.5)
        self.chat = Label(
            text='', size_hint_y=None, halign='left',
            valign='top', color=(0.8,0.8,0.8,1),
            text_size=(350, None)
        )
        self.chat.bind(texture_size=self.chat.setter('size'))
        scroll.add_widget(self.chat)
        layout.add_widget(scroll)
        self.msg_input = TextInput(
            hint_text='Mensagem...',
            multiline=False, size_hint_y=0.1,
            background_color=(0.1,0.1,0.1,1),
            foreground_color=(1,1,1,1)
        )
        layout.add_widget(self.msg_input)
        btn_enviar = Button(
            text='Enviar',
            size_hint_y=0.08,
            background_color=(0.2,0.2,0.2,1)
        )
        btn_enviar.bind(on_press=self.enviar)
        layout.add_widget(btn_enviar)
        self.ip_input = TextInput(
            hint_text='IP para conectar',
            multiline=False, size_hint_y=0.08,
            background_color=(0.1,0.1,0.1,1),
            foreground_color=(1,1,1,1)
        )
        layout.add_widget(self.ip_input)
        btn_conectar = Button(
            text='Conectar',
            size_hint_y=0.08,
            background_color=(0.15,0.15,0.15,1)
        )
        btn_conectar.bind(on_press=self.conectar)
        layout.add_widget(btn_conectar)
        self.no = None
        return layout

    def iniciar(self, *args):
        nome = self.nome_input.text.strip() or 'Anônimo'
        from eliabycrypt_core import No, Identidade
        self.identidade = Identidade(nome)
        self.no = No(self.identidade, self.receber_msg)
        self.no.iniciar()
        self.label.text = f'✅ Nó ativo\nID: {self.identidade.node_id}\nIP: {self.identidade.ip}'
        self.adicionar_chat(f'[Sistema] Nó iniciado como {nome}')

    def receber_msg(self, de, texto):
        self.adicionar_chat(f'[{de}] {texto}')

    def adicionar_chat(self, texto):
        self.chat.text += texto + '\n'

    def enviar(self, *args):
        if not self.no:
            self.adicionar_chat('[!] Inicie o nó primeiro')
            return
        txt = self.msg_input.text.strip()
        if not txt:
            return
        nos = self.no.tabela.todos()
        if not nos:
            self.adicionar_chat('[!] Nenhum nó conectado')
            return
        dest = nos[0]
        self.no.enviar_para(dest['node_id'], txt)
        self.adicionar_chat(f'[Você] {txt}')
        self.msg_input.text = ''

    def conectar(self, *args):
        if not self.no:
            self.adicionar_chat('[!] Inicie o nó primeiro')
            return
        ip = self.ip_input.text.strip()
        if ip:
            self.no.conectar_manual(ip)
            self.adicionar_chat(f'[Sistema] Conectando em {ip}...')

if __name__ == '__main__':
    EliabyCryptApp().run()
