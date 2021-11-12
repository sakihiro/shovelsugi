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


# helpメッセージ
def zatsudanMessage(userName):
    # <@!767249067553849355>: デバッグ
    # <@&884356359024439336>: リリース用
    return f"""
        <@!767249067553849355>
        {userName}が入室しました。
    """


