from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import mysql.connector as driver
import os
import requests
import threading
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, 
    get_jwt_identity, get_jwt, set_access_cookies, 
    unset_jwt_cookies
)
from functools import wraps
from flask_caching import Cache

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'db')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_ROOT_PASSWORD', 'admin123')
app.config['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'almoxarifado_db')
app.config['SECRET_KEY'] = 'sua_chave_secreta_flask'
#jwt
app.config['JWT_SECRET_KEY'] = 'sua_chave_jwt_super_secreta' 
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False 
jwt = JWTManager(app)
#cache
app.config['CACHE_TYPE'] = 'FileSystemCache'
app.config['CACHE_DIR'] = '/tmp/flask_cache' # Pasta temporária do Linux
app.config['CACHE_DEFAULT_TIMEOUT'] = 300 # 5 minutos
app.config['CACHE_THRESHOLD'] = 500 

cache = Cache(app)

# --- TRATAMENTO DE ERROS JWT ---
@jwt.unauthorized_loader
def missing_token_callback(error_string): return redirect(url_for('login'))
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload): return redirect(url_for('login'))
@jwt.invalid_token_loader
def invalid_token_callback(error_string): return redirect(url_for('login'))

# --- ADAPTER MYSQL ---
class MySQLAdapter:
    def __init__(self, app): self.app = app
    @property
    def connection(self):
        return driver.connect(
            host=self.app.config['MYSQL_HOST'], 
            user=self.app.config['MYSQL_USER'], 
            password=self.app.config['MYSQL_PASSWORD'], 
            database=self.app.config['MYSQL_DATABASE']
        )

mysql = MySQLAdapter(app)

