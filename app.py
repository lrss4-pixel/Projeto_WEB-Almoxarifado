from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysql_connector import MySQL  
import os  
import requests  
import threading  

from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = 'chave_secreta_muito_segura'


app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'admin123'  
app.config['MYSQL_DB'] = 'almoxarifado_db'


mysql = MySQL(app)  


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'danger'

class User(UserMixin):
    """Classe de usuário simples para o Flask-Login"""
    def __init__(self, id, email, nome):
        self.id = id
        self.email = email
        self.nome = nome

@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário da sessão"""
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    if user_data:
        return User(id=user_data['id'], email=user_data['email'], nome=user_data['nome'])
    return None



def get_dados_comuns():
    conn = mysql.connection

    cursor = conn.cursor(dictionary=True)

    cursor.execute("USE almoxarifado_db")


    # 1. Dados do Dashboard
    cursor.execute("SELECT SUM(quantidade) as total FROM produtos")
    total_itens_result = cursor.fetchone()
    total_itens = total_itens_result['total'] if total_itens_result['total'] else 0

    cursor.execute("SELECT COUNT(id) as count FROM produtos WHERE quantidade < estoque_min")
    estoque_baixo_result = cursor.fetchone()
    estoque_baixo_count = estoque_baixo_result['count']

    # 2. Lista de Produtos (MODIFICADO para incluir nome do fornecedor)
    cursor.execute("""
        SELECT p.*, f.nome as fornecedor_nome 
        FROM produtos p
        LEFT JOIN fornecedores f ON p.fornecedor_id = f.id
        ORDER BY p.nome
    """)
    produtos = cursor.fetchall()

    # 3. Lista de Fornecedores (NOVO - para o dropdown)
    cursor.execute("SELECT id, nome FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()

    cursor.close()

    return {
        'total_itens': total_itens,
        'estoque_baixo_count': estoque_baixo_count,
        'produtos': produtos,
        'fornecedores': fornecedores 
    }



def chamar_microservico_email(subject, body):
    """Dispara uma chamada para o microserviço de e-mail em uma thread separada."""
    try:
        # O microserviço rodará na porta 5001
        url = 'http://127.0.0.1:5001/send_email'
        payload = {'subject': subject, 'body': body}

        requests.post(url, json=payload, timeout=2)
        print("Solicitação de e-mail enviada ao microserviço.")
    except Exception as e:
        print(f"Erro ao contatar o microserviço de e-mail: {e}")

def disparar_alerta_em_thread(subject, body):
    """Inicia a thread para não bloquear a aplicação principal."""
    t = threading.Thread(target=chamar_microservico_email, args=[subject, body])
    t.start()

def disparar_alerta_estoque_baixo(produto_id, nome_produto):
    """Formata a mensagem e chama a thread para disparar o alerta."""
    subject = f"ALERTA: Estoque Baixo (ID: {produto_id})"
    body = f"O produto '{nome_produto}' (ID: {produto_id}) está com estoque baixo."
    disparar_alerta_em_thread(subject, body)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Lida com o login do usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db")
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()

        # Verifica se o usuário existe e a senha está correta
        if user_data and check_password_hash(user_data['senha'], senha):
            user = User(id=user_data['id'], email=user_data['email'], nome=user_data['nome'])
            login_user(user) # Loga o usuário
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha inválidos.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Lida com o registro de um novo usuário"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        nome = request.form.get('nome')
        senha = request.form.get('senha')

        if not email or not nome or not senha:
            flash('Todos os campos são obrigatórios.', 'danger')
            return render_template('login.html')

        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db")
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user_exite = cursor.fetchone()

        if user_exite:
            flash('Este e-mail já está cadastrado. Tente fazer login.', 'danger')
            cursor.close()
            return render_template('login.html')

        # Cria a senha com hash
        hash_senha = generate_password_hash(senha, method='pbkdf2:sha256')
        
        cursor.execute(
            "INSERT INTO usuarios (email, nome, senha) VALUES (%s, %s, %s)",
            (email, nome, hash_senha)
        )
        mysql.connection.commit()
        cursor.close()

        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))

    return render_template('login.html') 

@app.route('/logout')
@login_required
def logout():
    """Desloga o usuário"""
    logout_user()
    flash('Você foi desconectado.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required 
def dashboard():
    """Exibe o dashboard E a lista de produtos."""
    dados_comuns = get_dados_comuns()

    return render_template('almoxarifado_dashboard.html', **dados_comuns)


@app.route('/estoque')
@login_required # <-- Protegido
def listar_produtos():
    """Redireciona para o dashboard, que agora contém a lista."""
    return redirect(url_for('dashboard'))


@app.route('/adicionar', methods=['POST'])
@login_required 
def adicionar_produto():
    """Adiciona um novo produto ao estoque."""
    if request.method == 'POST':
        # Captura os dados do formulário
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        fornecedor_id = request.form.get('fornecedor_id') 
        

        if fornecedor_id == '0':
            fornecedor_id = None

        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db")  #
        cursor.execute(
            "INSERT INTO produtos (nome, quantidade, localizacao, estoque_min, fornecedor_id) VALUES (%s, %s, %s, %s, %s)",
            (nome, quantidade, localizacao, estoque_min, fornecedor_id)
        )
        
        # Pega o ID do produto que acabou de ser criado
        novo_produto_id = cursor.lastrowid 
        
        mysql.connection.commit()  # Salva as alterações
        cursor.close()

        flash(f'Produto "{nome}" adicionado com sucesso!', 'success')

        if quantidade < estoque_min:
            disparar_alerta_estoque_baixo(novo_produto_id, nome)

    # Redireciona de volta para a página principal
    return redirect(url_for('dashboard'))

@app.route('/editar/<int:produto_id>', methods=['GET', 'POST'])
@login_required # <-- Protegido
def editar_produto(produto_id):
    """Edita um produto existente."""

    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")  

    if request.method == 'POST':
        # Captura os dados do form
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        fornecedor_id = request.form.get('fornecedor_id') 


        if fornecedor_id == '0':
            fornecedor_id = None

        # Executa o UPDATE no banco
        cursor.execute(
            """
            UPDATE produtos 
            SET nome=%s, quantidade=%s, localizacao=%s, estoque_min=%s, fornecedor_id=%s
            WHERE id=%s
            """,
            (nome, quantidade, localizacao, estoque_min, fornecedor_id, produto_id)
        )
        mysql.connection.commit()
        cursor.close()


        if quantidade < estoque_min:
            disparar_alerta_estoque_baixo(produto_id, nome)

        flash(f'Produto "{nome}" atualizado com sucesso!', 'info')

        return redirect(url_for('dashboard'))


    cursor.execute("SELECT * FROM produtos WHERE id = %s", (produto_id,))
    produto_para_editar = cursor.fetchone()
    cursor.close()

    if produto_para_editar is None:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('dashboard'))


    dados_comuns = get_dados_comuns()


    return render_template(
        'almoxarifado_dashboard.html',
        **dados_comuns,
        produto_para_editar=produto_para_editar
    )

# 5. Remover Produto
@app.route('/remover/<int:produto_id>', methods=['POST'])
@login_required # <-- Protegido
def remover_produto(produto_id):
    """Remove um produto do estoque."""

    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")  


    cursor.execute("SELECT nome FROM produtos WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()

    if produto:
        cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
        mysql.connection.commit()
        flash(f'Produto "{produto["nome"]}" removido com sucesso!', 'danger')
    else:
        flash('Produto não encontrado.', 'error')

    cursor.close()
    return redirect(url_for('dashboard'))

@app.route('/fornecedores')
@login_required
def fornecedores_crud():
    """Página principal para CRUD de Fornecedores"""
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()
    cursor.close()
    
    return render_template('fornecedores.html', fornecedores=fornecedores)

@app.route('/fornecedores/adicionar', methods=['POST'])
@login_required
def adicionar_fornecedor():
    """Adiciona um novo fornecedor"""
    if request.method == 'POST':
        nome = request.form['nome']
        contato_nome = request.form.get('contato_nome')
        telefone = request.form.get('telefone')
        email = request.form.get('email')
        
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db")
        cursor.execute(
            "INSERT INTO fornecedores (nome, contato_nome, telefone, email) VALUES (%s, %s, %s, %s)",
            (nome, contato_nome, telefone, email)
        )
        mysql.connection.commit()
        cursor.close()
        flash(f'Fornecedor "{nome}" adicionado com sucesso!', 'success')
    
    return redirect(url_for('fornecedores_crud'))

@app.route('/fornecedores/editar/<int:fornecedor_id>', methods=['GET', 'POST'])
@login_required
def editar_fornecedor(fornecedor_id):
    """Mostra o form de edição (GET) ou atualiza (POST) um fornecedor"""
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    if request.method == 'POST':
        nome = request.form['nome']
        contato_nome = request.form.get('contato_nome')
        telefone = request.form.get('telefone')
        email = request.form.get('email')
        
        cursor.execute(
            """
            UPDATE fornecedores
            SET nome=%s, contato_nome=%s, telefone=%s, email=%s
            WHERE id=%s
            """,
            (nome, contato_nome, telefone, email, fornecedor_id)
        )
        mysql.connection.commit()
        cursor.close()
        flash(f'Fornecedor "{nome}" atualizado com sucesso!', 'info')
        return redirect(url_for('fornecedores_crud'))
        

    cursor.execute("SELECT * FROM fornecedores WHERE id = %s", (fornecedor_id,))
    fornecedor_para_editar = cursor.fetchone()
    

    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()
    cursor.close()

    if fornecedor_para_editar is None:
        flash('Fornecedor não encontrado.', 'error')
        return redirect(url_for('fornecedores_crud'))
        
    return render_template(
        'fornecedores.html', 
        fornecedores=fornecedores, 
        fornecedor_para_editar=fornecedor_para_editar
    )

@app.route('/fornecedores/remover/<int:fornecedor_id>', methods=['POST'])
@login_required
def remover_fornecedor(fornecedor_id):
    """Remove um fornecedor"""
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db")
    
    # Pega o nome para o flash
    cursor.execute("SELECT nome FROM fornecedores WHERE id = %s", (fornecedor_id,))
    fornecedor = cursor.fetchone()

    if fornecedor:
        try:
            # Tenta deletar
            cursor.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
            mysql.connection.commit()
            flash(f'Fornecedor "{fornecedor["nome"]}" removido com sucesso!', 'danger')
        except Exception as e:
            # Captura erro de chave estrangeira (se o fornecedor estiver em uso)
            mysql.connection.rollback()
            flash(f'Erro ao remover "{fornecedor["nome"]}". Pode estar associado a produtos.', 'danger')
    else:
        flash('Fornecedor não encontrado.', 'error')

    cursor.close()
    return redirect(url_for('fornecedores_crud'))


if __name__ == '__main__':
    app.run(
        host=os.environ.get('IP', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8080)),
        debug=True
    )
