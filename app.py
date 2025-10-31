from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysql_connector import MySQL  # Importe a biblioteca (CORRIGIDO)

app = Flask(__name__)
app.secret_key = 'chave_secreta_muito_segura'

# --- CONFIGURAÇÃO DO BANCO DE DADOS MYSQL ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'SUA_SENHA_AQUI'  # <-- COLOQUE A SENHA QUE VOCÊ CRIOU
app.config['MYSQL_DB'] = 'almoxarifado_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'  # Retorna resultados como dicionários

mysql = MySQL(app)  # Inicialização (CORRIGIDO)

# --- ROTAS PRINCIPAIS ---

# 1. Dashboard / Tela Inicial
@app.route('/')
def dashboard():
    """Exibe o dashboard/resumo do almoxarifado."""
    conn = mysql.connection
    cursor = conn.cursor()
    
    # Lógica para calcular indicadores com SQL
    cursor.execute("SELECT SUM(quantidade) as total FROM produtos")
    total_itens_result = cursor.fetchone()
    total_itens = total_itens_result['total'] if total_itens_result['total'] else 0
    
    cursor.execute("SELECT COUNT(id) as count FROM produtos WHERE quantidade < estoque_min")
    estoque_baixo_result = cursor.fetchone()
    estoque_baixo_count = estoque_baixo_result['count']
    
    cursor.close()
    
    return render_template('almoxarifado_dashboard.html',
                           total_itens=total_itens,
                           estoque_baixo_count=estoque_baixo_count)

# 2. Listar Todos os Produtos
@app.route('/estoque')
def listar_produtos():
    """Exibe a lista completa de produtos."""
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM produtos ORDER BY nome")
    produtos = cursor.fetchall()
    cursor.close()
    return render_template('listar_produtos.html', produtos=produtos)

# 3. Adicionar Novo Produto (GET para formulário, POST para salvar)
@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar_produto():
    """Adiciona um novo produto ao estoque."""
    if request.method == 'POST':
        # Captura os dados do formulário
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        
        # Conecta e executa a inserção no banco
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO produtos (nome, quantidade, localizacao, estoque_min) VALUES (%s, %s, %s, %s)",
            (nome, quantidade, localizacao, estoque_min)
        )
        mysql.connection.commit()  # Salva as alterações
        cursor.close()
        
        flash(f'Produto "{nome}" adicionado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
        
    return render_template('adicionar_produto.html')

# 4. Editar Produto (GET para formulário, POST para salvar)
@app.route('/editar/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    """Edita um produto existente."""
    cursor = mysql.connection.cursor()
    
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
        return redirect(url_for('listar_produtos'))
    
    # Se for GET, busca o produto para preencher o formulário
    cursor.execute("SELECT * FROM produtos WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()
    cursor.close()
    
    if produto is None:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('listar_produtos'))
        
    return render_template('editar_produto.html', produto=produto)

# 5. Remover Produto
@app.route('/remover/<int:produto_id>', methods=['POST'])
def remover_produto(produto_id):
    """Remove um produto do estoque."""
    cursor = mysql.connection.cursor()
    
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
    return redirect(url_for('listar_produtos'))

if __name__ == '__main__':
    # Em um ambiente de produção real, você usaria um servidor WSGI
    app.run(debug=True)
