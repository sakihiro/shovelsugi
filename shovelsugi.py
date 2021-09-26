# インストールした discord.py を読み込む
import discord
import boto3
import re
import datetime
import time
from collections import deque
from botocore.exceptions import ClientError

# AWSライブラリ
polly = boto3.client('polly')
secretsmanager = boto3.client('secretsmanager')
dynamodb = boto3.client('dynamodb')

# 変数
TOKEN = ""
PREFIX = ";"
COMMAND_START = "shl"
COMMAND_END = "bye"
COMMAND_HELP = "help"
COMMAND_VC = "vc"
VC_TABLE = "shovelsugi_vc"
botJoinChannel = None
botJoinVoiceChannel = None
secret_name = "shovelsugi"
message_queue = deque([])

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
    # wwをわらわらに変換
    convertText = re.sub('[wWwWｗ]{5,}', 'おおわらわら', message)
    convertText = re.sub('[wWwWｗ]{2,}', 'わらわら', convertText)
    convertText = re.sub('https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', 'URL省略', convertText)
    print({
        "元メッセージ": message,
        "変換後": convertText
    })
    return convertText

# 文字列の変換
def personalized(user, message):
    response = dynamodb.get_item(
        Key={
            'userID': {
                'S': user,
            },
        },
        TableName=VC_TABLE,
    )
    vocal_tract_length = "100"
    if "Item" in response: 
        vocal_tract_length = response["Item"]["vocal_tract_length"]["S"]
    tag_start = f'<speak><amazon:effect vocal-tract-length="{vocal_tract_length}%">'
    tag_end = '</amazon:effect></speak>'
    personalized_text = tag_start + message + tag_end
    print({
        "元メッセージ": message,
        "変換後": personalized_text
    })
    return personalized_text

# helpメッセージ
def helpMessage():
    return """
        使用可能なコマンド
        ;shl: botの起動
        ;bye: botの停止
        ;help: コマンド一覧
        ;vc 数字（-50 ~ 200）: 声の高さの変更（;vc 120）
    """

# 読み上げ速度の調整
def setPitch(vocal_tract_length):
    if len(vocal_tract_length) < -25:
        return "30"
    elif len(vocal_tract_length) < 0:
        return "20"
    elif len(vocal_tract_length) < 50:
        return "10"
    elif len(vocal_tract_length) <= 100:
        return "0"
    elif len(vocal_tract_length) < 125:
        return "-10"
    elif len(vocal_tract_length) < 150:
        return "-20"
    elif len(vocal_tract_length) < 175:
        return "-40"
    elif len(vocal_tract_length) <= 200:
        return "-80"

# 
def is_integer(a):
    try:
        float(a)
    except:
        return False
    return True

# 起動時に動作する処理
@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# VCでのメンバーの入退室時に動作する処理
@client.event
async def on_voice_state_update(member, before, after): 
    global botJoinChannel, botJoinVoiceChannel
    # 入退室がbotの場合
    if member.bot:
        # 何もせず終了
        return
    # botがVCに参加していない場合
    if botJoinVoiceChannel is None:
        # 何もせず終了
        return
    # botJoinVoiceChannelからメンバーが退室時
    if before.channel == botJoinVoiceChannel: 
        # botJoinVoiceChannelにいるメンバーの人数チェック
        if len(before.channel.members) == 1:
            await member.guild.voice_client.disconnect()

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    global botJoinChannel, botJoinVoiceChannel
    author = message.author
    pattern = ".*(#.+)"
    m = re.match(pattern, str(author))
    input = message.content.replace(PREFIX, "").split(" ")
    userID = m.group(1)
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
            botJoinVoiceChannel = message.author.voice.channel
            return
        # botの切断
        if command == COMMAND_END:
            if message.guild.voice_client is None:
                await message.channel.send("どこも使ってません")
                return
            botJoinChannel = None
            botJoinVoiceChannel = None
            await message.guild.voice_client.disconnect()
            await message.channel.send("切断しました。")
            return
        # helpコマンド
        if command == COMMAND_HELP:
            await message.channel.send(helpMessage())
            return
        # 読み上げ音量コマンド
        # ;vc 声帯（数字）
        if command == COMMAND_VC:
            if len(input) != 2:
                await message.channel.send(";vc 数字（-50~200）の形式で入力してください")
                return
            if not is_integer(input[1]):
                await message.channel.send("数字（-50~200）の形式で入力してください")                
                return
            if float(input[1]) < -50:
                await message.channel.send("-50~200の間で入力してください")                
                return
            if float(input[1]) > 200:
                await message.channel.send("-50~200の間で入力してください")                
                return
            vocal_tract_length = input[1]
            pitch = setPitch(vocal_tract_length)
            dynamodb.put_item(
                Item={
                    'userID': {
                        'S': userID,
                    },
                    'vocal_tract_length': {
                        'S': vocal_tract_length,
                    },
                    'pitch': {
                        'S': pitch,
                    },
                },
                TableName=VC_TABLE,
            )
            return
    # 通常の文章の場合
    elif botJoinChannel == message.channel:
        # 現在時刻の取得
        datetime_now = datetime.datetime.now()
        response = polly.synthesize_speech(
            OutputFormat='mp3',
            SampleRate='22050',
            Text=personalized(userID, convertText(message.content)),
            TextType='ssml',
            VoiceId='Mizuki',
        )
        folder = "mp3/"
        filename = f'{botJoinChannel}_{datetime_now.strftime("%Y%m%d%H%M%S%f")}.mp3'
        file = open(folder + filename, 'wb')
        file.write(response['AudioStream'].read())
        file.close()

        message_queue.append(filename)
        while(len(message_queue) > 0):
            # botが読み上げ中の時は待機
            while(message.guild.voice_client.is_playing()):
                time.sleep(1)
            message.guild.voice_client.play(discord.FFmpegPCMAudio(folder + message_queue[0]))
            message_queue.popleft()

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)
