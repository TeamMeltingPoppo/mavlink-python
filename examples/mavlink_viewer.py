import threading
import time
import logging
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports

import mavlink
from mavlink import MAVLinkConnection
from mavlink import definition
from mavlink.transport import TransportSerial


class MAVLinkViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MAVLink Tkinter Example")
        self.logger = logging.getLogger("MAVLinkViewer")
        self.geometry("750x500")

        self.stop_event = threading.Event()
        self.threads = []
        self.serialport = None
        self.subscriber = None
        self.recorder = None
        # MAVLink Topic & Log 準備
        self.mavlink_topic = mavlink.MAVLinkTopic()
        self.mav=definition.MAVLink(None,1,10)
        
        # Direct Subscriber & Publisher
        self.subscriber = self.mavlink_topic.create_subscriber(
            lambda msgid, sysid, compid: (sysid == 1) and (compid == 1)
        )
        self.publisher = self.mavlink_topic.create_publisher()

        self._build_ui()
        self._refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_ui(self):
        # 接続設定フレーム
        conn_frame = ttk.LabelFrame(self, text="Serial Connection")
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Port:").pack(side="left", padx=(10, 2))
        self.port_combo = ttk.Combobox(conn_frame, width=15)
        self.port_combo.pack(side="left", padx=5)

        btn_refresh = ttk.Button(conn_frame, text="↻", width=3, command=self._refresh_ports)
        btn_refresh.pack(side="left", padx=(0, 10))

        ttk.Label(conn_frame, text="Baudrate:").pack(side="left", padx=(5, 2))
        self.baud_combo = ttk.Combobox(
            conn_frame, 
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            width=10
        )
        self.baud_combo.set("115200")
        self.baud_combo.pack(side="left", padx=5)

        self.btn_connect = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=15)

        # メッセージ送信操作フレーム
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=5)

        self.btn_send_heartbeat = ttk.Button(
            control_frame, 
            text="Send HEARTBEAT", 
            command=self.send_heartbeat,
            state="disabled"
        )
        self.btn_send_heartbeat.pack(side="left", padx=5)

        # ログ表示エリア
        self.log_area = scrolledtext.ScrolledText(self, state="disabled", wrap="word")
        self.log_area.pack(fill="both", expand=True, padx=10, pady=5)

        # ステータスバー
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

    def _refresh_ports(self):
        """利用可能なシリアルポートを検出してComboboxを更新"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])

    def toggle_connection(self):
        """Connect / Disconnect ボタンの切り替え"""
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """接続処理"""
        port = self.port_combo.get()
        baud_str = self.baud_combo.get()

        if not port or not baud_str:
            self.logger.error("Error: Select Port and Baudrate.")
            return

        try:
            baud = int(baud_str)
            self.serialport = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        except serial.SerialException as e:
            self.logger.error(f"Connection Failed: {e}")
            return

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        filepath = log_dir / f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tlog"
        self.recorder=self.mavlink_topic.create_record(filepath=filepath)

        transport = TransportSerial(serialport=self.serialport)
        self.connection = MAVLinkConnection(transport=transport, topic=self.mavlink_topic)

        self.stop_event.clear()
        self.threads = [
            threading.Thread(target=self.connection.run_rx, args=(self.stop_event,), name="mavlink-rx", daemon=True),
            threading.Thread(target=self.connection.run_tx, args=(self.stop_event,), name="mavlink-tx", daemon=True),
        ]

        for thread in self.threads:
            thread.start()

        # UI状態更新
        self.btn_connect.config(text="Disconnect")
        self.port_combo.config(state="disabled")
        self.baud_combo.config(state="disabled")
        self.btn_send_heartbeat.config(state="normal")
        self.logger.info(f"Connected: {port} @ {baud} | Log: {filepath.name}")

        # ポーリング開始
        self.after(10, self._poll_subscriber)

    def disconnect(self):
        """接続解除処理"""
        self.stop_event.set()

        if self.serialport and self.serialport.is_open:
            self.serialport.close()

        if self.recorder:
            self.mavlink_topic.unsubscribe(self.recorder)

        self.connection.close()

        self.recorder=None

        self.threads = []
        self.serialport = None

        # UI状態のリセット
        self.btn_connect.config(text="Connect")
        self.port_combo.config(state="normal")
        self.baud_combo.config(state="normal")
        self.btn_send_heartbeat.config(state="disabled")
        self.status_var.set("Disconnected")
        self.logger.info("Disconnected from serial port.")

    def _poll_subscriber(self):

        while True:
            result = self.subscriber.get(timeout=0)
            if not result:
                break

            timestamp_str = datetime.now().strftime('%H:%M:%S.%f')
            log_str = f"[{timestamp_str}] {result.message}"
            self._append_log(log_str)

        self.after(10, self._poll_subscriber)

    def send_heartbeat(self):
        if not self.mavlink_topic:
            return

        heartbeat = mavlink.definition.MAVLink_heartbeat_message(
            type=mavlink.definition.MAV_TYPE_GENERIC,
            autopilot=mavlink.definition.MAV_AUTOPILOT_GENERIC,
            base_mode=mavlink.definition.MAV_MODE_PREFLIGHT,
            custom_mode=0,
            system_status=mavlink.definition.MAV_STATE_ACTIVE,
            mavlink_version=3
        )
        heartbeat.pack(self.mav)

        self.mavlink_topic.publish(
            timestamp=time.time_ns() // 1000, 
            message=heartbeat, 
            source=self
        )
        self._append_log("[Tx] Sent HEARTBEAT from GUI thread")

    def _append_log(self, text: str):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def on_closing(self):
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        self.destroy()


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s %(name)s] %(message)s")

    app = MAVLinkViewerApp()
    app.mainloop()