import discord
import asyncio
import os

# Lista de IDs de Discord de las personas autorizadas (Whitelist)
WHITELIST_IDS = [123456789012345678, 876543210987654321] # Reemplaza con tus IDs reales

# Cargar variables críticas del entorno
CONTROL_BOT_TOKEN = os.getenv('CONTROL_BOT_TOKEN')
SELF_BOT_TOKENS_RAW = os.getenv('SELF_BOT_TOKENS', '')

# Procesar los tokens de las cuentas limpiando espacios y comas fantasmas
SELF_BOT_TOKENS = [t.strip() for t in SELF_BOT_TOKENS_RAW.split(',') if t.strip()]

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
                return False
        except Exception as e:
            print(f'[!] [{self.user.name}] Error en conexión de voz: {e}')
            return False

    async def disconnect_voice(self):
        if self.current_vc and self.current_vc.is_connected():
            await self.current_vc.disconnect()
            self.current_vc = None

# Contenedor global para los clones instanciados
clones = []

# Inicializar el Bot Controlador Oficial
control_intents = discord.Intents.default()
control_intents.message_content = True  # Requerido para leer comandos
control_bot = discord.Client(intents=control_intents)

def is_authorized(user_id):
    return user_id in WHITELIST_IDS

@control_bot.event
async def on_ready():
    print(f'[*] BOT CONTROLADOR PRINCIPAL ACTIVO: {control_bot.user}')
    print(f'[i] Panel listo. Controlando de forma segura las cuentas que pudieron iniciar sesión.')

@control_bot.event
async def on_message(message):
    if message.author == control_bot.user or not is_authorized(message.author.id):
        return

    command = message.content.strip().split()
    if not command:
        return

    action = command[0].lower()

    # Comando 1: !conectar <ID_CANAL> <CANTIDAD> [unmute]
    if action == "!conectar":
        if len(command) < 3:
            await message.reply("Uso: `!conectar <ID_canal_voz> <cantidad_cuentas> [unmute]`")
            return

        try:
            channel_id = int(command[1])
            cantidad = int(command[2])
        except ValueError:
            await message.reply("El ID del canal y la cantidad deben ser números.")
            return

        unmute_mode = False
        if len(command) >= 4 and command[3].lower() == "unmute":
            unmute_mode = True

        clones_libres = [c for c in clones if c.is_ready() and not (c.current_vc and c.current_vc.is_connected())]
        
        if not clones_libres:
            await message.reply("No hay cuentas clonadas activas o libres en este momento.")
            return

        if cantidad > len(clones_libres):
            cantidad = len(clones_libres)

        grupo = clones_libres[:cantidad]
        await message.reply(f"Conectando {cantidad} cuentas al canal {channel_id}...")

        exitos = 0
        for bot in grupo:
            success = await bot.connect_to_voice(channel_id, mute=not unmute_mode, deaf=not unmute_mode)
            if success:
                exitos += 1
            await asyncio.sleep(0.5)

        await message.reply(f"Proceso terminado. {exitos}/{cantidad} cuentas se conectaron con éxito.")

    # Comando 2: !desconectar
    elif action == "!desconectar":
        await message.reply("Desconectando todas las cuentas activas...")
        for bot in clones:
            if bot.is_ready():
                await bot.disconnect_voice()
        await message.reply("Todas las cuentas se han desconectado.")

    # Comando 3: !nombre <Nuevo Nombre>
    elif action == "!nombre":
        nuevo_nombre = " ".join(command[1:])
        if not nuevo_nombre:
            await message.reply("Uso: `!nombre <Nuevo Display Name>`")
            return

        await message.reply(f"Cambiando Display Name a las cuentas en lote...")
        for bot in clones:
            if bot.is_ready():
                try:
                    await bot.http.request(
                        discord.http.Route('PATCH', '/users/@me'),
                        json={'global_name': nuevo_nombre}
                    )
                except Exception as e:
                    print(f"Error cambiando nombre a {bot.user}: {e}")
                await asyncio.sleep(2.0)
        await message.reply("Cambio de nombre finalizado.")

    # Comando 4: !quitarfoto
    elif action == "!quitarfoto":
        await message.reply("Removiendo las fotos de perfil de las cuentas activas...")
        for bot in clones:
            if bot.is_ready():
                try:
                    await bot.user.edit(avatar=None)
                except Exception as e:
                    print(f"Error quitando avatar a {bot.user}: {e}")
                await asyncio.sleep(2.0)
        await message.reply("Proceso completado.")

    # Comando 5: !estado
    elif action == "!estado":
        activos = [c for c in clones if c.is_ready()]
        en_voz = sum(1 for c in activos if c.current_vc and c.current_vc.is_connected())
        libres = len(activos) - en_voz
        await message.reply(f"📊 **Estado del Panel:**\n• Cuentas en línea: {len(activos)}\n• En canales de voz: {en_voz}\n• Disponibles: {libres}")

async def main():
    global clones
    
    tasks = []

    # 1. Intentar arrancar el Bot Controlador de comandos
    if not CONTROL_BOT_TOKEN:
        print("[!] ERROR CRÍTICO: Falta la variable de entorno CONTROL_BOT_TOKEN.")
        return

    async def start_control():
        try:
            await control_bot.start(CONTROL_BOT_TOKEN)
        except discord.errors.LoginFailure:
            print("[!] ERROR CRÍTICO: El CONTROL_BOT_TOKEN de Railway es inválido o incorrecto.")
        except Exception as e:
            print(f"[!] Error inesperado al iniciar el Bot Controlador: {e}")

    tasks.append(asyncio.create_task(start_control()))

    # 2. Intentar arrancar las cuentas clonadas de manera independiente
    if not SELF_BOT_TOKENS:
        print("[!] ADVERTENCIA: La lista SELF_BOT_TOKENS está vacía.")
    else:
        print(f"[i] Preparando el inicio de {len(SELF_BOT_TOKENS)} cuentas...")
        
        for i, token in enumerate(SELF_BOT_TOKENS):
            bot_instance = MySelfbot(token=token)
            clones.append(bot_instance)
            
            # Función envoltorio para evitar que el fallo de un login tumbe a los demás
            async def safe_start(b=bot_instance, idx=i):
                try:
                    await b.start(b.my_token)
                except discord.errors.LoginFailure:
                    print(f"[!] ERROR: El token #{idx+1} ({b.my_token[:15]}...) es incorrecto. Saltado.")
                except Exception as e:
                    print(f"[!] Error inesperado en la cuenta #{idx+1}: {e}")

            tasks.append(asyncio.create_task(safe_start()))

    # Lanzar todas las conexiones en paralelo
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Apagando servicio...")
