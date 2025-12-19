# Projeto Web Almoxarifado - Entrega Final

Este projeto é uma aplicação web de controle de almoxarifado, desenvolvida em Python com Flask, utilizando MySQL, Docker e autenticação JWT baseada em cookies.

### O sistema permite:

##### -Controle de produtos e estoque

##### -Cadastro de fornecedores

##### -Gestão de usuários com níveis de permissão (admin, gestor, vendedor)

##### -Login seguro com senha criptografada

##### -Alertas automáticos de estoque baixo


# Arquitetura/Tecnologias deste Projeto

Flask → Backend e rotas

MySQL → Banco de dados

JWT (flask-jwt-extended) → Autenticação e autorização

Docker / Docker Compose → Infraestrutura

Microserviço de Email → Alertas de estoque


# Autenticação e Segurança - Usando o JWT

As senhas são armazenadas usando hash seguro (werkzeug.security)

O login gera um JWT armazenado em cookie HTTPOnly

O token contém claims com:

##### ID do usuário

##### Nome

##### Cargo (admin / gestor / vendedor)

### Cargos e Permissões

Criamos uma imagem ilustrativa de como é as permissões no sistema

<img width="1024" height="329" alt="image" src="https://github.com/user-attachments/assets/0e449b20-ee06-44d9-bb3d-f981d628b095" />

# JWT – Configuração

### Esta é a configuração em código do JWT:

app.config['JWT_TOKEN_LOCATION'] = ['cookies']

app.config['JWT_COOKIE_CSRF_PROTECT'] = False

app.config['JWT_ACCESS_COOKIE_PATH'] = '/'

#### O token fica salvo em cookie

#### Rotas protegidas usam @jwt_required()

### Handlers personalizados redirecionam para /login caso:

##### Token ausente

##### Token expirado

##### Token inválido

# Criação Automática do Usuário Admin

## Na inicialização do sistema:

### inicializar_admin()

## Se não existir um admin, o sistema cria:

### Email: admin@sistema.com
### Senha: admin123
### Cargo: admin

# Configuração do Banco de Dados

As configurações são feitas via variáveis de ambiente:

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'db')

app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')

app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_ROOT_PASSWORD', 'admin123')

app.config['MYSQL_DATABASE'] = os.environ.get('MYSQL_DATABASE', 'almoxarifado_db')

#### Isso permite rodar localmente ou em Docker/EC2 sem alterar o código

# Construimos - Decoradores de Permissão

### O decorador: 

#### @role_required(['admin', 'gestor'])

Faz o seguinte: 

##### 1- Lê o cargo do JWT
##### 2- Compara com os cargos permitios e por fim
##### 3- Bloqueia acesso indevido (erro 403)

# Dashboard Principal

### Rota protegida:

#### @app.route('/')
#### @jwt_required()

### Funcionalidades:

#### Dashboard de estoque

#### Produtos

#### Fornecedores

#### Usuários (somente admin)

### A interface esconde botões conforme o cargo do usuário.

# Alerta de Estoque Baixo

### Quando a quantidade fica abaixo do mínimo:

#### disparar_alerta_estoque_baixo()

### O que isso significa:

#### Executa em thread separada

#### Chama microserviço de email






# SEGURITY GROUP

Criamos um Grupo Seguro para a instância do projeto, com as configurações:

<img width="1130" height="357" alt="image" src="https://github.com/user-attachments/assets/e1e637b4-b5d6-48a5-89bb-ea31ac69c944" />

## REGRAS DE ENTRADA:

<img width="1100" height="191" alt="image" src="https://github.com/user-attachments/assets/c26e9335-f7e7-4cdb-8106-92938c352531" />


## REGRAS DE SAIDA:

<img width="1140" height="231" alt="image" src="https://github.com/user-attachments/assets/5130c1c0-6e04-4646-a100-7bdd116bc8b2" />


# IP ELASTICO - IP FIXO

Decidimos criar um IP Elástico, para sempre ser o mesmo IP, sem precisar que o EC2, toda vez que inicializar o Docker, precise mudar de IP.

http://13.219.65.108:8000/login

<img width="1121" height="208" alt="image" src="https://github.com/user-attachments/assets/99e6221e-d20d-4caf-9198-a38be707a765" />

# Conclusão

Então este projeto de almoxarifado, demonstra:

Arquitetura segura

Controle de acesso por cargo

Boas práticas com Flask

Uso real de JWT + Cookies

Integração com microserviços
























