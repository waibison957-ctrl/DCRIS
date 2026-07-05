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

@app.route('/favicon.ico')
def favicon():
    return '', 204  # Silencia el error 404 estético del icono

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# =====================================================================
# CONFIGURACIÓN DE SEGURIDAD
# =====================================================================
# Lista de IDs de Discord autorizadas para ejecutar comandos (Whitelist)
WHITELIST_IDS = [786993411605135411, 1164635211833823242]

# Cargar variables críticas del entorno de Render
CONTROL_BOT_TOKEN = os.getenv('CONTROL_BOT_TOKEN')
SELF_BOT_TOKENS_RAW = os.getenv('SELF_BOT_TOKENS', '')

# Limpiar y procesar la lista de tokens
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
# CONFIGURACIÓN DEL BOT CONTROLADOR PRINCIPAL (MÉTODO COMPATIBLE v1.7.3)
# =====================================================================
control_intents = discord.Intents.default()
control_intents.messages = True  # En v1.7.3 habilita explícitamente la lectura de eventos de chat[cite: 2]
control_bot = discord.Client(intents=control_intents)

def is_authorized(user_id):
    return user_id in WHITELIST_IDS

@control_bot.event
async def on_ready():
    print(f'[*] BOT CONTROLADOR PRINCIPAL ACTIVO: {control_bot.user}')
    print(f'[i] Panel listo en Discord. Controlando de forma segura los clones conectados.')

@control_bot.event
async def on_message(message):
    # Ignorar mensajes propios o de usuarios fuera de la Whitelist
    if message.author == control_bot.user or not is_authorized(message.author.id):
        return

    command = message.content.strip().split()
    if not command:
        return

    action = command[0].lower()

    # 1. Comando Conectar: !conectar <ID_CANAL> <CANTIDAD> [unmute]
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
        estado_msg = "🔓 desmuteadas y desensordecidas" if unmute_mode else "🔇 muteadas y sordas"
        await message.reply(f"🚀 Conectando {cantidad} cuentas al canal `{channel_id}` de forma {estado_msg}...")

        exitos = 0
        for bot in grupo:
            success = await bot.connect_to_voice(channel_id, mute=not unmute_mode, deaf=not unmute_mode)
            if success:
                exitos += 1
            await asyncio.sleep(0.5)

        await message.reply(f"✅ Proceso terminado. Conectadas con éxito `{exitos}/{cantidad}` cuentas.")

    # 2. Comando Desconectar Todo: !desconectar
    elif action == "!desconectar":
        await message.reply("🔌 Desconectando todas las cuentas de los canales de voz...")
        for bot in clones:
            if bot.is_ready():
                await bot.disconnect_voice()
        await message.reply("✅ Todas las cuentas activas han sido desconectadas.")

    # 3. Comando Cambiar Nombre: !nombre <Nuevo Nombre>
    elif action == "!nombre":
        nuevo_nombre = " ".join(command[1:])
        if not nuevo_nombre:
            await message.reply("⚠️ Uso correcto: `!nombre <Nuevo Display Name>`")
            return

        await message.reply(f"⚙️ Cambiando Display Name a todas las cuentas en línea...")
        for bot in clones:
            if bot.is_ready():
                try:
                    await bot.http.request(
                        discord.http.Route('PATCH', '/users/@me'),
                        json={'global_name': nuevo_nombre}
                    )
                except Exception as e:
                    print(f"Error cambiando nombre a {bot.user}: {e}")
                await asyncio.sleep(2.5)
        await message.reply("✅ Cambio de Display Names completado.")

    # 4. Comando Quitar Foto: !quitarfoto
    elif action == "!quitarfoto":
        await message.reply("🖼️ Eliminando las fotos de perfil de los clones activos...")
        for bot in clones:
            if bot.is_ready():
                try:
                    await bot.user.edit(avatar=None)
                except Exception as e:
                    print(f"Error quitando avatar a {bot.user}: {e}")
                await asyncio.sleep(2.5)
        await message.reply("✅ Proceso de remoción de avatares finalizado.")

    # 5. Comando Estado del Servidor: !estado
    elif action == "!estado":
        activos = [c for c in clones if c.is_ready()]
        en_voz = sum(1 for c in activos if c.current_vc and c.current_vc.is_connected())
        libres = len(activos) - en_voz
        await message.reply(
            f"📊 **Estado actual del sistema:**\n"
            f"• Cuentas con sesión activa: `{len(activos)}` / `{len(SELF_BOT_TOKENS)}` totales\n"
            f"• En canales de voz: `{en_voz}`\n"
            f"• Libres/Disponibles: `{libres}`"
        )

# =====================================================================
# BUCLE PRINCIPAL DE ARRANQUE SECUENCIAL (ANTI-RATELIMIT)
# =====================================================================
async def main():
    global clones
    
    if not CONTROL_BOT_TOKEN:
        print("[!] ERROR CRÍTICO: Falta la variable de entorno CONTROL_BOT_TOKEN.")
        return

    # 1. Arrancar el servidor web de Flask en segundo plano para Render antes de los bots
    keep_alive()

    # 2. Iniciar el Bot Controlador
    print("[i] Iniciando Bot Controlador Principal...")
    control_task = asyncio.create_task(control_bot.start(CONTROL_BOT_TOKEN))
    await asyncio.sleep(2.0)

    # 3. Iniciar de forma secuencial las cuentas clonadas
    if not SELF_BOT_TOKENS:
        print("[!] ADVERTENCIA: La lista SELF_BOT_TOKENS está vacía.")
    else:
        print(f"[i] Preparando el inicio secuencial controlado de {len(SELF_BOT_TOKENS)} cuentas...")
        
        for i, token in enumerate(SELF_BOT_TOKENS):
            bot_instance = MySelfbot(token=token)
            clones.append(bot_instance)
            
            print(f"[~] Sincronizando e iniciando cuenta #{i+1}/{len(SELF_BOT_TOKENS)}...")
            
            async def safe_start(b=bot_instance, idx=i):
                try:
                    await b.start(b.my_token)
                except Exception as e:
                    print(f"[!] Error inesperado en la cuenta #{idx+1}: {e}")

            asyncio.create_task(safe_start())
            await asyncio.sleep(5.5)  # Pausa obligatoria anti-Cloudflare de Render

    # Mantener el Web Service encendido escuchando a Discord
    await control_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Apagando servicio de forma ordenada...")
