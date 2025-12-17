CREATE DATABASE IF NOT EXISTS almoxarifado_db;
USE almoxarifado_db;

-- Tabela de Usuários
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100),
    email VARCHAR(100),
    senha VARCHAR(255)
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

-- Inserir um usuário administrador padrão para você conseguir logar/testar
INSERT INTO usuarios (nome, email, senha) VALUES ('Admin', 'admin@admin.com', 'admin');