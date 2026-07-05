import discord
import asyncio
import os
from flask import Flask
from threading import Thread

# =====================================================================
# SERVIDOR WEB DE MENTIRA (FLASK) PARA EVITAR QUE RENDER APAGUE LA APP
# =====================================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot activo y corriendo 24/7"

def run_flask():
    # Render asigna automáticamente un puerto en la variable de entorno PORT
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# =====================================================================
# CONFIGURACIÓN DE SEGURIDAD
# =====================================================================
WHITELIST_IDS = [786993411605135411, 1164635211833823242]

CONTROL_BOT_TOKEN = os.getenv('CONTROL_BOT_TOKEN')
SELF_BOT_TOKENS_RAW = os.getenv('SELF_BOT_TOKENS', '')
SELF_BOT_TOKENS = [t.strip() for t in SELF_BOT_TOKENS_RAW.split(',') if t.strip()]

# =====================================================================
# CLASE PARA LAS CUENTAS CLONADAS (SELFBOTS)
# =====================================================================
class MySelfbot(discord.Client):
    def __init__(self, token, *args, **kwargs):
        self_intents = discord.Intents.default()
        super().__init__(*args, **kwargs, intents=self_intents, self_bot=True)
        self.my_token = token
        self.current_vc = None

    async def on_ready(self):
        print(f'[+] Cuenta clon conectada con éxito: {self.user}')

    async def connect_to_voice(self, channel_id, mute=True, deaf=True):
        try:
            if self.current_vc and self.current_vc.is_connected():
                await self.current_vc.disconnect()

            channel = self.get_channel(channel_id)
            if channel and isinstance(channel, discord.VoiceChannel):
                self.current_vc = await channel.connect(self_mute=mute, self_deaf=deaf)
                print(f'[+] [{self.user.name}] Conectado a: {channel.name} (Mute: {mute}, Deaf: {deaf})')
                return True
            else:
                print(f'[!] [{self.user.name}] Canal {channel_id} no encontrado o no es de voz.')
                return False
        except Exception as e:
            print(f'[!] [{self.user.name}] Error en conexión de voz: {e}')
            return False

    async def disconnect_voice(self):
        if self.current_vc and self.current_vc.is_connected():
            await self.current_vc.disconnect()
            self.current_vc = None

clones = []

# =====================================================================
# CONFIGURACIÓN DEL BOT CONTROLADOR PRINCIPAL
# =====================================================================
control_intents = discord.Intents.default()
control_intents.message_content = True  
control_bot = discord.Client(intents=control_intents)

def is_authorized(user_id):
    return user_id in WHITELIST_IDS

@control_bot.event
async def on_ready():
    print(f'[*] BOT CONTROLADOR PRINCIPAL ACTIVO: {control_bot.user}')

@control_bot.event
async def on_message(message):
    if message.author == control_bot.user or not is_authorized(message.author.id):
        return

    command = message.content.strip().split()
    if not command:
        return

    action = command[0].lower()

    if action == "!conectar":
        if len(command) < 3:
            await message.reply("⚠️ Uso correcto: `!conectar <ID_canal_voz> <cantidad_cuentas> [unmute]`")
            return
        try:
            channel_id = int(command[1])
            cantidad = int(command[2])
        except ValueError:
            await message.reply("❌ El ID del canal y la cantidad deben ser números enteros.")
            return

        unmute_mode = False
        if len(command) >= 4 and command[3].lower() == "unmute":
            unmute_mode = True

        clones_libres = [c for c in clones if c.is_ready() and not (c.current_vc and c.current_vc.is_connected())]
        if not clones_libres:
            await message.reply("⚠️ No hay cuentas clonadas activas o libres en este momento.")
            return

        if cantidad > len(clones_libres):
            cantidad = len(clones_libres)

        grupo = clones_libres[:cantidad]
        estado_msg = "🔓 desmuteadas" if unmute_mode else "🔇 muteadas"
        await message.reply(f"🚀 Conectando {cantidad} cuentas...")

        exitos = 0
        for bot in grupo:
            success = await bot.connect_to_voice(channel_id, mute=not unmute_mode, deaf=not unmute_mode)
            if success:
                exitos += 1
            await asyncio.sleep(0.5)

        await message.reply(f"✅ Conectadas con éxito `{exitos}/{cantidad}` cuentas.")

    elif action == "!desconectar":
        for bot in clones:
            if bot.is_ready():
                await bot.disconnect_voice()
        await message.reply("✅ Todas las cuentas desconectadas.")

    elif action == "!estado":
        activos = [c for c in clones if c.is_ready()]
        en_voz = sum(1 for c in activos if c.current_vc and c.current_vc.is_connected())
        await message.reply(f"📊 Cuentas en línea: `{len(activos)}` | En voz: `{en_voz}`")

# =====================================================================
# ARRANQUE
# =====================================================================
async def main():
    global clones
    if not CONTROL_BOT_TOKEN:
        print("[!] Falta CONTROL_BOT_TOKEN.")
        return

    # 1. Arrancar el servidor web en segundo plano para Render
    keep_alive()

    print("[i] Iniciando Bot Controlador Principal...")
    control_task = asyncio.create_task(control_bot.start(CONTROL_BOT_TOKEN))
    await asyncio.sleep(2.0)

    if SELF_BOT_TOKENS:
        for i, token in enumerate(SELF_BOT_TOKENS):
            bot_instance = MySelfbot(token=token)
            clones.append(bot_instance)
            
            async def safe_start(b=bot_instance):
                try: await b.start(b.my_token)
                except Exception as e: print(f"[!] Error en cuenta: {e}")

            asyncio.create_task(safe_start())
            await asyncio.sleep(5.5)

    await control_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Apagando...")
