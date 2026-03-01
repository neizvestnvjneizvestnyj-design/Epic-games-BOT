import os
import discord
from discord.ext import commands, tasks
import datetime
from datetime import timezone
from flask import Flask
from threading import Thread
from epicstore_api import EpicGamesStoreAPI

# --- SERVER PENTRU 24/7 ---
app = Flask('')
@app.route('/')
def main(): return "Botul este online!"

def run(): app.run(host="0.0.0.0", port=8080)
def keep_alive():
    server = Thread(target=run)
    server.start()

# --- CONFIGURARE ---
TOKEN = os.getenv("DISCORD_TOKEN")
ANNOUNCE_CH_ID = 1476567269566840842
MY_USER_ID = 810609759324471306

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Dicționar pentru a ține evidența: {game_id: message_id}
active_ads = {}

@bot.event
async def on_ready():
    print(f"✅ {bot.user} monitorizează jocurile!")
    if not check_epic_games.is_running():
        check_epic_games.start()

@tasks.loop(minutes=30) # Verificăm mai des (la 30 min) pentru precizie
async def check_epic_games():
    channel = bot.get_channel(ANNOUNCE_CH_ID)
    if not channel: return

    api = EpicGamesStoreAPI()
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        data = api.get_free_games()['data']['Catalog']['searchStore']['elements']
        current_game_ids = []

        for game in data:
            promotions = game.get('promotions')
            if not promotions: continue
            
            offer_list = promotions.get('promotionalOffers')
            if not offer_list or len(offer_list) == 0: continue

            offer = offer_list[0]['promotionalOffers'][0]
            
            # Data expirării convertită în obiect datetime pentru comparare
            expiry_str = offer['endDate']
            expiry_date = datetime.datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            
            game_id = game['id']

            # LOGICA DE ȘTERGERE: Dacă jocul a expirat și avem un mesaj pentru el
            if now >= expiry_date:
                if game_id in active_ads:
                    try:
                        msg = await channel.fetch_message(active_ads[game_id])
                        await msg.delete()
                        del active_ads[game_id]
                        print(f"🗑️ Am șters jocul expirat: {game['title']}")
                    except:
                        pass
                continue

            # LOGICA DE TRIMITERE: Dacă este gratis (100% discount)
            if offer['discountSetting']['discountPercentage'] == 0:
                current_game_ids.append(game_id)
                
                if game_id not in active_ads:
                    title = game['title']
                    image = game['keyImages'][0]['url']
                    slug = game.get('productSlug') or game.get('urlSlug')

                    embed = discord.Embed(
                        title=f"🎮 Joc Gratuit: {title}",
                        url=f"https://store.epicgames.com/p/{slug}",
                        color=discord.Color.green(),
                        timestamp=now
                    )
                    embed.set_image(url=image)
                    embed.add_field(name="⌛ Expiră la:", value=f"`{expiry_str.replace('T', ' ').replace('Z', '')} UTC`")
                    
                    msg = await channel.send(content=f"🔔 <@{MY_USER_ID}>, joc nou!", embed=embed)
                    active_ads[game_id] = msg.id # Salvăm ID-ul mesajului
        
        # Curățare secundară: dacă un joc dispare subit din API
        ids_to_remove = []
        for gid in active_ads:
            if gid not in current_game_ids:
                try:
                    msg = await channel.fetch_message(active_ads[gid])
                    await msg.delete()
                    ids_to_remove.append(gid)
                except:
                    ids_to_remove.append(gid)
        
        for gid in ids_to_remove:
            del active_ads[gid]

    except Exception as e:
        print(f"Eroare: {e}")

keep_alive()
bot.run(TOKEN)
