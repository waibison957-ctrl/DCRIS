import discord
import asyncio
import os

# =====================================================================
# CONFIGURACIÓN DE SEGURIDAD
# =====================================================================
# Lista de IDs de Discord autorizadas para ejecutar comandos (Whitelist)
# Pon aquí tu ID de usuario de Discord y el de tus administradores
WHITELIST_IDS = [786993411605135411, 1164635211833823242]

# Cargar variables críticas del entorno de Railway
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
                # self_mute y self_deaf controlan si entra silenciado o no
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


# Contenedor global de las instancias de los bots
clones = []

# =====================================================================
# CONFIGURACIÓN DEL BOT CONTROLADOR PRINCIPAL
# =====================================================================
control_intents = discord.Intents.default()
control_intents.message_content = True  # Obligatorio para leer los comandos de chat
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

        # Comprobar si se solicitó explícitamente el desmuteo
        unmute_mode = False
        if len(command) >= 4 and command[3].lower() == "unmute":
            unmute_mode = True

        # Filtrar solo los bots que estén listos y que NO estén ya metidos en un canal
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
            # Si unmute_mode es True -> mute=False, deaf=False. Si es False -> mute=True, deaf=True.
            success = await bot.connect_to_voice(channel_id, mute=not unmute_mode, deaf=not unmute_mode)
            if success:
                exitos += 1
            await asyncio.sleep(0.5)  # Pequeña pausa entre conexiones internas

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
                await asyncio.sleep(2.5)  # Delay para evitar penalizaciones por spam de perfiles
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

    # 1. Iniciar el Bot Controlador
    print("[i] Iniciando Bot Controlador Principal...")
    control_task = asyncio.create_task(control_bot.start(CONTROL_BOT_TOKEN))

    # Esperar un par de segundos a que se asiente el bot maestro
    await asyncio.sleep(2.0)

    # 2. Iniciar de forma secuencial las cuentas clonadas
    if not SELF_BOT_TOKENS:
        print("[!] ADVERTENCIA: La lista SELF_BOT_TOKENS en Railway está vacía.")
    else:
        print(f"[i] Preparando el inicio secuencial controlado de {len(SELF_BOT_TOKENS)} cuentas...")
        
        for i, token in enumerate(SELF_BOT_TOKENS):
            bot_instance = MySelfbot(token=token)
            clones.append(bot_instance)
            
            print(f"[~] Sincronizando e iniciando cuenta #{i+1}/{len(SELF_BOT_TOKENS)}...")
            
            # Sub-tarea segura para que si un login falla, el bucle continúe sin crasheos
            async def safe_start(b=bot_instance, idx=i):
                try:
                    await b.start(b.my_token)
                except discord.errors.LoginFailure:
                    print(f"[!] ERROR: El token #{idx+1} ({b.my_token[:15]}...) es inválido. Saltado.")
                except discord.errors.HTTPException as http_err:
                    if http_err.status == 429:
                        print(f"[!] RATELIMIT: Cloudflare/Discord bloqueó temporalmente la cuenta #{idx+1} (429).")
                    else:
                        print(f"[!] Error HTTP en cuenta #{idx+1}: {http_err}")
                except Exception as e:
                    print(f"[!] Error inesperado en la cuenta #{idx+1}: {e}")

            asyncio.create_task(safe_start())
            
            # Pausa obligatoria de 5.5 segundos por cuenta para evitar el error 1015 de Cloudflare
            await asyncio.sleep(5.5)

    # Bloquear la ejecución principal para que mantenga el contenedor de Railway encendido
    await control_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Apagando servicio de forma ordenada...")
