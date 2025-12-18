from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import mysql.connector as driver
import os
import requests
import threading
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, 
    get_jwt_identity, get_jwt, set_access_cookies, 
    unset_jwt_cookies, verify_jwt_in_request
)
from functools import wraps

app = Flask(__name__)

# --- CONFIGURAÇÃO SEGURA ---
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'db')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_ROOT_PASSWORD', 'admin123')
app.config['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'almoxarifado_db')

# --- CONFIGURAÇÃO JWT (NOVO) ---
app.config['SECRET_KEY'] = 'sua_chave_secreta_flask' # Troque em produção
app.config['JWT_SECRET_KEY'] = 'sua_chave_jwt_super_secreta' 
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False # Em produção, ative e configure
app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
app.config['JWT_COOKIE_SECURE'] = False # True se usar HTTPS

jwt = JWTManager(app)

# ... logo após jwt = JWTManager(app)

# Se o usuário não tiver token (cookie), manda pro login em vez de dar erro JSON
@jwt.unauthorized_loader
def missing_token_callback(error_string):
    return redirect(url_for('login'))

# Se o token venceu (sessão expirou), manda pro login também
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return redirect(url_for('login'))

# Se o token for inválido/falso
@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    return redirect(url_for('login'))

# --- ADAPTADOR MYSQL (MANTIDO IGUAL) ---
class MySQLAdapter:
    def __init__(self, app):
        self.app = app

    @property
    def connection(self):
        return driver.connect(
            host=self.app.config['MYSQL_HOST'],
            user=self.app.config['MYSQL_USER'],
            password=self.app.config['MYSQL_PASSWORD'],
            database=self.app.config['MYSQL_DATABASE']
        )

mysql = MySQLAdapter(app)

# --- DECORADORES DE PERMISSÃO (NOVO) ---
# Verifica se o usuário tem um dos cargos permitidos
def role_required(roles_permitidas):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            # Se o cargo do token não estiver na lista permitida
            if claims.get('cargo') not in roles_permitidas:
                # Se for requisição AJAX/API retorna JSON, se não, redireciona ou erro
                return jsonify({"msg": "Acesso negado para seu nível de usuário"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# --- FUNÇÃO AUXILIAR DE INICIALIZAÇÃO (CRIA ADMIN) ---
# Executar isso garante que existe um admin padrão
def inicializar_admin():
    try:
        conn = mysql.connection
        cursor = conn.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db")
        
        # Verifica se a tabela tem a coluna cargo, se não tiver (legado), idealmente alteraria aqui ou manualmente.
        # Vamos assumir que a tabela já foi criada corretamente ou ajustada.
        
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", ('admin@sistema.com',))
        admin = cursor.fetchone()
        
        if not admin:
            senha_hash = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO usuarios (nome, email, senha, cargo) VALUES (%s, %s, %s, %s)",
                ('Administrador', 'admin@sistema.com', senha_hash, 'admin')
            )
            conn.commit()
            print("--- Usuário ADMIN criado: admin@sistema.com / admin123 ---")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Aviso na inicialização do DB: {e}")

# Chame a função antes de iniciar (ou manualmente)
inicializar_admin() # Descomente se quiser rodar ao iniciar

# --- DADOS COMUNS (ALTERADO PARA FILTRAR VISÃO) ---
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
        SELECT p.*, f.nome as fornecedor_nome, u.nome as gestor_nome
        FROM produtos p
        LEFT JOIN fornecedores f ON p.fornecedor_id = f.id
        LEFT JOIN usuarios u ON p.gestor_id = u.id
        ORDER BY p.nome
    """)
    produtos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()
       
    # Apenas admin deveria ver a lista completa de usuários com detalhes, 
    # mas manteremos a query para preencher selects se necessário
    cursor.execute("SELECT id, nome, email, cargo FROM usuarios ORDER BY nome")
    usuarios = cursor.fetchall()
   
    cursor.close()
    conn.close() # Importante fechar aqui pois a connection property abre uma nova a cada chamada
   
    return {
        'total_itens': total_itens,
        'estoque_baixo_count': estoque_baixo_count,
        'produtos': produtos,
        'fornecedores': fornecedores,
        'usuarios': usuarios  
    }

# --- ROTA DE LOGIN (NOVO) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    # --- INÍCIO DO DIAGNÓSTICO ---
    print("=== TENTATIVA DE LOGIN ===")
    
    email = request.form.get('email')
    password = request.form.get('password')
    print(f"1. Dados recebidos do form -> Email: '{email}' | Senha digitada: '{password}'")

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    user = cursor.fetchone()
    
    cursor.close()
    conn.close()

    if user:
        print(f"2. Usuário encontrado no Banco -> ID: {user['id']} | Nome: {user['nome']}")
        print(f"3. Hash da senha no Banco: {user['senha']}")
        
        bateu = check_password_hash(user['senha'], password)
        print(f"4. A senha confere? {bateu}")
        
        if bateu:
            print("5. SUCESSO! Gerando token...")
            identity = str(user['id'])
            additional_claims = {"cargo": user['cargo'], "nome": user['nome']}
            access_token = create_access_token(identity=identity, additional_claims=additional_claims)
            
            resp = make_response(redirect(url_for('index')))
            set_access_cookies(resp, access_token)
            return resp
    else:
        print("2. Usuário NÃO encontrado no banco de dados.")

    print("=== FIM DA TENTATIVA (FALHA) ===")
    return render_template('login.html', erro="Credenciais Inválidas")

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    return resp

# --- ROTA PRINCIPAL (PROTEGIDA E ADAPTADA) ---
@app.route('/')
@jwt_required() # <--- Agora exige login
def index():
    # Pega dados do usuário logado
    claims = get_jwt()
    user_cargo = claims.get('cargo', 'vendedor')
    
    dados_comuns = get_dados_comuns()
       
    active_tab = request.args.get('tab', 'dashboard') 

    # Lógica de permissão de visualização de abas
    if user_cargo == 'vendedor' and active_tab in ['usuarios', 'fornecedores']:
        active_tab = 'dashboard' # Vendedor volta pro dashboard se tentar acessar outros
    
    # Se não for admin, não pode ver aba usuários
    if user_cargo != 'admin' and active_tab == 'usuarios':
        active_tab = 'dashboard'

    edit_produto_id = request.args.get('edit_produto')
    edit_fornecedor_id = request.args.get('edit_fornecedor')
    edit_usuario_id = request.args.get('edit_usuario') 
   
    produto_para_editar = None
    fornecedor_para_editar = None
    usuario_para_editar = None 
   
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")

    # Apenas carrega dados de edição se o usuário tiver permissão
    if edit_produto_id:
        cursor.execute("SELECT * FROM produtos WHERE id = %s", (edit_produto_id,))
        produto_para_editar = cursor.fetchone()
        active_tab = 'dashboard'
   
    if edit_fornecedor_id and user_cargo in ['admin', 'gestor']:
        cursor.execute("SELECT * FROM fornecedores WHERE id = %s", (edit_fornecedor_id,))
        fornecedor_para_editar = cursor.fetchone()
        active_tab = 'fornecedores'
   
    if edit_usuario_id and user_cargo == 'admin': 
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (edit_usuario_id,))
        usuario_para_editar = cursor.fetchone()
        active_tab = 'usuarios'

    cursor.close()
    conn.close()

    return render_template(
        'almoxarifado_dashboard.html',
        active_tab=active_tab,
        produto_para_editar=produto_para_editar,
        fornecedor_para_editar=fornecedor_para_editar,
        usuario_para_editar=usuario_para_editar,
        current_user_role=user_cargo, # <--- Passamos o cargo para o HTML esconder botões
        **dados_comuns
    )

# --- ROTAS DE REDIRECIONAMENTO ---
@app.route('/estoque')
@jwt_required()
def listar_produtos():
    return redirect(url_for('index'))

@app.route('/fornecedores', methods=['GET'])
@role_required(['admin', 'gestor']) # <--- Bloqueia Vendedor
def fornecedores_crud():
    edit_id = request.args.get('edit_id')
    if edit_id:
        return redirect(url_for('index', tab='fornecedores', edit_fornecedor=edit_id))
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/usuarios', methods=['GET'])
@role_required(['admin']) # <--- Apenas Admin
def usuarios_crud():
    edit_id = request.args.get('edit_id')
    if edit_id:
        return redirect(url_for('index', tab='usuarios', edit_usuario=edit_id))
    return redirect(url_for('index', tab='usuarios'))

@app.route('/editar/<int:produto_id>', methods=['GET'])
@jwt_required()
def editar_produto_get(produto_id):
    # Vendedor pode acessar aqui? Se for só para visualizar modal ok, 
    # mas o HTML deve bloquear os inputs se for vendedor.
    return redirect(url_for('index', edit_produto=produto_id))

# --- AÇÕES DE ESCRITA (PROTEGIDAS POR CARGO) ---

@app.route('/fornecedores/adicionar', methods=['POST'])
@role_required(['admin', 'gestor'])
def adicionar_fornecedor():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    # ... (seu código existente de insert) ...
    nome = request.form.get('nome')
    contato_nome = request.form.get('contato_nome')
    telefone = request.form.get('telefone')
    email = request.form.get('email')
    
    cursor.execute(
        "INSERT INTO fornecedores (nome, contato_nome, telefone, email) VALUES (%s, %s, %s, %s)",
        (nome, contato_nome, telefone, email)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/fornecedores/editar/<int:fornecedor_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def editar_fornecedor(fornecedor_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    contato_nome = request.form.get('contato_nome')
    telefone = request.form.get('telefone')
    email = request.form.get('email')
    
    cursor.execute(
        "UPDATE fornecedores SET nome=%s, contato_nome=%s, telefone=%s, email=%s WHERE id=%s",
        (nome, contato_nome, telefone, email, fornecedor_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/fornecedores/remover/<int:fornecedor_id>', methods=['POST'])
@role_required(['admin', 'gestor'])
def remover_fornecedor(fornecedor_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index', tab='fornecedores'))


# --- USUÁRIOS (SÓ ADMIN) - ALTERADO PARA HASH DE SENHA ---

@app.route('/usuarios/adicionar', methods=['POST'])
@role_required(['admin'])
def adicionar_usuario():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha_raw = request.form.get('senha') # Campo novo no form
    cargo = request.form.get('cargo')     # Campo novo no form (admin, gestor, vendedor)
    
    senha_hash = generate_password_hash(senha_raw)

    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, cargo) VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash, cargo)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao adicionar usuário: {e}")
    finally:
        cursor.close()
        conn.close()
   
    return redirect(url_for('index', tab='usuarios'))

@app.route('/usuarios/editar/<int:usuario_id>', methods=['POST'])
@role_required(['admin'])
def editar_usuario(usuario_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    email = request.form.get('email')
    cargo = request.form.get('cargo')
    nova_senha = request.form.get('senha') # Opcional no form

    try:
        if nova_senha:
            senha_hash = generate_password_hash(nova_senha)
            cursor.execute(
                "UPDATE usuarios SET nome=%s, email=%s, cargo=%s, senha=%s WHERE id=%s",
                (nome, email, cargo, senha_hash, usuario_id)
            )
        else:
             cursor.execute(
                "UPDATE usuarios SET nome=%s, email=%s, cargo=%s WHERE id=%s",
                (nome, email, cargo, usuario_id)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro: {e}")
    finally:
        cursor.close()
        conn.close()
       
    return redirect(url_for('index', tab='usuarios'))

@app.route('/usuarios/remover/<int:usuario_id>', methods=['POST'])
@role_required(['admin'])
def remover_usuario(usuario_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    try:
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index', tab='usuarios'))


# --- PRODUTOS (Gestor edita tudo, Vendedor só baixa) ---

@app.route('/adicionar', methods=['POST'])
@role_required(['admin', 'gestor']) # Vendedor não adiciona produto novo
def adicionar_produto():
    # ... (mesmo código, apenas protegido) ...
    nome = request.form.get('nome')
    quantidade = int(request.form['quantidade'])
    localizacao = request.form.get('localizacao')
    estoque_min = int(request.form['estoque_min'])
    fornecedor_id = request.form.get('fornecedor_id')
    gestor_id = request.form.get('gestor_id') 

    if fornecedor_id == '0': fornecedor_id = None
    if gestor_id == '0': gestor_id = None 

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute(
        "INSERT INTO produtos (nome, quantidade, localizacao, estoque_min, fornecedor_id, gestor_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (nome, quantidade, localizacao, estoque_min, fornecedor_id, gestor_id)
    )
    conn.commit()
    novo_produto_id = cursor.lastrowid
    cursor.close()
    conn.close()
   
    if quantidade < estoque_min:
        disparar_alerta_estoque_baixo(novo_produto_id, nome)
   
    return redirect(url_for('index'))

@app.route('/editar/<int:produto_id>', methods=['POST'])
@jwt_required() # <--- Aberto, mas validamos a ROLE dentro
def editar_produto(produto_id):
    claims = get_jwt()
    role = claims.get('cargo')

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    # Pega dados atuais para comparação
    cursor.execute("SELECT quantidade FROM produtos WHERE id = %s", (produto_id,))
    res = cursor.fetchone()
    qtd_antiga = res['quantidade'] if res else 0
    
    # Dados do Form
    try:
        nova_quantidade = int(request.form['quantidade'])
    except:
        nova_quantidade = qtd_antiga

    # Lógica do VENDEDOR (Só pode diminuir estoque)
    if role == 'vendedor':
        if nova_quantidade > qtd_antiga:
            # Vendedor tentou aumentar estoque
            return "Erro: Vendedores só podem realizar saída (diminuir quantidade).", 403
        
        # Vendedor só atualiza quantidade. Ignora outros campos.
        cursor.execute("UPDATE produtos SET quantidade=%s WHERE id=%s", (nova_quantidade, produto_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Alerta se baixou demais
        # (Para o vendedor, precisamos pegar o nome e estoque min de novo pois não vieram do form confiável)
        # ... Simplificação: assumindo que a lógica de alerta segue igual ...
        return redirect(url_for('index'))

    # Lógica GESTOR/ADMIN (Edita tudo)
    nome = request.form.get('nome')
    localizacao = request.form.get('localizacao')
    estoque_min = int(request.form['estoque_min'])
    fornecedor_id = request.form.get('fornecedor_id')
    gestor_id = request.form.get('gestor_id')
    
    if fornecedor_id == '0': fornecedor_id = None
    if gestor_id == '0': gestor_id = None 

    cursor.execute(
        """
        UPDATE produtos
        SET nome=%s, quantidade=%s, localizacao=%s, estoque_min=%s, fornecedor_id=%s, gestor_id=%s
        WHERE id=%s
        """,
        (nome, nova_quantidade, localizacao, estoque_min, fornecedor_id, gestor_id, produto_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
   
    if (nova_quantidade < estoque_min) and (qtd_antiga >= estoque_min):
        disparar_alerta_estoque_baixo(produto_id, nome)
   
    return redirect(url_for('index'))

@app.route('/remover/<int:produto_id>', methods=['POST'])
@role_required(['admin', 'gestor']) # Vendedor não deleta produto
def remover_produto(produto_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/realizar_saida/<int:produto_id>', methods=['POST'])
@jwt_required()
def realizar_saida(produto_id):
    try:
        qtd_saida = int(request.form.get('quantidade_saida'))
    except:
        return "Quantidade inválida", 400

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    # 1. Verifica estoque atual
    cursor.execute("SELECT quantidade, estoque_min, nome FROM produtos WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()
    
    if not produto:
        cursor.close()
        conn.close()
        return "Produto não encontrado", 404
        
    estoque_atual = produto['quantidade']
    
    # 2. Verifica se pode retirar
    if qtd_saida > estoque_atual:
        cursor.close()
        conn.close()
        return f"Erro: Tentativa de retirar {qtd_saida}, mas só existem {estoque_atual} em estoque.", 400
        
    # 3. Atualiza
    novo_estoque = estoque_atual - qtd_saida
    cursor.execute("UPDATE produtos SET quantidade = %s WHERE id = %s", (novo_estoque, produto_id))
    conn.commit()
    
    cursor.close()
    conn.close()
    
    # 4. Checa alerta
    if (novo_estoque < produto['estoque_min']) and (estoque_atual >= produto['estoque_min']):
        disparar_alerta_estoque_baixo(produto_id, produto['nome'])
        
    return redirect(url_for('index'))

# --- UTILITÁRIOS (MANTIDO IGUAL) ---

def chamar_microservico_email(subject, body):
    try:
        url = 'http://email_service:5001/send_email'
        payload = {'subject': subject, 'body': body}
        requests.post(url, json=payload, timeout=2)
    except Exception as e:
        print(f"Erro email: {e}")

def disparar_alerta_em_thread(subject, body):
    t = threading.Thread(target=chamar_microservico_email, args=[subject, body])
    t.start()

def disparar_alerta_estoque_baixo(produto_id, nome_produto):
    subject = f"ALERTA: Estoque Baixo (ID: {produto_id})"
    body = f"O produto '{nome_produto}' (ID: {produto_id}) está com estoque baixo."
    disparar_alerta_em_thread(subject, body)

if __name__ == '__main__':
    # inicializar_admin() # Opcional: roda uma vez para criar o admin
    app.run(
        host=os.environ.get('IP', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8080)),
        debug=True
    )