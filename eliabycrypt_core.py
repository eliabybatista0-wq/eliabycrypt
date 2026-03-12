import socket, threading, json, os, hashlib, time, base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

PORTA_CHAT = 55444
PORTA_DISCO = 55445

class Cripto:
    def __init__(self):
        self.chave_privada = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        self.chave_publica = self.chave_privada.public_key()
    def exportar_publica(self):
        return self.chave_publica.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    def importar_publica(self, pem):
        return serialization.load_pem_public_key(pem.encode(), backend=default_backend())
    def criptografar(self, texto, chave_pub):
        chave_aes = os.urandom(32); iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(chave_aes), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor(); dados = texto.encode()
        pad = 16 - (len(dados) % 16); dados += bytes([pad]*pad)
        cifrado = enc.update(dados) + enc.finalize()
        chave_cifrada = chave_pub.encrypt(chave_aes, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        return {"c": base64.b64encode(cifrado).decode(), "k": base64.b64encode(chave_cifrada).decode(), "i": base64.b64encode(iv).decode()}
    def descriptografar(self, p):
        try:
            chave_aes = self.chave_privada.decrypt(base64.b64decode(p["k"]), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
            iv = base64.b64decode(p["i"]); cifrado = base64.b64decode(p["c"])
            cipher = Cipher(algorithms.AES(chave_aes), modes.CBC(iv), backend=default_backend())
            dec = cipher.decryptor(); dados = dec.update(cifrado) + dec.finalize()
            return dados[:-dados[-1]].decode()
        except: return "[erro]"

class Identidade:
    def __init__(self, apelido):
        self.apelido = apelido; self.cripto = Cripto()
        self.node_id = hashlib.sha256(self.cripto.exportar_publica().encode()).hexdigest()[:16]
        self.ip = self._ip()
    def _ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ip = s.getsockname()[0]; s.close(); return ip
        except: return "127.0.0.1"
    def cartao(self):
        return {"tipo":"cartao","apelido":self.apelido,"node_id":self.node_id,"chave_publica":self.cripto.exportar_publica(),"ip":self.ip}

class TabelaNos:
    def __init__(self): self._nos = {}; self._lock = threading.Lock()
    def adicionar(self, info):
        with self._lock: self._nos[info.get("node_id")] = {**info,"visto":time.time()}
    def obter(self, nid):
        with self._lock: return self._nos.get(nid)
    def todos(self):
        with self._lock: return list(self._nos.values())

class No:
    def __init__(self, identidade, callback):
        self.id = identidade; self.tabela = TabelaNos()
        self.callback = callback; self._vistas = set(); self._lock = threading.Lock()
    def iniciar(self):
        for t in [self._servidor_chat, self._servidor_disco, self._anunciar]:
            threading.Thread(target=t, daemon=True).start()
    def _anunciar(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        cartao = json.dumps(self.id.cartao()).encode()
        while True:
            try: s.sendto(cartao, ("255.255.255.255", PORTA_DISCO))
            except: pass
            time.sleep(8)
    def _servidor_disco(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.bind(("", PORTA_DISCO))
        except: return
        while True:
            try:
                dados, _ = s.recvfrom(65535); info = json.loads(dados.decode())
                if info.get("node_id") != self.id.node_id:
                    self.tabela.adicionar(info); self.callback("Sistema", f"Nó encontrado: {info['apelido']}")
            except: pass
    def _servidor_chat(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", PORTA_CHAT)); srv.listen(10)
        while True:
            try:
                conn, _ = srv.accept(); threading.Thread(target=self._tratar, args=(conn,), daemon=True).start()
            except: pass
    def _tratar(self, conn):
        try:
            dados = b""
            while True:
                chunk = conn.recv(65535)
                if not chunk: break
                dados += chunk
                try: json.loads(dados.decode()); break
                except: continue
            conn.close()
            if dados: self._processar(json.loads(dados.decode()))
        except: pass
    def _processar(self, p):
        mid = p.get("mid","")
        with self._lock:
            if mid in self._vistas: return
            self._vistas.add(mid)
        if p.get("tipo") == "msg" and p.get("dest") == self.id.node_id:
            texto = self.id.cripto.descriptografar(p["conteudo"])
            self.callback(p.get("rem_apelido","?"), texto)
        elif p.get("tipo") == "handshake":
            self.tabela.adicionar(p); self.callback("Sistema", f"Conectado: {p.get('apelido','?')}")
    def enviar_para(self, node_id, texto):
        no = self.tabela.obter(node_id)
        if not no: return
        chave = self.id.cripto.importar_publica(no["chave_publica"])
        conteudo = self.id.cripto.criptografar(texto, chave)
        mid = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        pacote = {"tipo":"msg","mid":mid,"rem_id":self.id.node_id,"rem_apelido":self.id.apelido,"dest":node_id,"conteudo":conteudo}
        self._enviar(no["ip"], pacote)
    def _enviar(self, ip, pacote):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(6); s.connect((ip, PORTA_CHAT)); s.sendall(json.dumps(pacote).encode()); s.close()
        except: pass
    def conectar_manual(self, ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(8); s.connect((ip, PORTA_CHAT))
            cartao = {**self.id.cartao(), "tipo":"handshake"}; s.sendall(json.dumps(cartao).encode()); s.close()
        except: pass
