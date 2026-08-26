# Examples

## Basic

### [mavlink_subscriber.py](./mavlink_subscriber.py)

MAVLinkメッセージをSubscriberで受信する基本的な例です。

### [mavlink_history.py](./mavlink_history.py)

1sごとに受信したMAVLinkメッセージの履歴を参照する例です。

## Communication

### [topic_udpin](./topic_udpin.py)

UDPからMAVLinkメッセージを受信する例です。`multi_bridge.py`を同時に実行することでプロセス間の通信も可能です。

### [multiple_bridge.py](./multiple_bridge.py)

1つのTopicに複数のBridgeを接続し、SerialとUDPを同時に利用する例です。

## Application

### [mavlink_viewer.py](./mavlink_viewer.py)

`tkinter`を利用した簡易的なMAVLink Viewerです。`mavlink-python`を利用してGUIアプリケーションを構築する例として提供しています。

### [mock_node.py](./mock_node.py)

`Node`を継承してユーザー独自のアプリケーションを実装する例です。メッセージの送受信とログ保存を行います。

## Logging

### [tlog_to_df.py](./tlog_to_df.py)

.tlogファイルを読み込み、Message TypeおよびSystem ID / Component IDごとにpandas.DataFrameへ変換する例です。

※ このExampleではpandasを使用します。pandasはmavlink-pythonの必須依存ではありません。

### [tlog_replay.py](./tlog_replay.py)

TlogReaderを利用してログを再生する実装例です。