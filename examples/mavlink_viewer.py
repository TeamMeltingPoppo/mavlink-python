import threading
import logging
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports

import mavlink
from mavlink import MAVLinkTopic, MAVLinkConnection, definition
from mavlink.transport import TransportSerial


class MAVLinkViewerApp(tk.Tk):
    """
    MAVLinkStatus の観測状況 (snapshot) を Treeview テーブルで表示する例
    (Topic / Status をアプリ起動時に1度だけ作成して再利用する構成)
    """
    def __init__(self):
        super().__init__()
        self.title("MAVLink Status Monitor")
        self.geometry("600x400")

        self.mavlink_topic = MAVLinkTopic()
        self.status = self.mavlink_topic.get_status()

        self.stop_event = threading.Event()
        self.connection_thread = None
        self.serialport = None

        self._build_ui()
        self._refresh_ports()
        
        # UI更新ループを開始 (200ms間隔)
        self.after(200, self._update_status_display)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_ui(self):
        # 接続設定エリア
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
            values=["9600", "57600", "115200", "230400", "460800", "921600"],
            width=10
        )
        self.baud_combo.set("115200")
        self.baud_combo.pack(side="left", padx=5)

        self.btn_connect = ttk.Button(conn_frame, text="Connect", command=self.toggle_connection)
        self.btn_connect.pack(side="left", padx=15)

        # MAVLink Status テーブル表示エリア (Treeview)
        table_frame = ttk.LabelFrame(self, text="Observed Messages (MAVLink Status)")
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("msgid", "msgname", "sysid", "compid", "last_timestamp")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("msgid", text="Msg ID")
        self.tree.heading("msgname", text="Message Name")
        self.tree.heading("sysid", text="Sys ID")
        self.tree.heading("compid", text="Comp ID")
        self.tree.heading("last_timestamp", text="Latest Timestamp (us)")

        self.tree.column("msgid", width=40, anchor="center")
        self.tree.column("msgname", width=80, anchor="w")
        self.tree.column("sysid", width=40, anchor="center")
        self.tree.column("compid", width=40, anchor="center")
        self.tree.column("last_timestamp", width=80, anchor="e")

        # スクロールバー設定
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ステータスバー
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

    def _refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.set(ports[0])

    def toggle_connection(self):
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.port_combo.get()
        baud_str = self.baud_combo.get()

        if not port or not baud_str:
            self.status_var.set("Error: Select Port and Baudrate.")
            return

        try:
            baud = int(baud_str)
            self.serialport = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        except Exception as e:
            self.status_var.set(f"Connection Failed: {e}")
            return

        transport = TransportSerial(serialport=self.serialport)
        connection = MAVLinkConnection(transport=transport, topic=self.mavlink_topic)

        self.stop_event.clear()
        self.connection_thread = threading.Thread(
            target=connection.run, 
            args=(self.stop_event,), 
            name="connection-serialport", 
            daemon=True
        )
        self.connection_thread.start()

        # UI状態更新
        self.btn_connect.config(text="Disconnect")
        self.port_combo.config(state="disabled")
        self.baud_combo.config(state="disabled")
        self.status_var.set(f"Connected: {port} @ {baud}")

    def disconnect(self):
        self.stop_event.set()

        self.connection_thread.join(0.1)

        self.connection_thread = None
        self.serialport = None

        self.btn_connect.config(text="Connect")
        self.port_combo.config(state="normal")
        self.baud_combo.config(state="normal")
        self.status_var.set("Disconnected")

    def _update_status_display(self):
        """MAVLinkStatus の snapshot を取得してテーブルを更新"""
        snapshot = self.status.snapshot()

        for (msgid, sysid, compid) in snapshot.observed_messages:
            msg_name = definition.mavlink_map[msgid].msgname if msgid in definition.mavlink_map else "UNKNOWN"
            last_time = snapshot.last_received.get((msgid, sysid, compid), 0)

            item_id = f"{msgid}_{sysid}_{compid}"
            if self.tree.exists(item_id):
                self.tree.item(item_id, values=(msgid, msg_name, sysid, compid, last_time))
            else:
                self.tree.insert("", "end", iid=item_id, values=(msgid, msg_name, sysid, compid, last_time))

        # 次回の画面更新をスケジューリング
        self.after(200, self._update_status_display)

    def on_closing(self):
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        self.destroy()


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s %(name)s] %(message)s")

    app = MAVLinkViewerApp()
    app.mainloop()