import asyncio
import io
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS  # <-- NOVO: Importação do CORS
import edge_tts

app = Flask(__name__)

# Habilita o CORS para permitir que o Netlify acesse o Render
# Em produção, você pode restringir para CORS(app, origins=["https://seu-site.netlify.app"])
CORS(app) 

VOZES_DISPONIVEIS = {
    "pt-BR-FranciscaNeural": "Português (Brasil) - Francisca (Feminino)",
    "pt-BR-AntonioNeural": "Português (Brasil) - Antonio (Masculino)",
    "en-US-AriaNeural": "Inglês (EUA) - Aria (Feminino)",
}

# Rota para o frontend saber quais vozes existem (opcional, mas útil)
@app.route("/api/vozes", methods=["GET"])
def listar_vozes():
    return jsonify(VOZES_DISPONIVEIS)

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    texto = data.get("texto", "").strip()
    voz = data.get("voz", "pt-BR-FranciscaNeural")

    if not texto:
        return jsonify({"erro": "Texto vazio"}), 400

    if voz not in VOZES_DISPONIVEIS:
        return jsonify({"erro": "Voz inválida"}), 400

    try:
        mp3_bytes = asyncio.run(gerar_audio(texto, voz))
        
        return send_file(
            io.BytesIO(mp3_bytes),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="audio.mp3"
        )
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

async def gerar_audio(texto: str, voz: str) -> bytes:
    communicate = edge_tts.Communicate(texto, voice=voz)
    audio_buffer = io.BytesIO()
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    
    return audio_buffer.getvalue()

if __name__ == "__main__":
    app.run(debug=True, port=5000)