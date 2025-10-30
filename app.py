from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'chave_secreta_muito_segura'  # Necessário para usar 'flash' (mensagens)

# --- SIMULAÇÃO DE BANCO DE DADOS (Substitua por um SGBD real, como SQLite/PostgreSQL, no futuro) ---
produtos = [
    {'id': 1, 'nome': 'Parafuso Sextavado M10', 'quantidade': 1500, 'localizacao': 'A1-01', 'estoque_min': 500},
    {'id': 2, 'nome': 'Óleo Lubrificante 5L', 'quantidade': 50, 'localizacao': 'B2-05', 'estoque_min': 20},
    {'id': 3, 'nome': 'Luvas de Couro', 'quantidade': 5, 'localizacao': 'C3-10', 'estoque_min': 100},
]
next_id = 4 # Próximo ID a ser usado

# --- ROTAS PRINCIPAIS ---

# 1. Dashboard / Tela Inicial
@app.route('/')
def dashboard():
    """Exibe o dashboard/resumo do almoxarifado."""
    # Lógica para calcular indicadores
    total_itens = sum(p['quantidade'] for p in produtos)
    estoque_baixo = [p for p in produtos if p['quantidade'] < p['estoque_min']]
    
    return render_template('almoxarifado_dashboard.html', 
                           produtos=produtos,
                           total_itens=total_itens,
                           estoque_baixo_count=len(estoque_baixo))

# 2. Listar Todos os Produtos
@app.route('/estoque')
def listar_produtos():
    """Exibe a lista completa de produtos."""
    return render_template('listar_produtos.html', produtos=produtos)

# 3. Adicionar Novo Produto (GET para formulário, POST para salvar)
@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar_produto():
    """Adiciona um novo produto ao estoque."""
    global next_id
    if request.method == 'POST':
        # Captura os dados do formulário
        nome = request.form['nome']
        quantidade = int(request.form['quantidade'])
        localizacao = request.form['localizacao']
        estoque_min = int(request.form['estoque_min'])
        
        # Cria o novo produto
        novo_produto = {
            'id': next_id,
            'nome': nome,
            'quantidade': quantidade,
            'localizacao': localizacao,
            'estoque_min': estoque_min
        }
        produtos.append(novo_produto)
        next_id += 1
        
        flash(f'Produto "{nome}" adicionado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
        
    # Se for GET, apenas exibe o formulário
    return render_template('adicionar_produto.html')

# 4. Editar Produto (GET para formulário, POST para salvar)
@app.route('/editar/<int:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    """Edita um produto existente."""
    produto = next((p for p in produtos if p['id'] == produto_id), None)
    
    if produto is None:
        flash('Produto não encontrado.', 'error')
        return redirect(url_for('listar_produtos'))

    if request.method == 'POST':
        # Atualiza os dados do produto
        produto['nome'] = request.form['nome']
        produto['quantidade'] = int(request.form['quantidade'])
        produto['localizacao'] = request.form['localizacao']
        produto['estoque_min'] = int(request.form['estoque_min'])
        
        flash(f'Produto "{produto["nome"]}" atualizado com sucesso!', 'info')
        return redirect(url_for('listar_produtos'))
        
    # Se for GET, exibe o formulário preenchido
    return render_template('editar_produto.html', produto=produto)

# 5. Remover Produto
@app.route('/remover/<int:produto_id>', methods=['POST'])
def remover_produto(produto_id):
    """Remove um produto do estoque."""
    global produtos
    produto_a_remover = next((p for p in produtos if p['id'] == produto_id), None)
    
    if produto_a_remover:
        produtos = [p for p in produtos if p['id'] != produto_id] # Recria a lista sem o produto
        flash(f'Produto "{produto_a_remover["nome"]}" removido com sucesso!', 'danger')
        
    return redirect(url_for('listar_produtos'))


if __name__ == '__main__':
    # Em um ambiente de produção real, você usaria um servidor WSGI
    app.run(debug=True)