import os
import discord
from discord.ext import commands, tasks
import datetime
import json
from flask import Flask
from threading import Thread
from epicstore_api import EpicGamesStoreAPI

# --- PERSISTENȚĂ DATE (Pentru restarturi pe Render) ---
DATA_FILE = "sent_games.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {} # Structura: {"game_id": message_id}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# --- SERVER PENTRU 24/7 ---
app = Flask('')
@app.route('/')
def main(): return "Botul este online!"

def run(): app.run(host="0.0.0.0", port=8080)
def keep_alive():
    Thread(target=run).start()

# --- CONFIGURARE BOT ---
TOKEN = os.getenv("DISCORD_TOKEN")
ANNOUNCE_CH_ID = 1476567269566840842
MY_USER_ID = 810609759324471306

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Botul {bot.user} a pornit!")
    if not check_epic_games.is_running():
        check_epic_games.start()

@tasks.loop(minutes=30)
async def check_epic_games():
    channel = bot.get_channel(ANNOUNCE_CH_ID)
    if not channel: return

    api = EpicGamesStoreAPI()
    now = datetime.datetime.now(datetime.timezone.utc)
    active_ads = load_data()
    
    try:
        data = api.get_free_games()['data']['Catalog']['searchStore']['elements']
        current_free_ids = []

        for game in data:
            promotions = game.get('promotions')
            if not promotions: continue
            
            # Verificăm ofertele active
            offers = promotions.get('promotionalOffers')
            if not offers: continue

            offer_data = offers[0]['promotionalOffers'][0]
            game_id = game['id']
            
            # Convertim data expirării
            expiry_str = offer_data['endDate']
            expiry_date = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))

            # 1. DACĂ JOCUL E GRATIS ACUM (Discount 0 în API înseamnă 100% reducere)
            if offer_data['discountSetting']['discountPercentage'] == 0 and now < expiry_date:
                current_free_ids.append(game_id)
                
                # Trimitem doar dacă nu a fost deja anunțat
                if game_id not in active_ads:
                    title = game['title']
                    slug = game.get('productSlug') or game.get('urlSlug')
                    image = game['keyImages'][0]['url']

                    embed = discord.Embed(
                        title=f"🎮 JOC GRATUIT: {title}",
                        url=f"https://store.epicgames.com/p/{slug}",
                        color=discord.Color.green(),
                        timestamp=now
                    )
                    embed.set_image(url=image)
                    embed.add_field(name="⌛ Expiră pe:", value=f"`{expiry_str.replace('T', ' ').replace('Z', '')} UTC`")
                    
                    msg = await channel.send(content=f"🔔 <@{MY_USER_ID}>, joc nou gratis!", embed=embed)
                    active_ads[game_id] = msg.id
                    save_data(active_ads)

        # 2. CURĂȚENIE: Ștergem mesajele pentru jocurile care nu mai sunt gratis
        to_delete = []
        for gid, mid in active_ads.items():
            if gid not in current_free_ids:
                try:
                    msg = await channel.fetch_message(mid)
                    await msg.delete()
                    print(f"🗑️ Am șters anunțul pentru jocul cu ID: {gid}")
                except:
                    pass # Mesajul a fost deja șters manual sau nu există
                to_delete.append(gid)

        if to_delete:
            for gid in to_delete:
                del active_ads[gid]
            save_data(active_ads)

    except Exception as e:
        print(f"⚠️ Eroare la verificare: {e}")

keep_alive()
bot.run(TOKEN)
