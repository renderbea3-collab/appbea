import asyncio
import io
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
from pypdf import PdfReader  # <-- NOVA BIBLIOTECA

app = Flask(__name__)
CORS(app)

VOZES_DISPONIVEIS = {
    "pt-BR-FranciscaNeural": "Português (Brasil) - Francisca (Feminino)",
    "pt-BR-AntonioNeural": "Português (Brasil) - Antonio (Masculino)",
    "en-US-AriaNeural": "Inglês (EUA) - Aria (Feminino)",
}

@app.route("/api/vozes", methods=["GET"])
def listar_vozes():
    return jsonify(VOZES_DISPONIVEIS)

@app.route("/api/tts", methods=["POST"])
def tts():
    # Rota antiga para texto puro
    data = request.get_json()
    if not data: return jsonify({"erro": "Payload inválido"}), 400
    texto = data.get("texto", "").strip()
    voz = data.get("voz", "pt-BR-FranciscaNeural")
    if not texto: return jsonify({"erro": "Texto vazio"}), 400
    
    return processar_audio(texto, voz)

@app.route("/api/tts-pdf", methods=["POST"])
def tts_pdf():
    # NOVA ROTA: Recebe o arquivo PDF
    if 'arquivo' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
    arquivo = request.files['arquivo']
    voz = request.form.get("voz", "pt-BR-FranciscaNeural")

    if arquivo.filename == '':
        return jsonify({"erro": "Nome de arquivo vazio"}), 400

    try:
        # Lê o PDF e extrai o texto
        reader = PdfReader(arquivo)
        texto_extraido = ""
        for pagina in reader.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_extraido += texto_pagina + "\n"
                
        texto_extraido = texto_extraido.strip()
        
        if not texto_extraido:
            return jsonify({"erro": "Não foi possível extrair texto deste PDF (pode ser uma imagem escaneada)."}), 400

        return processar_audio(texto_extraido, voz)
        
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return jsonify({"erro": "Falha ao processar o PDF. Verifique se o arquivo é válido."}), 500

def processar_audio(texto, voz):
    """Função auxiliar para não repetir o código de geração de áudio"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_bytes = loop.run_until_complete(gerar_audio(texto, voz))
        loop.close()
        
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
    communicate = edge_tts.Communicate(texto, voice=voz)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    return audio_buffer.getvalue()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
