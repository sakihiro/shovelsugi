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
COMMAND_AN = "an"
COMMAND_ALIAS = "alias"
VC_TABLE = "shovelsugi_vc"
ALIAS_TABLE = "shovelsugi_dict"
botJoinChannel = None
botJoinVoiceChannel = None
secret_name = "shovelsugi"
message_queue = deque([])
announcers = ["Mizuki", "Takumi", "Joanna", "Matthew"]
zatsudanVoiceChannelCount = 0
zatsudanVoiceChannel = "飲酒雑談用VC"
zatsudanChatChannelId = "824238020252925952"

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
    # 辞書登録の変換
    pronunciation = get_shovelsugi_word(message)
    convetText = message.replace(message, pronunciation)
    # 辞書登録の顔文字を変換
    m = re.match(".*(<.+>).*", convetText)
    if m:
        kaomoji = m.group(1)
        pronunciation = get_shovelsugi_word(kaomoji)
        convetText = re.sub("<.+>", pronunciation, convetText)
    else:
        print("不一致")
    # wwをわらわらに変換
    convertText = re.sub('[wWwWｗ]{5,}', 'おおわらわら', convetText)
    convertText = re.sub('[wWwWｗ]{2,}', 'わらわら', convertText)
    # URLを省略
    convertText = re.sub('https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', 'URL省略', convertText)

    print({
        "title": "convertText",
        "元メッセージ": message,
        "変換後": convertText
    })
    return convertText

# 文字列の変換
def personalized(user, message):
    vocal_tract_length, pitch, announcer = get_shovelsugi_vc(user)
    tag_start = f'<speak><amazon:effect vocal-tract-length="{vocal_tract_length}%">'
    tag_end = '</amazon:effect></speak>'
    personalized_text = tag_start + message + tag_end
    print({
        "元メッセージ": message,
        "変換後": personalized_text,
        "voiceID": announcer,
    })
    return polly.synthesize_speech(
            OutputFormat='mp3',
            SampleRate='22050',
            Text=personalized_text,
            TextType='ssml',
            VoiceId=announcer,
        )
 
    return personalized_text

# helpメッセージ
def helpMessage():
    return """
        使用可能なコマンド
        ;shl: botの起動
        ;bye: botの停止
        ;help: コマンド一覧
        ;vc 数字（-50 ~ 200）: 声の高さの変更（;vc 120）
        ;an Mizuki/Takumi: 読み手の切り替え（;an Mizuki）
            日本語： Mizuki（女性）/Takumi（男性）
            英語： Joanna（女性）/Matthew（男性）
        ;alias 文字 読み方: 辞書登録
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

# shovelsugi_vcからuserIDをキーにデータ取得
def get_shovelsugi_vc(userID):
    response = dynamodb.get_item(
        Key={
            'userID': {
                'S': userID,
            },
        },
        TableName=VC_TABLE,
    )
    if not "Item" in response:
        return "100", "0", "Mizuki"
    vocal_tract_length = response["Item"]["vocal_tract_length"]["S"] if "vocal_tract_length" in response["Item"] else "100"
    pitch = response["Item"]["pitch"]["S"] if "pitch" in response["Item"] else "0"
    announcer = response["Item"]["announcer"]["S"] if "announcer" in response["Item"] else "Mizuki"
    return vocal_tract_length, pitch, announcer

# shovelsugi_vcにuserIDをキーにデータを設定
def put_shovelsugi_vc(userID, vocal_tract_length, pitch, announcer):
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
            'announcer': {
                'S': announcer,
            },
        },
        TableName=VC_TABLE,
    )


# shovelsugi_dictにwordをキーにデータを設定
def put_shovelsugi_dict(word, pronunciation):
    dynamodb.put_item(
        Item={
            'word': {
                'S': word,
            },
            'pronunciation': {
                'S': pronunciation,
            },
        },
        TableName=ALIAS_TABLE,
    )


# shovelsugi_vcからuserIDをキーにデータ取得
def get_shovelsugi_word(word):
    response = dynamodb.get_item(
        Key={
            'word': {
                'S': word,
            },
        },
        TableName=ALIAS_TABLE,
    )
    if not "Item" in response:
        return word
    pronunciation = response["Item"]["pronunciation"]["S"] if "pronunciation" in response["Item"] else word
    return pronunciation


# 数字に変換可能かの判定
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
    # 雑談用VCにメンバーが入室時
    if after.channel.name == zatsudanVoiceChannel: 
        global zatsudanVoiceChannelCount
        # botJoinVoiceChannelにいるメンバーの人数チェック
        # 人数が、0人から1人に遷移したとき
        if zatsudanVoiceChannelCount == 0 and len(after.channel.voice_states.keys()) == 1:
            # 入室メッセージを送る
            channel = client.get_channel(zatsudanChatChannelId)
            await channel.send('hello')
        zatsudanVoiceChannelCount = len(before.channel.voice_states.keys())
    # botJoinVoiceChannelからメンバーが退室時
    if before.channel == botJoinVoiceChannel: 
        # botJoinVoiceChannelにいるメンバーの人数チェック
        # len(before.channel.members)だとbot入室後のアクティブユーザのみカウントされる
        if len(before.channel.voice_states.keys()) == 1:
            await member.guild.voice_client.disconnect()
            botJoinChannel = None
            botJoinVoiceChannel = None

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
        # 読み上げ声色コマンド
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
            db_vocal_tract_length, db_pitch, db_announcer = get_shovelsugi_vc(userID)
            put_shovelsugi_vc(userID, vocal_tract_length, pitch, db_announcer)
            return
        # 読み上げVCの変更コマンド
        # ;an Mizuki/Takumi
        if command == COMMAND_AN:
            if len(input) != 2:
                await message.channel.send(";vc MizukiまたはTakumi の形式で入力してください")
                return
            if input[1] not in announcers:
                await message.channel.send(f"{announcers}の中から指定してください")
                return
            announcer = input[1]
            db_vocal_tract_length, db_pitch, db_announcer = get_shovelsugi_vc(userID)
            put_shovelsugi_vc(userID, db_vocal_tract_length, db_pitch, announcer)
            return
        # 辞書登録コマンド
        # ;alias args1 args2
        if command == COMMAND_ALIAS:
            if len(input) != 3:
                await message.channel.send(";alias 単語 読み方 の形式で入力してください")
                return
            word = input[1]
            pronunciation = input[2]
            put_shovelsugi_dict(word, pronunciation)
            return
    # 通常の文章の場合
    elif botJoinChannel == message.channel:
        # 現在時刻の取得
        datetime_now = datetime.datetime.now()
        response = personalized(userID, convertText(message.content))
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