# --- DECORATOR DE PERMISSÃO ---
def role_required(roles_permitidas):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            if claims.get('cargo') not in roles_permitidas:
                return jsonify({"msg": "Acesso negado"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# --- UTILITÁRIOS (EMAILS) ---
def chamar_microservico_email(subject, body, to_email=None):
    try:
        payload = {'subject': subject, 'body': body}
        if to_email:
            payload['to_email'] = to_email
        requests.post('http://email_service:5001/send_email', json=payload, timeout=2)
    except Exception as e:
        print(f"Falha ao chamar microserviço de e-mail: {e}")

def enviar_boas_vindas_thread(nome, email, senha_raw):
    subject = "Bem-vindo ao Sistema de Almoxarifado - Credenciais"
    body = f"""Olá {nome},
Sua conta foi criada com sucesso.
Login: {email}
Senha: {senha_raw}
Por favor, altere sua senha após o primeiro acesso."""
    chamar_microservico_email(subject, body, to_email=email)

def disparar_alerta_estoque_baixo(pid, nome, destinatario_email):
    subject = f"ALERTA: Estoque Baixo (Item {pid})"
    body = f"O produto '{nome}' atingiu o nível mínimo de estoque."
    threading.Thread(target=chamar_microservico_email, args=[subject, body, destinatario_email]).start()

# --- DADOS COMUNS (COM LOCAIS) ---
def get_dados_comuns():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    cursor.execute("SELECT SUM(quantidade) as total FROM produtos")
    res = cursor.fetchone()
    total_itens = res['total'] if res and res['total'] else 0
   
    cursor.execute("SELECT COUNT(id) as count FROM produtos WHERE quantidade < estoque_min")
    res = cursor.fetchone()
    estoque_baixo_count = res['count'] if res else 0
    
    cursor.execute("""
        SELECT p.*, f.nome as fornecedor_nome, u.nome as gestor_nome, l.nome as local_nome
        FROM produtos p
        LEFT JOIN fornecedores f ON p.fornecedor_id = f.id
        LEFT JOIN usuarios u ON p.gestor_id = u.id
        LEFT JOIN locais l ON p.local_id = l.id
        ORDER BY p.nome
    """)
    produtos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()
    
    cursor.execute("SELECT * FROM locais ORDER BY nome")
    locais = cursor.fetchall()
    
    cursor.execute("SELECT id, nome, email, cargo FROM usuarios ORDER BY nome")
    usuarios = cursor.fetchall()
   
    cursor.close()
    conn.close()
   
    return {
        'total_itens': total_itens,
        'estoque_baixo_count': estoque_baixo_count,
        'produtos': produtos,
        'fornecedores': fornecedores,
        'locais': locais,
        'usuarios': usuarios  
    }

# --- FUNÇÃO CACHE
@cache.cached(timeout=300, key_prefix='dados_dashboard')
def get_dados_comuns_cache():
    """
    Esta função verifica se já existe o resultado salvo no arquivo.
    Se existir, retorna o arquivo (rápido).
    Se não, roda a get_dados_comuns(), salva no arquivo e retorna.
    """
    return get_dados_comuns()

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET': return render_template('login.html')
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and check_password_hash(user['senha'], password):
        token = create_access_token(identity=str(user['id']), additional_claims={"cargo": user['cargo'], "nome": user['nome']})
        resp = make_response(redirect(url_for('index')))
        set_access_cookies(resp, token)
        return resp
    return render_template('login.html', erro="Credenciais Inválidas")

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    return resp

@app.route('/minha_conta', methods=['POST'])
@jwt_required()
def minha_conta():
    usuario_id = get_jwt_identity()
    nova_senha = request.form.get('senha')
    novo_email = request.form.get('email')
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("USE almoxarifado_db")
    try:
        if novo_email: cursor.execute("UPDATE usuarios SET email = %s WHERE id = %s", (novo_email, usuario_id))
        if nova_senha and nova_senha.strip():
            sh = generate_password_hash(nova_senha)
            cursor.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (sh, usuario_id))
        conn.commit()
        cache.delete('dados_dashboard')
    except: pass
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# --- ROTA PRINCIPAL (INDEX) ---
@app.route('/')
@jwt_required()
def index():
    claims = get_jwt()
    user_cargo = claims.get('cargo', 'vendedor')
    
    # Lógica de Abas
    active_tab = request.args.get('tab', 'dashboard') 
    if user_cargo == 'vendedor': active_tab = 'dashboard'
    if user_cargo != 'admin' and active_tab == 'usuarios': active_tab = 'dashboard'

    # Lógica de Edição
    edit_produto_id = request.args.get('edit_produto')
    edit_fornecedor_id = request.args.get('edit_fornecedor')
    edit_local_id = request.args.get('edit_local')
    edit_usuario_id = request.args.get('edit_usuario')
    erro_msg = request.args.get('erro_msg')
    
    produto_para_editar = None
    fornecedor_para_editar = None
    local_para_editar = None
    usuario_para_editar = None
    email_alerta_atual = ""

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    # Buscas pontuais (Edição não usa cache pois precisa ser imediato)
    if edit_produto_id:
        cursor.execute("SELECT * FROM produtos WHERE id = %s", (edit_produto_id,))
        produto_para_editar = cursor.fetchone()
        active_tab = 'dashboard'
    
    if edit_fornecedor_id and user_cargo in ['admin', 'gestor']:
        cursor.execute("SELECT * FROM fornecedores WHERE id = %s", (edit_fornecedor_id,))
        fornecedor_para_editar = cursor.fetchone()
        active_tab = 'fornecedores'

    if edit_local_id and user_cargo in ['admin', 'gestor']:
        cursor.execute("SELECT * FROM locais WHERE id = %s", (edit_local_id,))
        local_para_editar = cursor.fetchone()
        active_tab = 'locais'
        
    if edit_usuario_id and user_cargo == 'admin':
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (edit_usuario_id,))
        usuario_para_editar = cursor.fetchone()
        active_tab = 'usuarios'

    if user_cargo == 'admin':
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'email_alerta'")
        res = cursor.fetchone()
        if res: email_alerta_atual = res['valor']

    cursor.close()
    conn.close()

    # Chamamos a versão cacheada. Se o cache existir, nem bate no banco.
    dados = get_dados_comuns_cache()
    
    return render_template('almoxarifado_dashboard.html', 
                           active_tab=active_tab, 
                           produto_para_editar=produto_para_editar, 
                           fornecedor_para_editar=fornecedor_para_editar,
                           local_para_editar=local_para_editar,
                           usuario_para_editar=usuario_para_editar, 
                           current_user_role=user_cargo,
                           config_email_alerta=email_alerta_atual,
                           erro_msg=erro_msg,
                           **dados)

# --- ROTAS DE CONFIGURAÇÃO ---
@app.route('/config/atualizar_email', methods=['POST'])
@role_required(['admin'])
def atualizar_email_alerta():
    novo_email = request.form.get('email_alerta')
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("REPLACE INTO configuracoes (chave, valor) VALUES ('email_alerta', %s)", (novo_email,))
        conn.commit()
        cache.delete('dados_dashboard')
    except Exception as e: print(f"Erro config: {e}")
    finally: cursor.close(); conn.close()
    return redirect(url_for('index', tab='usuarios'))

# --- ROTAS DE LOCAIS ---
@app.route('/locais/adicionar', methods=['POST'])
@role_required(['admin', 'gestor'])
def adicionar_local():
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("INSERT INTO locais (nome) VALUES (%s)", (request.form.get('nome'),))
        conn.commit()

        cache.delete('dados_dashboard')
    except: pass
    cursor.close(); conn.close()
    return redirect(url_for('index', tab='locais'))

