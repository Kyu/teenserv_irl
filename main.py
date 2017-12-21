import sys

import logging
from datetime import datetime, timedelta
from configparser import ConfigParser

import asyncio
import discord
import twitter


log = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)-5.5s [%(name)s:%(lineno)s][%(threadName)s] %(message)s')
logging.basicConfig(level=logging.INFO)

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
    SERVER_ID = starboard_info['server_id']
    WAIT_TIME = starboard_info.get('wait_time', fallback=5)
except KeyError as e:
    log.error("Fix your discord config section!")
    msg = "{err} on twitter config ".format(
        err=str(type(e).__name__ + ': ' + str(e)))
    log.error(msg)
    sys.exit(1)


client = discord.Client()
post_queue = {}


def get_message_info(message, author):
    image_link = ''
    text = message.clean_content
    star_channel = '#' + str(message.channel.name)
    stars = [i.count for i in message.reactions if i.id == '393129724211232768'][0]  # test

    if message.embeds:
        data = message.embeds[0]
        if data.type == 'image':
            image_link = data.url

    if message.attachments:
        file = message.attachments[0]
        if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
            image_link = file.url
        else:
            text += file.url

    def determine_stars(num):
        if 11 > num >= 0:
            return '\N{WHITE MEDIUM STAR}'
        elif 15 > num >= 11:
            return '\N{GLOWING STAR}'
        elif 25 > num >= 15:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    star_emoji = determine_stars(stars)

    status = "{emoji} {count}: {channel}\n{author}\n\n{text}".format(emoji=star_emoji, count=stars,
                                                                     channel=star_channel, author=author,
                                                                     text=text)
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
async def on_reaction_add(reaction, user):
    if reaction.message.channel.id != SERVER_ID:
        return

    if not (reaction.emoji.id == '393129724211232768' and reaction.count >= 10):
        return

    log.info("Starboard message detected!")
    author = str(reaction.message.author)
    post_queue[reaction.message.timestamp] = [reaction.message, author]


client.loop.create_task(parse_queue())
log.info("parse_queue() successfully added")

if not USE_TOKEN:
    client.run(EMAIL, PASSWORD)
else:
    client.run(USE_TOKEN)
