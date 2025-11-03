import smtplib
import ssl
import os
from email.message import EmailMessage
from flask import Flask, request, jsonify


EMAIL_ORIGEM = "audemarioweb@gmail.com" 

EMAIL_SENHA = os.environ.get("GMAIL_APP_SENHA")


EMAIL_DESTINO = "audemarioestudante@gmail.com"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465 # Para SSL


app = Flask(__name__)

@app.route('/send_email', methods=['POST'])
def send_email():
    """
    Endpoint de API para receber o pedido e enviar o e-mail.
    """
    dados = request.get_json()
    if not dados:
        return jsonify({"erro": "Payload JSON inválido"}), 400

    subject = dados.get('subject')
    body = dados.get('body')

    if not subject or not body:
        return jsonify({"erro": "Faltando 'subject' ou 'body'"}), 400

    print(f"Recebido pedido para enviar e-mail: Assunto: {subject}")

    try:
        # Prepara a mensagem de e-mail
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_ORIGEM
        msg['To'] = EMAIL_DESTINO
        msg.set_content(body)


        context = ssl.create_default_context()

        # Conecta e envia
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as smtp:
            smtp.login(EMAIL_ORIGEM, EMAIL_SENHA)
            smtp.send_message(msg)

        print("E-mail enviado com sucesso!")
        return jsonify({"sucesso": True, "mensagem": "E-mail enviado"}), 200

    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        # Retorna um erro, mas o app principal (app.py) não será afetado
        return jsonify({"sucesso": False, "erro": str(e)}), 500

if __name__ == '__main__':
    print("Iniciando Microserviço de E-mail na porta 5001...")
    app.run(host='0.0.0.0', port=5001, debug=True)
