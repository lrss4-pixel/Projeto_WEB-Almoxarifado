from flask import Flask, render_template, request, redirect, url_for
import mysql.connector as driver # <--- MUDAMOS AQUI: demos um apelido 'driver'
import os
import requests
import threading

app = Flask(__name__)

# Configuração Segura
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'db')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_ROOT_PASSWORD', 'admin123')
app.config['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'almoxarifado_db')

# --- NOSSO ADAPTADOR CORRIGIDO ---
class MySQLAdapter:
    def __init__(self, app):
        self.app = app

    @property
    def connection(self):
        # AQUI ESTAVA O ERRO: Agora usamos 'driver' em vez de 'mysql'
        return driver.connect(
            host=self.app.config['MYSQL_HOST'],
            user=self.app.config['MYSQL_USER'],
            password=self.app.config['MYSQL_PASSWORD'],
            database=self.app.config['MYSQL_DATABASE']
        )

# Inicializa nosso adaptador (Mantemos o nome 'mysql' para o resto do seu código funcionar)
mysql = MySQLAdapter(app)

# -----------------------------------------------------------
# DAQUI PARA BAIXO O CÓDIGO CONTINUA IGUAL (def get_dados_comuns...)

def get_dados_comuns():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    cursor.execute("SELECT SUM(quantidade) as total FROM produtos")
    total_itens_result = cursor.fetchone()
    total_itens = total_itens_result['total'] if total_itens_result['total'] else 0
   
    cursor.execute("SELECT COUNT(id) as count FROM produtos WHERE quantidade < estoque_min")
    estoque_baixo_result = cursor.fetchone()
    estoque_baixo_count = estoque_baixo_result['count']
      
    cursor.execute("""
        SELECT
            p.*,
            f.nome as fornecedor_nome,
            u.nome as gestor_nome
        FROM produtos p
        LEFT JOIN fornecedores f ON p.fornecedor_id = f.id
        LEFT JOIN usuarios u ON p.gestor_id = u.id
        ORDER BY p.nome
    """)
    produtos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()
       
    cursor.execute("SELECT * FROM usuarios ORDER BY nome")
    usuarios = cursor.fetchall()
   
    cursor.close()
   
    return {
        'total_itens': total_itens,
        'estoque_baixo_count': estoque_baixo_count,
        'produtos': produtos,
        'fornecedores': fornecedores,
        'usuarios': usuarios  
    }

@app.route('/')
def index():
    """
    A ROTA PRINCIPAL.
    Renderiza o app e decide qual aba mostrar.
    """
     
    dados_comuns = get_dados_comuns()
       
    active_tab = request.args.get('tab', 'dashboard') 

    edit_produto_id = request.args.get('edit_produto')
    edit_fornecedor_id = request.args.get('edit_fornecedor')
    edit_usuario_id = request.args.get('edit_usuario') 
   
    produto_para_editar = None
    fornecedor_para_editar = None
    usuario_para_editar = None 
   
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("USE almoxarifado_db")

    if edit_produto_id:
        cursor.execute("SELECT * FROM produtos WHERE id = %s", (edit_produto_id,))
        produto_para_editar = cursor.fetchone()
        active_tab = 'dashboard'
   
    if edit_fornecedor_id:
        cursor.execute("SELECT * FROM fornecedores WHERE id = %s", (edit_fornecedor_id,))
        fornecedor_para_editar = cursor.fetchone()
        active_tab = 'fornecedores'
   
    if edit_usuario_id: 
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
        usuario_para_editar=usuario_para_editar, # Novo
        **dados_comuns
    )

# --- ROTAS DE REDIRECIONAMENTO (Não mexem no banco, mantém igual) ---
@app.route('/estoque')
def listar_produtos():
    return redirect(url_for('index'))

@app.route('/fornecedores', methods=['GET'])
def fornecedores_crud():
    edit_id = request.args.get('edit_id')
    if edit_id:
        return redirect(url_for('index', tab='fornecedores', edit_fornecedor=edit_id))
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/usuarios', methods=['GET']) 
def usuarios_crud():
    edit_id = request.args.get('edit_id')
    if edit_id:
        return redirect(url_for('index', tab='usuarios', edit_usuario=edit_id))
    return redirect(url_for('index', tab='usuarios'))

@app.route('/editar/<int:produto_id>', methods=['GET'])
def editar_produto_get(produto_id):
    return redirect(url_for('index', edit_produto=produto_id))

# --- INÍCIO DAS CORREÇÕES DE BANCO DE DADOS ---

@app.route('/fornecedores/adicionar', methods=['POST'])
def adicionar_fornecedor():
    conn = mysql.connection  # 1. Cria conexão
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    contato_nome = request.form.get('contato_nome')
    telefone = request.form.get('telefone')
    email = request.form.get('email')
    
    cursor.execute(
        "INSERT INTO fornecedores (nome, contato_nome, telefone, email) VALUES (%s, %s, %s, %s)",
        (nome, contato_nome, telefone, email)
    )
    conn.commit()  # 2. Salva na conexão certa
    
    cursor.close()
    conn.close()   # 3. Fecha
    return redirect(url_for('index', tab='fornecedores'))

