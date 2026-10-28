import asyncio
import io
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import edge_tts

app = Flask(__name__)

# Habilita o CORS para permitir a comunicação com o frontend no Netlify
# Em produção, você pode substituir por: CORS(app, origins=["https://seu-site.netlify.app"])
CORS(app)

VOZES_DISPONIVEIS = {
    "pt-BR-FranciscaNeural": "Português (Brasil) - Francisca (Feminino)",
    "pt-BR-AntonioNeural": "Português (Brasil) - Antonio (Masculino)",
    "en-US-AriaNeural": "Inglês (EUA) - Aria (Feminino)",
}

@app.route("/api/vozes", methods=["GET"])
def listar_vozes():
    """Rota útil para o frontend verificar se o backend está online e obter as vozes."""
    return jsonify(VOZES_DISPONIVEIS)

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    
    if not data:
        return jsonify({"erro": "Payload inválido ou vazio"}), 400
        
    texto = data.get("texto", "").strip()
    voz = data.get("voz", "pt-BR-FranciscaNeural")

    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400

    if voz not in VOZES_DISPONIVEIS:
        return jsonify({"erro": "Voz inválida"}), 400

    try:
        # Cria um novo event loop para executar a função assíncrona do edge-tts
        # Isso evita conflitos com o Gunicorn e vazamento de memória
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_bytes = loop.run_until_complete(gerar_audio(texto, voz))
        loop.close()
        
        # Retorna o arquivo MP3 gerado em memória
        return send_file(
            io.BytesIO(mp3_bytes),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="audio.mp3"
        )
    except Exception as e:
        # Log do erro no console do Render para facilitar o debug
        print(f"Erro ao gerar áudio: {str(e)}")
        return jsonify({"erro": "Falha interna ao gerar o áudio. Tente novamente."}), 500

async def gerar_audio(texto: str, voz: str) -> bytes:
    """Função assíncrona que se comunica com a Microsoft e coleta os bytes do MP3."""
    communicate = edge_tts.Communicate(texto, voice=voz)
    audio_buffer = io.BytesIO()
    
    # Consome o stream de áudio e escreve no buffer
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    
    return audio_buffer.getvalue()

if __name__ == "__main__":
    # Porta 5000 para testes locais
    app.run(debug=True, port=5000)
