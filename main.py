import sys

import logging
from datetime import datetime, timedelta
from configparser import ConfigParser
import re

import asyncio
import discord
import twitter


log = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)-5.5s [%(name)s:%(lineno)s][%(threadName)s] %(message)s')

ch = logging.StreamHandler()
ch.setFormatter(formatter)
log.setLevel('DEBUG')
log.addHandler(ch)

log.info('------')
config = ConfigParser()
config.read('config.ini')


# Logging in to twitter
try:
    twitter_config = config['credentials:twitter']
    CONSUMER_KEY = twitter_config['consumer_key']
    CONSUMER_SECRET = twitter_config['consumer_secret']
    ACCESS_TOKEN_KEY = twitter_config['access_token_key']
    ACCESS_TOKEN_SECRET = twitter_config['access_token_secret']
except KeyError as e:
    log.error("Fix your twitter config section!")
    msg = "{err} on twitter config ".format(
        err=str(type(e).__name__ + ': ' + str(e)))
    log.error(msg)
    sys.exit(1)

twitter_api = twitter.Api(consumer_key=CONSUMER_KEY,
                          consumer_secret=CONSUMER_SECRET,
                          access_token_key=ACCESS_TOKEN_KEY,
                          access_token_secret=ACCESS_TOKEN_SECRET)
verified = twitter_api.VerifyCredentials()
if verified:
    log.info("Twitter verified as: " + str(verified))
else:
    log.warning("Could not verify twitter user, recheck info")
    sys.exit(1)


# Logging in to discord
try:
    discord_config = config['credentials:discord']
    EMAIL = discord_config['email']
    PASSWORD = discord_config['password']

    starboard_info = config['starboard_info']
    STARBOARD_ID = starboard_info['channel_id']
    BOT_ID = starboard_info['bot_id']
except KeyError as e:
    log.error("Fix your discord config section!")
    msg = "{err} on twitter config ".format(
        err=str(type(e).__name__ + ': ' + str(e)))
    log.error(msg)
    sys.exit(1)


client = discord.Client()
post_queue = {}


def get_message_info(message):
    image_link = ''
    real_msg = ''
    text = message.content
    star_emoji = text[0]
    star_channel = '#' + str(message.channel_mentions[0])
    stars = re.search('(?<=\*\*)(.*?)(?=\*\*)', text).group(0)  # Finds text between the **'s

    embed = message.embeds[0]
    author_id = re.search('(?<=/)(.*?)(?=/)', embed['author']['icon_url'][34:])  # Id from icon url link
    author = message.server.get_member(author_id)
    if 'description' in embed:
        real_msg = embed['description']
    if 'image' in embed:
        image_link = embed['image']['url']

    status = "{emoji} {count}: {channel}\n{author}\n\n{text}".format(emoji=star_emoji, count=stars,
                                                                     channel=star_channel, author=str(author),
                                                                     text=real_msg)
    info = {'message': status, 'image': image_link}
    return info


async def parse_queue():
    await client.wait_until_ready()
    log.info("parse_queue() running")
    while True:
        now = datetime.now()
        for k, v in post_queue.items():
            if k + timedelta(minutes=30) > now:
                continue
            else:
                log.info("Status ready")
                info = get_message_info(v)
                twitter_api.PostUpdate(info['message'], info['image_link'])
                log.info("Status posted: {0}, {1}".format(info['message'], info['image_link']))
                post_queue.pop(k)
        await asyncio.sleep(300)


@client.event
async def on_ready():
    log.info('Logged into Discord as')
    log.info(client.user.name)
    log.info(client.user.id)
    log.info('------')


@client.event
async def on_message(message):
    if message.author.id != BOT_ID or message.channel.id != STARBOARD_ID:
        return

    post_queue[message.timestamp] = message
    log.info("Starboard message detected!")


client.loop.create_task(parse_queue())
log.info("parse_queue() successfully added")
client.run(EMAIL, PASSWORD)
