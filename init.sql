CREATE DATABASE IF NOT EXISTS almoxarifado_db;
USE almoxarifado_db;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha VARCHAR(255) NOT NULL, -- Agora suporta o Hash longo
    cargo VARCHAR(50) DEFAULT 'vendedor' -- Novo campo de permissão
);

-- Tabela de Fornecedores
CREATE TABLE IF NOT EXISTS fornecedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100),
    contato_nome VARCHAR(100),
    telefone VARCHAR(50),
    email VARCHAR(100)
);

-- Tabela de Produtos
CREATE TABLE IF NOT EXISTS produtos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100),
    quantidade INT DEFAULT 0,
    localizacao VARCHAR(100),
    estoque_min INT DEFAULT 0,
    fornecedor_id INT,
    gestor_id INT,
    FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE SET NULL,
    FOREIGN KEY (gestor_id) REFERENCES usuarios(id) ON DELETE SET NULL
);


-- Inserir um usuário administrador com senha HASH (senha: admin)
INSERT INTO usuarios (nome, email, senha, cargo) 
VALUES ('Admin', 'admin@admin.com', 'scrypt:32768:8:1$J7tSdd2I1tGZzuhn$8ee373f4ac13fa6a5a3cc9a2f5b8685fe46aa120c95cc435e497835f752620662891f42b70f8751fa1e31456481079a861c82e9a0a72f437a429a341a55b3b40', 'admin');