@app.route('/fornecedores/editar/<int:fornecedor_id>', methods=['POST'])
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
def remover_fornecedor(fornecedor_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    try:
        cursor.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
        conn.commit()
    except Exception as e:
        conn.rollback() # Rollback na conexão correta
        print(f"Erro ao remover fornecedor: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index', tab='fornecedores'))


@app.route('/usuarios/adicionar', methods=['POST'])
def adicionar_usuario():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    email = request.form.get('email')
    
    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
            (nome, email, '!')
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
def editar_usuario(usuario_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    nome = request.form.get('nome')
    email = request.form.get('email')

    try:
        cursor.execute(
            "UPDATE usuarios SET nome=%s, email=%s WHERE id=%s",
            (nome, email, usuario_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao editar usuário: {e}")
    finally:
        cursor.close()
        conn.close()
       
    return redirect(url_for('index', tab='usuarios'))

@app.route('/usuarios/remover/<int:usuario_id>', methods=['POST'])
def remover_usuario(usuario_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    try:
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao remover usuário: {e}")
    finally:
        cursor.close()
        conn.close()
       
    return redirect(url_for('index', tab='usuarios'))

@app.route('/adicionar', methods=['POST'])
def adicionar_produto():
    nome = request.form.get('nome')
    quantidade = int(request.form['quantidade'])
    localizacao = request.form.get('localizacao')
    estoque_min = int(request.form['estoque_min'])
    fornecedor_id = request.form.get('fornecedor_id')
    gestor_id = request.form.get('gestor_id') 

    if fornecedor_id == '0': fornecedor_id = None
    if gestor_id == '0': gestor_id = None 

    # --- CORREÇÃO AQUI ---
    conn = mysql.connection  # 1. Pega a conexão e segura ela
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("USE almoxarifado_db")
    cursor.execute(
        "INSERT INTO produtos (nome, quantidade, localizacao, estoque_min, fornecedor_id, gestor_id) VALUES (%s, %s, %s, %s, %s, %s)",
        (nome, quantidade, localizacao, estoque_min, fornecedor_id, gestor_id)
    )
    
    conn.commit() # 2. Salva usando a conexão CORRETA (conn)
   
    novo_produto_id = cursor.lastrowid
    
    cursor.close()
    conn.close()  # 3. Fecha a conexão
    # ---------------------
   
    if quantidade < estoque_min:
        disparar_alerta_estoque_baixo(novo_produto_id, nome)
   
    return redirect(url_for('index'))

@app.route('/editar/<int:produto_id>', methods=['POST'])
def editar_produto(produto_id):
    # 1. Cria a conexão e mantém ela aberta
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("USE almoxarifado_db")
   
    nome = request.form.get('nome')
    quantidade = int(request.form['quantidade'])
    localizacao = request.form.get('localizacao')
    estoque_min = int(request.form['estoque_min'])
    fornecedor_id = request.form.get('fornecedor_id')
    gestor_id = request.form.get('gestor_id') 
   
    if fornecedor_id == '0': fornecedor_id = None
    if gestor_id == '0': gestor_id = None 

    # Busca a quantidade antiga antes de atualizar
    cursor.execute("SELECT quantidade FROM produtos WHERE id = %s", (produto_id,))
    resultado = cursor.fetchone()
    quantidade_antiga = resultado['quantidade'] if resultado else 0

    cursor.execute(
        """
        UPDATE produtos
        SET nome=%s, quantidade=%s, localizacao=%s, estoque_min=%s, fornecedor_id=%s, gestor_id=%s
        WHERE id=%s
        """,
        (nome, quantidade, localizacao, estoque_min, fornecedor_id, gestor_id, produto_id)
    )
    
    conn.commit() # 2. Salva as alterações
    
    cursor.close()
    conn.close()  # 3. Fecha a conexão explicitamente
   
    # Lógica de alerta (fora do banco)
    if (quantidade < estoque_min) and (quantidade_antiga >= estoque_min):
        disparar_alerta_estoque_baixo(produto_id, nome)
   
    return redirect(url_for('index'))

@app.route('/remover/<int:produto_id>', methods=['POST'])
def remover_produto(produto_id):
    # 1. Cria a conexão
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("USE almoxarifado_db")
    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
    
    conn.commit() # 2. Salva
    
    cursor.close()
    conn.close()  # 3. Fecha
    
    return redirect(url_for('index'))


# --- As funções abaixo já estavam corretas para o Docker, mantive igual ---

def chamar_microservico_email(subject, body):
    try:
        # Nota: 'email_service' é o nome do container definido no docker-compose
        url = 'http://email_service:5001/send_email'
        payload = {'subject': subject, 'body': body}
        requests.post(url, json=payload, timeout=2)
        print("Solicitação de e-mail enviada ao microserviço.")
    except Exception as e:
        print(f"Erro ao contatar o microserviço de e-mail: {e}")

def disparar_alerta_em_thread(subject, body):
    t = threading.Thread(target=chamar_microservico_email, args=[subject, body])
    t.start()

def disparar_alerta_estoque_baixo(produto_id, nome_produto):
    subject = f"ALERTA: Estoque Baixo (ID: {produto_id})"
    body = f"O produto '{nome_produto}' (ID: {produto_id}) está com estoque baixo."
    disparar_alerta_em_thread(subject, body)


if __name__ == '__main__':
    app.run(
        host=os.environ.get('IP', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8080)),
        debug=True
    )
