#!/usr/bin/env python3
"""
Discord Crafty Bot (UUID-safe) for discord.py v2.6.3
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List

import yaml
import aiohttp
import discord
from discord.ext import tasks, commands

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("crafty-bot")

# ---------- Config loader ----------
CONFIG_PATH = os.environ.get("CRAFTY_CONFIG", "config.yaml")

def load_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("update_interval", 60)
    cfg.setdefault("category_name", "Crafty Servers")
    cfg.setdefault("allowed_user_ids", [])
    cfg.setdefault("allowed_role_names", [])
    cfg.setdefault("servers", {})
    return cfg

# ---------- Crafty API Client ----------
class CraftyClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.base = cfg["crafty"]["base_url"].rstrip("/")
        self.username = cfg["crafty"].get("username")
        self.password = cfg["crafty"].get("password")
        self.bearer_token = cfg["crafty"].get("bearer_token")
        self.verify_ssl = cfg["crafty"].get("verify_ssl", True)
        self.timeout = aiohttp.ClientTimeout(total=15)
        self._token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def login(self) -> str:
        if self.bearer_token:
            self._token = self.bearer_token
            log.info("Using static bearer token")
            return self._token

        url = f"{self.base}/api/v2/auth/login"
        sess = await self.session()
        async with sess.post(url, json={"username": self.username, "password": self.password},
                             ssl=(None if self.verify_ssl else False)) as r:
            if r.status >= 400:
                text = await r.text()
                raise RuntimeError(f"Login failed {r.status}: {text}")
            js = await r.json()
            token = js.get("data", {}).get("token") or js.get("token") or js.get("data")
            if not token:
                raise RuntimeError(f"No token found in login response: {js}")
            self._token = token
            log.info("Logged in to Crafty API with username/password")
            return token

    async def _request(self, method: str, path: str, retry: bool = True, **kwargs):
        url = f"{self.base}{path}"
        sess = await self.session()
        headers = kwargs.pop("headers", {})
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with sess.request(
                method, url,
                headers=headers,
                ssl=(None if self.verify_ssl else False),
                timeout=self.timeout,
                **kwargs
            ) as r:
                if r.status == 401 and retry and not self.bearer_token:
                    # token expired → re-login once
                    await self.login()
                    return await self._request(method, path, retry=False, **kwargs)

                if r.status >= 400:
                    text = await r.text()
                    raise RuntimeError(f"HTTP {r.status}: {text}")

                return await r.json()

        except aiohttp.ClientConnectionError as e:
            log.warning(f"Crafty not reachable ({e}), will retry later")
            raise

        except asyncio.TimeoutError:
            log.warning("Crafty request timed out, will retry later")
            raise

    async def get_servers(self):
        data = await self._request("GET", "/api/v2/servers")
        return data.get("data", [])

    async def find_server_id(self, name_or_id: str) -> Optional[str]:
        if name_or_id:
            return str(name_or_id)
        return None

    async def action_server(self, server_id: str, action: str):
        return await self._request("POST", f"/api/v2/servers/{server_id}/action/{action}")

    async def get_public(self, server_id: str):
        data = await self._request("GET", f"/api/v2/servers/{server_id}/public")
        return data.get("data", {})

    async def get_stats(self, server_id: str):
        data = await self._request("GET", f"/api/v2/servers/{server_id}/stats")
        return data.get("data", {})

# ---------- Discord Bot ----------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)  # command_prefix required but using slash commands

_cfg = load_config()
crafty_client = CraftyClient(_cfg)
update_interval = int(_cfg.get("update_interval", 60))
CATEGORY_NAME = _cfg.get("category_name", "Crafty Servers")

SERVERS_CFG: Dict[str, str] = dict(_cfg.get("servers", {}))
server_map: Dict[str, str] = {}
channel_map: Dict[int, Dict[str, int]] = {}
channel_last_update: Dict[int, float] = {}
CHANNEL_COOLDOWN = 15  # seconds

# ---------- Helpers ----------
def is_authorized(ctx: discord.Interaction) -> bool:
    if str(ctx.user.id) in [str(x) for x in _cfg.get("allowed_user_ids", [])]:
        return True
    for role in ctx.user.roles:
        if role.name in _cfg.get("allowed_role_names", []):
            return True
    return False

async def refresh_server_map():
    global server_map
    servers = await crafty_client.get_servers()
    id_by_name = {s["server_name"]: str(s["server_id"]) for s in servers}
    new_map: Dict[str, str] = {}
    for friendly, craft_name in SERVERS_CFG.items():
        sid = id_by_name.get(craft_name) or str(craft_name)
        new_map[friendly] = sid
    server_map = new_map
    log.info("Server map: %s", server_map)

async def ensure_channels_for_guild(guild: discord.Guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(CATEGORY_NAME)
    per_guild_map = channel_map.setdefault(guild.id, {})
    for friendly in SERVERS_CFG.keys():
        found = None
        for ch in category.voice_channels:
            if friendly.lower() in ch.name.lower():
                found = ch
                break
        if not found:
            created = await guild.create_voice_channel(f"🔄 {friendly.capitalize()}...", category=category)
            per_guild_map[friendly] = created.id
        else:
            per_guild_map[friendly] = found.id

# ---------- Events ----------
@bot.event
async def on_ready():
    # Try logging into Crafty safely
    try:
        await crafty_client.login()
    except Exception as e:
        log.warning(f"Crafty not available yet: {e}")

    # Try refreshing the server map safely
    try:
        await refresh_server_map()
    except Exception as e:
        log.warning(f"Could not refresh server map yet: {e}")

    # Ensure channels exist for each guild, safely
    for g in bot.guilds:
        try:
            await ensure_channels_for_guild(g)
        except Exception as e:
            log.warning(f"Could not ensure channels for guild {g.name}: {e}")

    # 🔑 Sync slash commands
    try:
        # Option A: Global sync (commands everywhere, may take up to 1h)
        synced = await bot.tree.sync()
        log.info(f"Globally synced {len(synced)} slash commands.")

        # Option B: Per-guild sync (instant, for testing)
        # test_guild_id = 123456789012345678  # replace with your test server ID
        # synced = await bot.tree.sync(guild=discord.Object(id=test_guild_id))
        # log.info(f"Synced {len(synced)} commands to guild {test_guild_id}.")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

    # Start the background update loop
    update_task.start()
    log.info("Bot ready as %s", bot.user)


@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        await ensure_channels_for_guild(guild)
    except Exception as e:
        log.warning(f"Could not ensure channels for new guild {guild.name}: {e}")


# ---------- Autocomplete ----------
# Not working yet
async def server_autocomplete(interaction: discord.Interaction, current: str) -> List[discord.app_commands.Choice[str]]:
    return [discord.app_commands.Choice(name=n, value=n) for n in server_map.keys() if current.lower() in n.lower()][:25]

# ---------- Slash Commands ----------
@bot.tree.command(name="start", description="Start a Crafty server")
@discord.app_commands.autocomplete(server=server_autocomplete)
async def start(interaction: discord.Interaction, server: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("⛔ Unauthorized", ephemeral=True)
        return
    sid = server_map.get(server)
    if not sid:
        await interaction.response.send_message(f"❌ Unknown server {server}", ephemeral=True)
        return
    await crafty_client.action_server(sid, "start_server")
    await interaction.response.send_message(f"✅ Starting {server}")

@bot.tree.command(name="stop", description="Stop a Crafty server")
@discord.app_commands.autocomplete(server=server_autocomplete)
async def stop(interaction: discord.Interaction, server: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("⛔ Unauthorized", ephemeral=True)
        return
    sid = server_map.get(server)
    if not sid:
        await interaction.response.send_message(f"❌ Unknown server {server}", ephemeral=True)
        return
    await crafty_client.action_server(sid, "stop_server")
    await interaction.response.send_message(f"🛑 Stopping {server}")

@bot.tree.command(name="restart", description="Restart a Crafty server")
@discord.app_commands.autocomplete(server=server_autocomplete)
async def restart(interaction: discord.Interaction, server: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("⛔ Unauthorized", ephemeral=True)
        return
    sid = server_map.get(server)
    if not sid:
        await interaction.response.send_message(f"❌ Unknown server {server}", ephemeral=True)
        return
    await crafty_client.action_server(sid, "restart_server")
    await interaction.response.send_message(f"🔁 Restarting {server}")

@bot.tree.command(name="status", description="Check status of a Crafty server")
@discord.app_commands.autocomplete(server=server_autocomplete)
async def status(interaction: discord.Interaction, server: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("⛔ Unauthorized", ephemeral=True)
        return
    sid = server_map.get(server)
    if not sid:
        await interaction.response.send_message(f"❌ Unknown server {server}", ephemeral=True)
        return
    data = await crafty_client.get_public(sid)
    await interaction.response.send_message(
        f"📊 {server} — running: {data.get('running')}, "
        f"players: {data.get('online')}/{data.get('max')}"
    )

@bot.tree.command(name="reload-config", description="Reload config.yaml")
async def reload_config(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("⛔ Unauthorized", ephemeral=True)
        return
    global _cfg, SERVERS_CFG, CATEGORY_NAME, update_interval
    _cfg = load_config(CONFIG_PATH)
    SERVERS_CFG = dict(_cfg.get("servers", {}))
    CATEGORY_NAME = _cfg.get("category_name", CATEGORY_NAME)
    update_interval = int(_cfg.get("update_interval", update_interval))
    await refresh_server_map()
    for g in bot.guilds:
        await ensure_channels_for_guild(g)
    await interaction.response.send_message("✅ Config reloaded.", ephemeral=True)

# ---------- Background Task ----------
@tasks.loop(seconds=update_interval)
async def update_task():
    await refresh_server_map()
    for guild_id, per_guild_map in channel_map.items():
        guild = bot.get_guild(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found")
            continue

        for friendly, ch_id in per_guild_map.items():
            sid = server_map.get(friendly)
            if not sid:
                continue

            try:
                data = await crafty_client.get_stats(sid)
                running = bool(data.get("running"))

                # Only show Online/Offline now
                new_name = (
                    f"🟢 {friendly.capitalize()}: Online"
                    if running else f"🔴 {friendly.capitalize()}: Offline"
                )

                ch = guild.get_channel(ch_id)
                if ch and ch.name != new_name:
                    now = time.time()
                    last = channel_last_update.get(ch.id, 0)
                    if now - last < CHANNEL_COOLDOWN:
                        log.info(f"Skipping update for {ch.name}, cooldown not reached")
                        continue
                    await ch.edit(name=new_name)
                    channel_last_update[ch.id] = now

            except Exception as e:
                log.warning(f"Failed to update server {friendly}: {e}")
                
# ---------- Main ----------
if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN") or _cfg.get("discord_token")
    if not token:
        log.error("No Discord token found")
        raise SystemExit(1)
    bot.run(token)
