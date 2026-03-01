import os
import discord
from discord.ext import commands, tasks
import datetime
# Am corectat linia de mai jos:
from datetime import timezone 
from flask import Flask
from threading import Thread
from epicstore_api import EpicGamesStoreAPI

# --- SERVER PENTRU 24/7 (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def main():
    return "Botul este online!"

def run():
    # Render folosește de obicei portul 10000, dar 8080 e ok dacă e configurat
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    server = Thread(target=run)
    server.start()

# --- CONFIGURARE ID-URI ---
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CH_ID = 1444796054313766922
ANNOUNCE_CH_ID = 1476567269566840842
MY_USER_ID = 810609759324471306

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

sent_games = []

@bot.event
async def on_ready():
    print(f"✅ {bot.user} a pornit fara erori!")
    if not check_epic_games.is_running():
        check_epic_games.start()

@tasks.loop(minutes=60)
async def check_epic_games():
    channel = bot.get_channel(ANNOUNCE_CH_ID)
    if not channel:
        return

    api = EpicGamesStoreAPI()

    try:
        data = api.get_free_games()['data']['Catalog']['searchStore']['elements']
        for game in data:
            promotions = game.get('promotions')
            if not promotions:
                continue
                
            offer_list = promotions.get('promotionalOffers')
            if not offer_list or len(offer_list) == 0:
                continue

            offer = offer_list[0]['promotionalOffers'][0]
            
            # Verificăm dacă prețul e 0
            if offer['discountSetting']['discountPercentage'] == 0:
                game_id = game['id']
                if game_id in sent_games:
                    continue

                title = game['title']
                image = game['keyImages'][0]['url']
                slug = game.get('productSlug') or game.get('urlSlug')
                expiry_date = offer['endDate']
                
                clean_date = expiry_date.replace('T', ' ').replace('Z', '')

                embed = discord.Embed(
                    title=f"🎮 Joc Gratuit: {title}",
                    url=f"https://store.epicgames.com/p/{slug}",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                
                embed.set_image(url=image)
                embed.add_field(
                    name="⌛ Expiră la data:", 
                    value=f"`{clean_date} UTC`", 
                    inline=False
                )
                embed.set_footer(text="Epic Games Tracker")

                await channel.send(content=f"🔔 <@{MY_USER_ID}>, a apărut un joc gratis nou!", embed=embed)
                sent_games.append(game_id)

    except Exception as e:
        print(f"Eroare: {e}")

@bot.event
async def on_message_delete(message):
    pass

keep_alive()
bot.run(TOKEN)
