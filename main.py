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
    USE_TOKEN = discord_config.get('token')
    EMAIL = ''
    PASSWORD = ''
    if not USE_TOKEN:
        EMAIL = discord_config['email']
        PASSWORD = discord_config['password']

    starboard_info = config['starboard_info']
    STARBOARD_ID = starboard_info['channel_id']
    BOT_ID = starboard_info['bot_id']
    WAIT_TIME = starboard_info.get('wait_time', fallback=5)
except KeyError as e:
    log.error("Fix your discord config section!")
    msg = "{err} on twitter config ".format(
        err=str(type(e).__name__ + ': ' + str(e)))
    log.error(msg)
    sys.exit(1)


client = discord.Client()
post_queue = {}


def clean_message(message, content):
    transformations = {}

    mentions = re.findall(r'<@!?([0-9]+)>', content)
    mentions = [message.server.get_member(i) for i in mentions]
    mention_transforms = {
        re.escape('<@{0.id}>'.format(member)): '@' + member.display_name
        for member in mentions
    }

    for k, v in mention_transforms.items():
        if k in content:
            content = content.replace(k, v)
    
    transformations.update(mention_transforms)

    transformations = {
        '@everyone': '@\u200beveryone',
        '@here': '@\u200bhere'
    }

    return content


def get_message_info(message, author):
    image_link = ''
    real_msg = ''
    text = message.content
    star_emoji = text[0]
    star_channel = '#' + str(message.channel_mentions[0])
    stars = re.search('(?<=\*\*)(.*?)(?=\*\*)', text).group(0)  # Finds text between the **'s

    embed = message.embeds[0]
    if 'description' in embed:
        real_msg = clean_message(message, embed['description'])
    if 'image' in embed:
        image_link = embed['image']['url']

    status = "{emoji} {count}: {channel}\n{author}\n\n{text}".format(emoji=star_emoji, count=stars,
                                                                     channel=star_channel, author=author,
                                                                     text=real_msg)
    info = {'message': status, 'image': image_link}
    return info


async def parse_queue():
    await client.wait_until_ready()
    log.info("parse_queue() running")
    while True:
        remove = []
        now = datetime.utcnow()
        for k, v in post_queue.copy().items():
            if k + timedelta(minutes=WAIT_TIME) > now:
                pass
            else:
                log.info("Status ready")
                info = get_message_info(v[0], v[1])
                status = "Status posted: {0}, {1}".format(info['message'], info['image'])
                try:
                    twitter_api.PostUpdate(info['message'], info['image'])
                except twitter.error.TwitterError:
                    twitter_api.PostUpdate(info['message'][:139], info['image'])
                    status = "Truncated " + msg
                log.info(status)
                remove.append(k)
        await asyncio.sleep(30)
        for i in remove:
            post_queue.pop(i)
            remove.pop(0)


@client.event
async def on_ready():
    log.info('Logged into Discord as')
    log.info(client.user.name)
    log.info(client.user.id)
    log.info('------')
    log.info("Started!")


@client.event
async def on_message(message):
    if message.author.id != BOT_ID or message.channel.id != STARBOARD_ID:
        return

    log.info("Starboard message detected!")
    author_id = re.search('(?<=/)(.*?)(?=/)', message.embeds[0]['author']['icon_url'][32:]).group(0) # Id from icon url link
    author = message.server.get_member(author_id)
    post_queue[message.timestamp] = [message, str(author)]

client.loop.create_task(parse_queue())
log.info("parse_queue() successfully added")

if not USE_TOKEN:
    client.run(EMAIL, PASSWORD)
else:
    client.run(USE_TOKEN)
