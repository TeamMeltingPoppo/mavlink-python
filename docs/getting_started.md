# Getting Started

このページでは、`mavlink-python` を使ってMAVLinkメッセージを
受信するまでの基本的な手順を説明します。

## 前提環境

- Python 3.14

## インストール

以下では バージョン`0.6.0` を使用します。

```bash
pip install https://github.com/TeamMeltingPoppo/mavlink-python/releases/download/0.6.0/mavlink-0.6.0-py3-none-any.whl
```

## 最初のプログラム

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
を使用しています。それぞれの役割と関係については [[Architecture]] を参照してください。

## Examples

より具体的な利用方法については [Examples](../examples/README.md) を参照してください。

Examplesでは、以下のような利用方法を扱っています。

- SubscriberによるMAVLinkメッセージの受信
- Message Historyの利用
- UDP通信
- 複数のBridgeの接続
- `Node`を利用したアプリケーションの実装
- GUIアプリケーション
- TLogのDataFrameへの変換
- TLogのReplay