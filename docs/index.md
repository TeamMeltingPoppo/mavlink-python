# mavlink-python

MAVLinkを利用した通信・データ処理システムを構築するためのPythonライブラリです。

`mavlink-python` は、MAVLinkメッセージの送受信だけでなく、メッセージの購読、履歴管理、ログ保存、リプレイなど、MAVLinkを利用するアプリケーションに必要となる機能を提供します。

シミュレーション、Software-in-the-Loop Simulation（SILS）、Hardware-in-the-Loop Simulation（HILS）をはじめ、実機を用いた通信・データ処理にも利用できることを目指しています。

## 特徴

- MAVLink dialectに基づくメッセージの送受信
- Publisher / Subscriberによるメッセージ配信
- マルチスレッド環境を考慮したデータアクセス
- MAVLink telemetry log（`.tlog`）形式でのログ保存
- コア機能を軽量に保った構成
- 通信媒体をTransportとして抽象化
- 受信したメッセージの履歴管理
- 保存したMAVLinkデータのリプレイ

MAVLinkのメッセージ定義と、通信・データ処理の機能を分離していることが本ライブラリの主要な設計方針です。

## MAVLink Dialect

`mavlink-python` 自体ではMAVLinkのメッセージを定義しません。

[`mavlink dialect`](https://github.com/TeamMeltingPoppo/mavlink-dialect)からコード生成ツールによってPythonのMAVLinkモジュールを生成し、それを `mavlink-python` から利用します。

```text
MAVLink Dialect
      │
      ▼
Generated MAVLink module
      │
      ├── Message definitions
      ├── Encoder / Decoder
      └── mavlink_map
              │
              ▼
        mavlink-python
              │
              ├── Transport
              ├── Publisher / Subscriber
              ├── History
              └── Logging / Replay
```

この構成により、MAVLinkのメッセージ定義と、それを利用するアプリケーションの機能を分離できます。

## Getting Started

### インストール

バージョンが0.7.0のmavlink-pythonをインストールするには、以下を実行してください。

```bash
pip install https://github.com/TeamMeltingPoppo/mavlink-python/releases/download/0.7.0/mavlink-0.7.0-py3-none-any.whl
```

### 最初のプログラム

```python
import serial
import threading

from mavlink import MAVLinkBridge, MAVLinkTopic
from mavlink.transport import TransportSerial

topic = MAVLinkTopic()

subscriber = topic.create_subscriber(
    lambda msgid, sysid, compid: True
)

transport = TransportSerial(
    serialport=serial.Serial("COM5")
)

bridge = MAVLinkBridge(
    transport=transport,
    topic=topic,
)

stop_event = threading.Event()

thread = threading.Thread(
    target=bridge.run,
    args=(stop_event,),
)
thread.start()

try:
    while True:
        result = subscriber.get(timeout=1.0)
        if result:
            print(result.message)
except KeyboardInterrupt:
    pass
finally:
    stop_event.set()
    thread.join()
```

この例では、

- `TransportSerial`
- `MAVLinkBridge`
- `MAVLinkTopic`
- `MAVLinkSubscriber`

を使用しています。それぞれの役割と関係については [Architecture](architecture.md) を参照してください。

## Examples

より具体的な利用方法については [examples](https://github.com/TeammeltingPoppo/mavlink-python/blob/main/examples/) を参照してください。

Examplesでは、以下のような利用方法を扱っています。

- SubscriberによるMAVLinkメッセージの受信
- Message Historyの利用
- UDP通信
- 複数のBridgeの接続
- `Node`を利用したアプリケーションの実装
- GUIアプリケーション
- TLogのDataFrameへの変換
- TLogのReplay

## 設計方針

`mavlink-python` では、以下の分離を重視しています。

1. MAVLinkのメッセージ定義とアプリケーションを分離する
2. 通信媒体とメッセージ処理を分離する
3. メッセージの送受信とアプリケーションによる処理を分離する
4. 記録したMAVLinkデータを、通信入力と同じように再利用できるようにする
5. コアパッケージの依存関係を最小限にする

本ライブラリは、Ground Control Station（GCS）やフライトスタックそのものを置き換えることを目的としていません。

MAVLinkを利用したシステムを構築するための、通信・データ処理の基盤を提供することを目的としています。

## 想定する用途

`mavlink-python` は、例えば次のような用途で利用できます。

- SILS / HILS / MILS
- フライトデータロギング
- テレメトリの可視化
- 実機試験
- センサーデータ解析
- 通信試験
- MAVLink通信のリプレイ