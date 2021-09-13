# インストールした discord.py を読み込む
import discord
import boto3
import re
from botocore.exceptions import ClientError

# AWSライブラリ
polly = boto3.client('polly')
secretsmanager = boto3.client('secretsmanager')

# 変数
TOKEN = ""
PREFIX = ";"
COMMAND_START = "shl"
COMMAND_END = "bye"
COMMAND_HELP = "help"
botJoinChannel = None
secret_name = "shovelsugi"

# DISCORD_TOKEN取得
try:
    get_secret_value_response = secretsmanager.get_secret_value(
        SecretId=secret_name
    )
    TOKEN = eval(get_secret_value_response["SecretString"])["BOT_TOKEN"]
except ClientError as e:
    raise e

# 接続に必要なオブジェクトを生成
client = discord.Client()

# 文字列の変換
def convertText(message):
    convertText = re.sub('[wWwW]+', 'わらわら', message)
    print(f"元メッセージ: {message}")
    print(f"変換後: {convertText}")
    return convertText

# 起動時に動作する処理
@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    global botJoinChannel
    author = message.author
    if message.author.voice != None:
        authorChannelId = message.author.voice.channel
    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return
    # PREFIXで始まる場合（コマンド実行）の処理
    if message.content.startswith(PREFIX):
        input = message.content.replace(PREFIX, "").split(" ")
        command = input[0]
        # botの呼び出し
        if command == COMMAND_START:
            # 呼び出しユーザのVC参加有無確認
            if message.author.voice is None:
                await message.channel.send("ボイスチャンネルに接続してください。")
                return
            # すでに他のところで呼び出されていないか確認
            if botJoinChannel is not None:
                await message.channel.send(f"すでに{botJoinChannel}に接続してます。")
                return
            # VCに接続
            await message.author.voice.channel.connect()
            await message.channel.send("接続しました。")
            botJoinChannel = message.channel
        # botの切断
        if command == COMMAND_END:
            if message.guild.voice_client is None:
                await message.channel.send("どこも使ってません")
                return
            botJoinChannel = None
            await message.guild.voice_client.disconnect()
            await message.channel.send("切断しました。")
        # helpコマンド
        if command == COMMAND_HELP:
            await message.channel.send("""
                使用可能なコマンド
                ;shl: botの起動
                ;bye: botの停止
                ;help: コマンド一覧
            """)
    # 通常の文章の場合
    elif botJoinChannel == message.channel:
        response = polly.synthesize_speech(
            OutputFormat='mp3',
            SampleRate='22050',
            Text=convertText(message.content),
            TextType='text',
            VoiceId='Mizuki',
        )
        filename = f'{botJoinChannel}_speech.mp3'
        file = open(filename, 'wb')
        file.write(response['AudioStream'].read())
        file.close()
        message.guild.voice_client.play(discord.FFmpegPCMAudio(filename))
# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)