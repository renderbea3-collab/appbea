import asyncio
import io
import gc  # <-- Importação do Garbage Collector para gerenciar memória
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
from pypdf import PdfReader

app = Flask(__name__)

# Habilita o CORS para permitir a comunicação com o frontend no Netlify
CORS(app)

VOZES_DISPONIVEIS = {
    "pt-BR-FranciscaNeural": "Português (Brasil) - Francisca (Feminino)",
    "pt-BR-AntonioNeural": "Português (Brasil) - Antonio (Masculino)",
    "en-US-AriaNeural": "Inglês (EUA) - Aria (Feminino)",
}

@app.route("/api/vozes", methods=["GET"])
def listar_vozes():
    """Rota útil para o frontend verificar se o backend está online."""
    return jsonify(VOZES_DISPONIVEIS)

@app.route("/api/tts", methods=["POST"])
def tts():
    """Rota para receber texto puro e converter em áudio."""
    data = request.get_json()
    
    if not data:
        return jsonify({"erro": "Payload inválido ou vazio"}), 400
        
    texto = data.get("texto", "").strip()
    voz = data.get("voz", "pt-BR-FranciscaNeural")

    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400

    if voz not in VOZES_DISPONIVEIS:
        return jsonify({"erro": "Voz inválida"}), 400

    return processar_audio(texto, voz)

@app.route("/api/tts-pdf", methods=["POST"])
def tts_pdf():
    """Rota para receber um arquivo PDF, extrair o texto e converter em áudio."""
    if 'arquivo' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
    arquivo = request.files['arquivo']
    voz = request.form.get("voz", "pt-BR-FranciscaNeural")

    if arquivo.filename == '':
        return jsonify({"erro": "Nome de arquivo vazio"}), 400

    try:
        # Extrai o texto do PDF
        reader = PdfReader(arquivo)
        texto_extraido = ""
        for pagina in reader.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_extraido += texto_pagina + "\n"
                
        texto_extraido = texto_extraido.strip()
        
        # --- OTIMIZAÇÃO DE MEMÓRIA ---
        # Libera o objeto do PDF da memória antes de gerar o áudio
        del reader
        del arquivo
        gc.collect()  # Força a limpeza do lixo na memória RAM
        
        if not texto_extraido:
            return jsonify({"erro": "Não foi possível extrair texto deste PDF (pode ser uma imagem escaneada)."}), 400

        return processar_audio(texto_extraido, voz)
        
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return jsonify({"erro": "Falha ao processar o PDF. Verifique se o arquivo é válido."}), 500

def processar_audio(texto, voz):
    """Função auxiliar que executa a síntese assíncrona e retorna o arquivo MP3."""
    try:
        # Cria um novo event loop para executar o edge-tts sem conflitar com o Gunicorn
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_bytes = loop.run_until_complete(gerar_audio(texto, voz))
        loop.close()
        
        # Retorna o MP3 empacotado na memória
        return send_file(
            io.BytesIO(mp3_bytes),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="audio.mp3"
        )
    except Exception as e:
        print(f"Erro ao gerar áudio: {e}")
        return jsonify({"erro": "Falha interna ao gerar o áudio. Tente novamente."}), 500

async def gerar_audio(texto: str, voz: str) -> bytes:
    """Conecta à API da Microsoft via edge-tts e coleta o áudio em bytes."""
    communicate = edge_tts.Communicate(texto, voice=voz)
    audio_buffer = io.BytesIO()
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    
    return audio_buffer.getvalue()

if __name__ == "__main__":
    # Porta 5000 para testes locais
    app.run(debug=True, port=5000)
