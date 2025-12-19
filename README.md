# Projeto Web Almoxarifado - Entrega Final

Este projeto é uma aplicação web de controle de almoxarifado, desenvolvida em Python com Flask, utilizando MySQL, Docker e autenticação JWT baseada em cookies.

#O sistema permite:

-Controle de produtos e estoque

-Cadastro de fornecedores

-Gestão de usuários com níveis de permissão (admin, gestor, vendedor)

-Login seguro com senha criptografada

-Alertas automáticos de estoque baixo


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

#ID do usuário

#Nome

#Cargo (admin / gestor / vendedor)


# SEGURITY GROUP

Criamos um Grupo Seguro para a instância do projeto, com as configurações:

<img width="1130" height="357" alt="image" src="https://github.com/user-attachments/assets/e1e637b4-b5d6-48a5-89bb-ea31ac69c944" />

## REGRAS DE ENTRADA:

<img width="1100" height="191" alt="image" src="https://github.com/user-attachments/assets/c26e9335-f7e7-4cdb-8106-92938c352531" />


#REGRAS DE SAIDA:

<img width="1140" height="231" alt="image" src="https://github.com/user-attachments/assets/5130c1c0-6e04-4646-a100-7bdd116bc8b2" />


# IP ELASTICO - IP FIXO

Decidimos criar um IP Elástico, para sempre ser o mesmo IP, sem precisar que o EC2, toda vez que inicializar o Docker, precise mudar de IP.

#http://13.219.65.108:8000/login

<img width="1121" height="208" alt="image" src="https://github.com/user-attachments/assets/99e6221e-d20d-4caf-9198-a38be707a765" />














