from flask import Flask, request
import os
import tempfile
import yt_dlp
import instaloader
from instaloader.context import InstaloaderContext
from facebook_scraper import get_posts
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8220244020:AAEL80e7YRUB9RSGRBcECUUOfejikJAlsQE"
bot = Bot(TOKEN)
app = Flask(__name__)

# -------------------- Funções de download --------------------

import tempfile
import yt_dlp

def download_youtube_video(url):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    
    # Opções do yt_dlp
    ydl_opts = {
        'outtmpl': tmp.name,
        'format': 'best',
        'nocheckcertificate': True,
        'cookies': 'cookies.txt',  # cookies exportados do navegador
        'noplaylist': True,
        'quiet': False,
        'merge_output_format': 'mp4',
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
                          'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/116.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return tmp.name
    except Exception as e:
        print(f"Erro YouTube: {e}")
        return None


def download_instagram_post(url, cookie_file=None):
    try:
        # Criar loader
        loader = instaloader.Instaloader(
            dirname_pattern=tempfile.gettempdir(),
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )

        # Definir headers como navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
                          'AppleWebKit/537.36 (KHTML, like Gecko) ' +
                          'Chrome/116.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        loader.context = InstaloaderContext()
        loader.context._session.headers.update(headers)

        # Carregar cookies se fornecido
        if cookie_file:
            loader.load_session_from_file(username=None, filename=cookie_file)

        # Pegar shortcode do post
        shortcode = url.split("/")[-2]
        post = instaloader.Post.from_shortcode(loader.context, shortcode)

        if post.is_video:
            tmp_file = os.path.join(tempfile.gettempdir(), f"{post.shortcode}.mp4")
            loader.download_post(post, target=tmp_file.replace(".mp4", ""))
            return tmp_file
        else:
            print("O post não contém vídeo.")
            return None

    except Exception as e:
        print(f"Erro Instagram: {e}")
        return None

def download_facebook_video(url):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    ydl_opts = {'outtmpl': tmp.name, 'format': 'best'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return tmp.name
    except Exception as e:
        print(f"Erro Facebook: {e}")
        return None

def get_facebook_post_details(url):
    try:
        posts = list(get_posts(post_urls=[url], cookies="cookies.txt"))
        return posts[0] if posts else {}
    except Exception as e:
        print(f"Erro scraping Facebook: {e}")
        return {}

def download_twitter_video(url):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    ydl_opts = {'outtmpl': tmp.name, 'format': 'best'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return tmp.name
    except Exception as e:
        print(f"Erro Twitter: {e}")
        return None

# -------------------- Webhook Telegram --------------------

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if "message" not in data:
        return "ok"

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    if not text.startswith("/get"):
        bot.send_message(chat_id, "Use assim: `/get <url>`", parse_mode="Markdown")
        return "ok"

    parts = text.split(" ", 1)
    if len(parts) < 2:
        bot.send_message(chat_id, "Envie a URL. Ex: `/get https://youtube.com/...`", parse_mode="Markdown")
        return "ok"

    url = parts[1]
    msg = bot.send_message(chat_id, "⏳ Gerando vídeo...")

    tmp_file = None
    try:
        if "youtube.com" in url or "youtu.be" in url:
            tmp_file = download_youtube_video(url)
        elif "instagram.com" in url:
            tmp_file = download_instagram_post(url)
        elif "facebook.com" in url:
            tmp_file = download_facebook_video(url)
        elif "twitter.com" in url or "x.com" in url:
            tmp_file = download_twitter_video(url)
        else:
            bot.edit_message_text("❌ Plataforma não suportada", chat_id, msg.message_id)
            return "ok"

        if not tmp_file or not os.path.exists(tmp_file):
            bot.edit_message_text("❌ Falha ao baixar vídeo", chat_id, msg.message_id)
            return "ok"

        # Botão de excluir
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Excluir", callback_data=f"delete_{user_id}")]])
        bot.edit_message_text("✅ Vídeo pronto!", chat_id, msg.message_id)
        bot.send_video(chat_id, video=open(tmp_file, "rb"), reply_markup=keyboard)

        os.remove(tmp_file)
    except Exception as e:
        bot.edit_message_text(f"❌ Erro: {e}", chat_id, msg.message_id)

    return "ok"

@app.route(f"/callback/{TOKEN}", methods=["POST"])
def callback():
    data = request.json
    if "callback_query" not in data:
        return "ok"

    query = data["callback_query"]
    chat_id = query["message"]["chat"]["id"]
    user_id = query["from"]["id"]
    data_str = query["data"]

    if not data_str.startswith("delete_"):
        return "ok"

    owner_id = data_str.split("_", 1)[1]
    if str(user_id) != owner_id:
        bot.answer_callback_query(query["id"], "⚠️ Só quem pediu pode excluir.")
        return "ok"

    bot.delete_message(chat_id, query["message"]["message_id"])
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