@app.route('/locais/editar/<int:local_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def editar_local(local_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    cursor.execute("UPDATE locais SET nome=%s WHERE id=%s", (request.form.get('nome'), local_id))
    conn.commit(); cursor.close(); conn.close()
    cache.delete('dados_dashboard')
    return redirect(url_for('index', tab='locais'))

@app.route('/locais/remover/<int:local_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def remover_local(local_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("DELETE FROM locais WHERE id=%s", (local_id,))
        conn.commit()
        cache.delete('dados_dashboard')
    except: pass
    cursor.close(); conn.close()
    return redirect(url_for('index', tab='locais'))

# --- ROTAS DE PRODUTOS ---
@app.route('/adicionar', methods=['POST'])
@role_required(['admin', 'gestor'])
def adicionar_produto():
    nome = request.form.get('nome')
    quantidade = request.form['quantidade']
    local_id = request.form.get('local_id')
    if local_id == '0': local_id = None
    estoque_min = request.form['estoque_min']
    fornecedor_id = request.form.get('fornecedor_id')
    gestor_id = request.form.get('gestor_id')
    if fornecedor_id == '0': fornecedor_id = None
    if gestor_id == '0': gestor_id = None

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    cursor.execute("INSERT INTO produtos (nome, quantidade, local_id, estoque_min, fornecedor_id, gestor_id) VALUES (%s, %s, %s, %s, %s, %s)", 
                   (nome, quantidade, local_id, estoque_min, fornecedor_id, gestor_id))
    conn.commit()
    cache.delete('dados_dashboard')
    id_prod = cursor.lastrowid
    
    if int(quantidade) < int(estoque_min):
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'email_alerta'")
        cfg = cursor.fetchone()
        destinatario = cfg['valor'] if cfg else "audemarioestudante@gmail.com"
        disparar_alerta_estoque_baixo(id_prod, nome, destinatario)
    
    cursor.close(); conn.close()
    return redirect(url_for('index'))

@app.route('/editar/<int:produto_id>', methods=['POST'])
@jwt_required()
def editar_produto(produto_id):
    claims = get_jwt()
    role = claims.get('cargo')
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    cursor.execute("SELECT quantidade, nome FROM produtos WHERE id = %s", (produto_id,))
    prod_antigo = cursor.fetchone()
    qtd_antiga = prod_antigo['quantidade'] if prod_antigo else 0
    nome_prod = prod_antigo['nome'] if prod_antigo else "Produto"

    nova_quantidade = 0
    novo_minimo = 0
    
    if role == 'vendedor':
        nova_quantidade = int(request.form['quantidade'])
        cursor.execute("SELECT estoque_min FROM produtos WHERE id = %s", (produto_id,))
        res = cursor.fetchone()
        novo_minimo = res['estoque_min'] if res else 0
        cursor.execute("UPDATE produtos SET quantidade=%s WHERE id=%s", (nova_quantidade, produto_id))
    else:
        nome_prod = request.form.get('nome')
        nova_quantidade = int(request.form['quantidade'])
        local_id = request.form.get('local_id')
        if local_id == '0': local_id = None
        novo_minimo = int(request.form['estoque_min'])
        forn = request.form.get('fornecedor_id')
        gest = request.form.get('gestor_id')
        if forn == '0': forn = None
        if gest == '0': gest = None
        
        cursor.execute("UPDATE produtos SET nome=%s, quantidade=%s, local_id=%s, estoque_min=%s, fornecedor_id=%s, gestor_id=%s WHERE id=%s",
                       (nome_prod, nova_quantidade, local_id, novo_minimo, forn, gest, produto_id))
    
    conn.commit()
    cache.delete('dados_dashboard')

    if (nova_quantidade < novo_minimo) and (qtd_antiga >= novo_minimo):
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'email_alerta'")
        cfg = cursor.fetchone()
        destinatario = cfg['valor'] if cfg else "audemarioestudante@gmail.com"
        disparar_alerta_estoque_baixo(produto_id, nome_prod, destinatario)

    cursor.close(); conn.close()
    return redirect(url_for('index'))

@app.route('/remover/<int:produto_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def remover_produto(produto_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
    conn.commit(); cursor.close(); conn.close()
    cache.delete('dados_dashboard')
    return redirect(url_for('index'))

@app.route('/realizar_saida/<int:produto_id>', methods=['POST'])
@jwt_required()
def realizar_saida(produto_id):
    try: qtd_saida = int(request.form.get('quantidade_saida'))
    except: return "Quantidade inválida", 400

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute("SELECT quantidade, estoque_min, nome FROM produtos WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()
    
    if produto:
        if qtd_saida > produto['quantidade']: 
            cursor.close(); conn.close()
            return "Erro: Estoque insuficiente", 400
        novo_estoque = produto['quantidade'] - qtd_saida
        cursor.execute("UPDATE produtos SET quantidade = %s WHERE id = %s", (novo_estoque, produto_id))
        conn.commit()
        cache.delete('dados_dashboard')
        
        if (novo_estoque < produto['estoque_min']) and (produto['quantidade'] >= produto['estoque_min']):
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'email_alerta'")
            cfg = cursor.fetchone()
            destinatario = cfg['valor'] if cfg else "audemarioestudante@gmail.com"
            disparar_alerta_estoque_baixo(produto_id, produto['nome'], destinatario)
            
    cursor.close(); conn.close()
    return redirect(url_for('index'))

# --- ROTAS DE FORNECEDORES ---
@app.route('/fornecedores/adicionar', methods=['POST'])
@role_required(['admin', 'gestor'])
def adicionar_fornecedor():
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    cursor.execute("INSERT INTO fornecedores (nome, contato_nome, telefone, email) VALUES (%s, %s, %s, %s)", 
                   (request.form.get('nome'), request.form.get('contato_nome'), request.form.get('telefone'), request.form.get('email')))
    conn.commit(); cursor.close(); conn.close()
    cache.delete('dados_dashboard')
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/fornecedores/editar/<int:fornecedor_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def editar_fornecedor(fornecedor_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    cursor.execute("UPDATE fornecedores SET nome=%s, contato_nome=%s, telefone=%s, email=%s WHERE id=%s", 
                   (request.form.get('nome'), request.form.get('contato_nome'), request.form.get('telefone'), request.form.get('email'), fornecedor_id))
    conn.commit(); cursor.close(); conn.close()
    cache.delete('dados_dashboard')
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/fornecedores/remover/<int:fornecedor_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def remover_fornecedor(fornecedor_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    try: cursor.execute("DELETE FROM fornecedores WHERE id=%s", (fornecedor_id,)); conn.commit()
    except: pass
    cursor.close(); conn.close()
    return redirect(url_for('index', tab='fornecedores'))

# --- ROTAS DE USUÁRIOS ---
@app.route('/usuarios/adicionar', methods=['POST'])
@role_required(['admin'])
def adicionar_usuario():
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    try:
        sh = generate_password_hash(request.form.get('senha'))
        cursor.execute("INSERT INTO usuarios (nome, email, senha, cargo) VALUES (%s, %s, %s, %s)",
                       (request.form.get('nome'), request.form.get('email'), sh, request.form.get('cargo')))
        conn.commit()
        cache.delete('dados_dashboard')
        threading.Thread(target=enviar_boas_vindas_thread, args=[request.form.get('nome'), request.form.get('email'), request.form.get('senha')]).start()
    except Exception as e: print(f"Erro: {e}")
    finally: cursor.close(); conn.close()
    return redirect(url_for('index', tab='usuarios'))

@app.route('/usuarios/editar/<int:usuario_id>', methods=['POST'])
@role_required(['admin'])
def editar_usuario(usuario_id):
    conn = mysql.connection; cursor = conn.cursor(); cursor.execute("USE almoxarifado_db")
    try:
        if request.form.get('senha'):
            sh = generate_password_hash(request.form.get('senha'))
            cursor.execute("UPDATE usuarios SET nome=%s, email=%s, cargo=%s, senha=%s WHERE id=%s",
                           (request.form.get('nome'), request.form.get('email'), request.form.get('cargo'), sh, usuario_id))
        else:
            cursor.execute("UPDATE usuarios SET nome=%s, email=%s, cargo=%s WHERE id=%s",
                           (request.form.get('nome'), request.form.get('email'), request.form.get('cargo'), usuario_id))
        conn.commit()
        cache.delete('dados_dashboard')
    except: pass
    cursor.close(); conn.close()
    return redirect(url_for('index', tab='usuarios'))

@app.route('/usuarios/remover/<int:usuario_id>', methods=['POST'])
@role_required(['admin'])
def remover_usuario(usuario_id):
    conn = mysql.connection; cursor = conn.cursor(dictionary=True); cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("SELECT cargo FROM usuarios WHERE id = %s", (usuario_id,))
        usuario_alvo = cursor.fetchone()
        if usuario_alvo and usuario_alvo['cargo'] == 'admin':
            cursor.execute("SELECT COUNT(*) as qtd FROM usuarios WHERE cargo = 'admin'")
            if cursor.fetchone()['qtd'] <= 1:
                return redirect(url_for('index', tab='usuarios', erro_msg="ERRO: Impossível excluir o único Admin."))
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conn.commit()
        cache.delete('dados_dashboard')
    except Exception as e: print(e)
    finally: cursor.close(); conn.close()
    return redirect(url_for('index', tab='usuarios'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)