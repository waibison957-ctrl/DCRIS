import discord
import asyncio
import os

# Lista de IDs de Discord de las personas autorizadas (Whitelist)
WHITELIST_IDS = [123456789012345678, 876543210987654321] # Reemplaza con tus IDs reales

# Cargar variables críticas del entorno
CONTROL_BOT_TOKEN = os.getenv('CONTROL_BOT_TOKEN')
SELF_BOT_TOKENS_RAW = os.getenv('SELF_BOT_TOKENS', '')

# Procesar los tokens de las cuentas
SELF_BOT_TOKENS = [t.strip() for t in SELF_BOT_TOKENS_RAW.split(',') if t.strip()]

if not CONTROL_BOT_TOKEN:
    print("[!] ERROR: Falta la variable CONTROL_BOT_TOKEN.")
    exit(1)

if not SELF_BOT_TOKENS:
    print("[!] ERROR: No se encontraron tokens en SELF_BOT_TOKENS.")
    exit(1)


class MySelfbot(discord.Client):
    def __init__(self, token, *args, **kwargs):
        # CORREGIDO: Definimos intents por defecto para evitar el TypeError
        self_intents = discord.Intents.default()
        super().__init__(*args, **kwargs, intents=self_intents, self_bot=True)
        self.my_token = token
        self.current_vc = None

    async def on_ready(self):
        print(f'[+] Cuenta clon conectada: {self.user}')

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
control_intents.message_content = True  # Requerido para leer los comandos de texto
control_bot = discord.Client(intents=control_intents)


def is_authorized(user_id):
    return user_id in WHITELIST_IDS


@control_bot.event
async def on_ready():
    print(f'[*] BOT CONTROLADOR ACTIVO: {control_bot.user}')
    print(f'[i] Administrando {len(clones)} cuentas clonadas.')


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

        clones_libres = [c for c in clones if not (c.current_vc and c.current_vc.is_connected())]
        
        if not clones_libres:
            await message.reply("No hay cuentas libres disponibles en este momento.")
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
        await message.reply("Desconectando todas las cuentas de los canales de voz...")
        for bot in clones:
            await bot.disconnect_voice()
        await message.reply("Todas las cuentas han sido desconectadas de los canales de voz.")

    # Comando 3: !nombre <Nuevo Nombre Decorativo>
    elif action == "!nombre":
        nuevo_nombre = " ".join(command[1:])
        if not nuevo_nombre:
            await message.reply("Uso: `!nombre <Nuevo Display Name>`")
            return

        await message.reply(f"Cambiando Display Name de las cuentas a '{nuevo_nombre}' de forma secuencial...")
        for bot in clones:
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
        await message.reply("Removiendo las fotos de perfil de todas las cuentas...")
        for bot in clones:
            try:
                await bot.user.edit(avatar=None)
            except Exception as e:
                print(f"Error quitando avatar a {bot.user}: {e}")
            await asyncio.sleep(2.0)
        await message.reply("Proceso de remoción de avatares completado.")

    # Comando 5: !estado
    elif action == "!estado":
        en_voz = sum(1 for c in clones if c.current_vc and c.current_vc.is_connected())
        libres = len(clones) - en_voz
        await message.reply(f"📊 **Estado del Panel:**\n• Cuentas totales: {len(clones)}\n• En canales de voz: {en_voz}\n• Libres/Disponibles: {libres}")


async def main():
    global clones
    print("[i] Inicializando instancias de cuentas clonadas...")
    
    clones = [MySelfbot(token=t) for t in SELF_BOT_TOKENS]
    
    tasks = [asyncio.create_task(bot.start(bot.my_token)) for bot in clones]
    tasks.append(asyncio.create_task(control_bot.start(CONTROL_BOT_TOKEN)))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Apagando el servicio...")
