import asyncio
import io
import gc
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts
from pypdf import PdfReader

app = Flask(__name__)
CORS(app)

# Lista atualizada de vozes
VOZES_DISPONIVEIS = {
    "pt-BR-FranciscaNeural": "Português (BR) - Francisca (Feminino)",
    "pt-BR-AntonioNeural": "Português (BR) - Antonio (Masculino)",
    "pt-PT-RaquelNeural": "Português (PT) - Raquel (Feminino)",
    "en-US-AriaNeural": "Inglês (EUA) - Aria (Feminino)",
    "en-US-EmmaMultilingualNeural": "Multilíngue - Emma (Feminino)",
    "en-US-AvaMultilingualNeural": "Multilíngue - Ava (Feminino)",
}

@app.route("/api/vozes", methods=["GET"])
def listar_vozes():
    return jsonify(VOZES_DISPONIVEIS)

def formatar_rate(rate):
    """Garante que o rate esteja no formato correto exigido pelo edge-tts (ex: +0%, -10%)."""
    if not rate:
        return "+0%"
    
    rate = str(rate).strip()
    
    # Se não tiver o sinal de + ou -, adiciona o + (resolve o problema do "0%")
    if not (rate.startswith('+') or rate.startswith('-')):
        rate = '+' + rate
        
    # Se não tiver o %, adiciona o %
    if not rate.endswith('%'):
        rate = rate + '%'
        
    return rate

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    if not data: 
        return jsonify({"erro": "Payload inválido ou vazio"}), 400
        
    texto = data.get("texto", "").strip()
    voz = data.get("voz", "pt-BR-FranciscaNeural")
    # Pega o rate e já formata corretamente
    rate = formatar_rate(data.get("rate", "+0%")) 

    if not texto: 
        return jsonify({"erro": "Texto vazio"}), 400
    if voz not in VOZES_DISPONIVEIS: 
        return jsonify({"erro": "Voz inválida"}), 400

    return processar_audio(texto, voz, rate)

@app.route("/api/tts-pdf", methods=["POST"])
def tts_pdf():
    if 'arquivo' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
        
    arquivo = request.files['arquivo']
    voz = request.form.get("voz", "pt-BR-FranciscaNeural")
    # Pega o rate e já formata corretamente
    rate = formatar_rate(request.form.get("rate", "+0%"))

    if arquivo.filename == '': 
        return jsonify({"erro": "Nome de arquivo vazio"}), 400
    if voz not in VOZES_DISPONIVEIS:
        return jsonify({"erro": "Voz inválida"}), 400

    try:
        reader = PdfReader(arquivo)
        texto_extraido = ""
        for pagina in reader.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_extraido += texto_pagina + "\n"
                
        texto_extraido = texto_extraido.strip()
        
        # Otimização de memória
        del reader
        del arquivo
        gc.collect() 
        
        if not texto_extraido:
            return jsonify({"erro": "Não foi possível extrair texto deste PDF (pode ser uma imagem escaneada)."}), 400

        return processar_audio(texto_extraido, voz, rate)
        
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
        return jsonify({"erro": "Falha ao processar o PDF. Verifique se o arquivo é válido."}), 500

def processar_audio(texto, voz, rate):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_bytes = loop.run_until_complete(gerar_audio(texto, voz, rate))
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

async def gerar_audio(texto: str, voz: str, rate: str) -> bytes:
    communicate = edge_tts.Communicate(texto, voice=voz, rate=rate)
    audio_buffer = io.BytesIO()
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    
    return audio_buffer.getvalue()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
