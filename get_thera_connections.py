import os
import glob
import json
import yaml
import logging
import requests

from string import Template
from discord.ext import commands
from discord import Webhook, RequestsWebhookAdapter


EVE_SCOUT_URL = "http://www.eve-scout.com/api/wormholes?systemSearch=Jita"

REQUEST_TIMEOUT = 2

TELEGRAM_URL = ""
TELEGRAM_TOKEN = ""
DISCORD_MAIN_WEBHOOK_URL = "https://discord.com/api/webhooks/970973891960905730/FmDClwW45Pkk6LGvsodR9-hn9jU4RxjAkvKIkcLbSKtIHDdU_FdUAOsvD__wwh_5ItWV"
DISCORD_HEARTBEAT_WEBHOOK_URL = "https://discord.com/api/webhooks/970976880612212787/HfNpkrTmZqaeJStC2qvNqMxDyVUo16UxjjIiBRHlRMDw5zlchzKMRs1quNkQCYmPsE9o"
DISCORD_DEBUG_WEBHOOK_URL = "https://discord.com/api/webhooks/971011717276499988/aqI-KFY-nww9huVEgVqIaQ5ufOO2lQAGxBixkMyvP2s38utr-2JstSntun3Es0U6qm-H"
MIN_THERA_CONNECTION_THRESHOLD = 5

logger = logging.getLogger(__name__)

#placeholder to load configs for searched systems. Every config is a dict


class InsufficientData(Exception):
    """Raised when Thera connections count less than MIN_THERA_CONNECTION_THRESHOLD or connection problems"""
    def __init__(self, message="Thera connections count less than expected", json_data: list()=[]):
      TheraConnection.send_discord_webhook_alert(DISCORD_DEBUG_WEBHOOK_URL, message)
      self.message = message
      super().__init__(self.message)

class ConfigError(Exception):
    def __init__(self, message="Unable to parse yaml config"):
      TheraConnection.send_discord_webhook_alert(DISCORD_DEBUG_WEBHOOK_URL, message)
      self.message = message
      super().__init__(self.message)


class TheraConnection():

  def __init__(self, url):
    for retry_n in range(5):
        try:
          response = requests.get(url, timeout=REQUEST_TIMEOUT)
          response.raise_for_status()
          break
        except RequestException:
            sleep(retry_n)
    if response.status_code != requests.codes.ok:
        raise InsufficientData(f"Unable to connect to {EVE_SCOUT_URL}")
        exit

    self.content = response.content.decode("utf-8")
    try:
        self.json_data = json.loads(self.content)
        self.count = len(self.json_data)
        if self.count < MIN_THERA_CONNECTION_THRESHOLD:
            raise InsufficientData(f"Thera known connections count = {self.connection_count}")
    except ValueError as e:
        raise("Unable to parse json")
    except InsufficientData as e:
        TheraConnection.send_discord_webhook_alert(DISCORD_HEARTBEAT_WEBHOOK_URL, f"Current connections count: {self.count}")

  @staticmethod
  def get_searching_regions(configs: list) -> list():
    regions = set([])
    for config in configs:
      if "region" in config:
          regions.add(config["region"])
    return regions
  @staticmethod
  def get_searching_systems(configs: list) -> list():
    systems = set()
    for config in configs:
      if "system" in config:
          systems.add(config["system"])
    return systems

  def find_system_connections(self, config) -> list():
    matched_connections = []
    searched_systems = TheraConnection.get_searching_systems(TheraConnection.load_configs())
    for connection in self.json_data:
        if connection["sourceSolarSystem"]["name"] in searched_systems  or connection["destinationSolarSystem"]["name"] in searched_systems:
            matched_connections.append(connection)
    return matched_connections

  def find_region_connections(self, config) -> list():
    matched_connections = []
    searched_regions = TheraConnection.get_searching_regions(TheraConnection.load_configs())
    for connection in self.json_data:
        if connection["sourceSolarSystem"]["region"]["name"] in searched_regions  or connection["destinationSolarSystem"]["region"]["name"] in searched_regions:
            matched_connections.append(connection)
    return matched_connections

  def send_telegram_alert(self) -> bool:
    bot_token = ""
    bot_chatID = ""
    send_text = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&parse_mode=Markdown&text={bot_message}"

    response = requests.get(send_text)

    return response.json()

  @staticmethod
  def send_discord_webhook_alert(webhook_url: str, message: str) -> bool:
      webhook = Webhook.from_url(webhook_url, adapter=RequestsWebhookAdapter())
      webhook.send(message)

  @staticmethod
  def format_message(template: str, values: dict()) -> str:
      return Template(template).safe_substitute(values)

  @staticmethod
  def validate_config(config: dict()) -> dict():
      return config

  @staticmethod
  def load_configs() -> list():
      working_directory = os.path.dirname(os.path.abspath(__file__))
      config_files =  glob.glob(os.path.join(working_directory,"conf","*.yaml"))
      configs = []
      for config_file in config_files:
          try:
              with open(config_file) as f:
                  config = TheraConnection.validate_config(yaml.load(f, Loader=yaml.SafeLoader))
                  if config:
                      configs.append(config)
          except yaml.YAMLError:
              raise ConfigError(f"Unable to parse {config_file}")
              continue
      return configs
#test = telegram_bot_sendtext("Testing Telegram bot")
#print(test)
connections = TheraConnection(EVE_SCOUT_URL)
configs = TheraConnection.load_configs()

active_system_connections = connections.find_system_connections(configs) or []
active_region_connections = connections.find_region_connections(configs)
active_connections = active_region_connections + active_system_connections
for connection in active_connections:
    template = "Source system signature $signatureId:\n $sourceSolarSystem\nDestination system signature $wormholeDestinationSignatureId:\n$destinationSolarSystem"
    message = TheraConnection.format_message(template, connection)
    TheraConnection.send_discord_webhook_alert(DISCORD_MAIN_WEBHOOK_URL, message)

msg = f"""Current known connections count with Thera: {connections.count}.\nLooking for regions: {str(TheraConnection.get_searching_regions(TheraConnection.load_configs()))}\
           Looking for systems: {TheraConnection.get_searching_systems(TheraConnection.load_configs())}"""
TheraConnection.send_discord_webhook_alert(DISCORD_HEARTBEAT_WEBHOOK_URL, msg)
exit
