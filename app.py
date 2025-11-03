from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysql_connector import MySQL  # Importe a biblioteca (CORRIGIDO)
import os # <-- ADICIONADO PARA LER VARIÁVEIS DE AMBIENTE DO CLOUD9

app = Flask(__name__)
app.secret_key = 'chave_secreta_muito_segura'

# --- CONFIGURAÇÃO DO BANCO DE DADOS MYSQL ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'admin123'  # <-- COLOQUE A SENHA QUE VOCÊ CRIOU
app.config['MYSQL_DB'] = 'almoxarifado_db'
# A linha 'MYSQL_CURSORCLASS' foi removida pois não é usada por esta biblioteca

mysql = MySQL(app)  # Inicialização (CORRIGIDO)

# --- FUNÇÃO HELPER PARA OBTER DADOS COMUNS ---
# Para evitar repetição, buscamos os dados do dashboard e a lista de produtos
def get_dados_comuns():
    conn = mysql.connection
    # CORREÇÃO: Solicita um cursor que retorna dicionários
    cursor = conn.cursor(dictionary=True) 
    
    # --- CORREÇÃO DEFINITIVA (RE-ADICIONADA) ---
    # Força a seleção do banco de dados para esta conexão
    cursor.execute("USE almoxarifado_db") 
    # --- FIM DA CORREÇÃO ---
    
    # 1. Dados do Dashboard
    cursor.execute("SELECT SUM(quantidade) as total FROM produtos")
    total_itens_result = cursor.fetchone()
    total_itens = total_itens_result['total'] if total_itens_result['total'] else 0
    
    cursor.execute("SELECT COUNT(id) as count FROM produtos WHERE quantidade < estoque_min")
    estoque_baixo_result = cursor.fetchone()
    estoque_baixo_count = estoque_baixo_result['count']
    
    # 2. Lista de Produtos
    cursor.execute("SELECT * FROM produtos ORDER BY nome")
    produtos = cursor.fetchall()
    
    cursor.close()
    
    return {
        'total_itens': total_itens,
        'estoque_baixo_count': estoque_baixo_count,
        'produtos': produtos
    }

# --- ROTAS PRINCIPAIS ---

# 1. Dashboard / Listagem / Página Principal
@app.route('/')
def dashboard():
    """Exibe o dashboard E a lista de produtos."""
    dados_comuns = get_dados_comuns()
    # CORRIGIDO: renderiza o seu arquivo original
    return render_template('almoxarifado_dashboard.html', **dados_comuns)

# 2. Rota de Estoque (apenas redireciona para o dashboard)
@app.route('/estoque')
def listar_produtos():
    """Redireciona para o dashboard, que agora contém a lista."""
    return redirect(url_for('dashboard'))

# 3. Adicionar Novo Produto (Apenas POST, o formulário está no dashboard)
@app.route('/adicionar', methods=['POST'])
def adicionar_produto():
    """Adiciona um novo produto ao estoque."""
    if request.method == 'POST':
        # Captura os dados do formulário
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        
        # Conecta e executa a inserção no banco
        # CORREÇÃO: Solicita um cursor que retorna dicionários
        cursor = mysql.connection.cursor(dictionary=True)
        cursor.execute("USE almoxarifado_db") # <-- CORREÇÃO ADICIONADA
        cursor.execute(
            "INSERT INTO produtos (nome, quantidade, localizacao, estoque_min) VALUES (%s, %s, %s, %s)",
            (nome, quantidade, localizacao, estoque_min)
        )
        mysql.connection.commit()  # Salva as alterações
        cursor.close()
        
        flash(f'Produto "{nome}" adicionado com sucesso!', 'success')
    
    # Redireciona de volta para a página principal
    return redirect(url_for('dashboard'))

# 4. Editar Produto (GET para formulário, POST para salvar)
@app.route('/editar/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    """Edita um produto existente."""
    # CORREÇÃO: Solicita um cursor que retorna dicionários
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db") # <-- CORREÇÃO ADICIONADA
    
    if request.method == 'POST':
        # Captura os dados do form
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        
        # Executa o UPDATE no banco
        cursor.execute(
            """
            UPDATE produtos 
            SET nome=%s, quantidade=%s, localizacao=%s, estoque_min=%s
            WHERE id=%s
            """,
            (nome, quantidade, localizacao, estoque_min, produto_id)
        )
        mysql.connection.commit()
        cursor.close()
        
        flash(f'Produto "{nome}" atualizado com sucesso!', 'info')
        # Redireciona para o dashboard principal após editar
        return redirect(url_for('dashboard'))
    
    # Se for GET, busca o produto para preencher o formulário DE EDIÇÃO
    cursor.execute("SELECT * FROM produtos WHERE id = %s", (produto_id,))
    produto_para_editar = cursor.fetchone()
    cursor.close()
    
    if produto_para_editar is None:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('dashboard'))
        
    # Pega os dados comuns (cards, lista de produtos) E passa o produto a ser editado
    dados_comuns = get_dados_comuns()
    
    # CORRIGIDO: renderiza o seu arquivo original
    return render_template(
        'almoxarifado_dashboard.html', 
        **dados_comuns, 
        produto_para_editar=produto_para_editar
    )

# 5. Remover Produto
@app.route('/remover/<int:produto_id>', methods=['POST'])
def remover_produto(produto_id):
    """Remove um produto do estoque."""
    # CORREÇÃO: Solicita um cursor que retorna dicionários
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("USE almoxarifado_db") # <-- CORREÇÃO ADICIONADA
    
    # Para a mensagem flash, pegamos o nome antes de deletar
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

if __name__ == '__main__':
    # Em um ambiente de produção real, você usaria um servidor WSGI
    # A linha abaixo foi modificada para funcionar com o Preview do AWS Cloud9
    app.run(
        host=os.environ.get('IP', '0.0.0.0'),
        port=int(os.environ.get('PORT', 8080)),
        debug=True
    )
