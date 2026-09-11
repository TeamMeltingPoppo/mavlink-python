import threading
import logging
import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
from datetime import datetime
from pathlib import Path

from mavlink import MAVLinkTopic, MAVLinkBridge, MAVLinkHistory, definition
from mavlink.transport import TransportSerial


class MAVLinkViewerApp(tk.Tk):
    """
    MAVLinkStatus の観測状況 (snapshot) とHistory を Treeviewで表示する例
    """
    def __init__(self):
        super().__init__()
        self.title("MAVLink Status Monitor")
        self.geometry("800x400")

        self.mavlink_topic = MAVLinkTopic()
        self.status = self.mavlink_topic.get_status()
        self.mavlink_history : MAVLinkHistory|None = None

        self.stop_event = threading.Event()
        self.bridge_thread = None
        self.serialport = None

        self._build_ui()
        self._refresh_ports()
        
        # UI更新ループを開始 (200ms間隔)
        self.after(200, self._update_status_display)
        self.after(10, self._update_subscriber)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.recorder=self.mavlink_topic.create_record(Path("logs")/f"log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tlog")

    def _build_ui(self):

        # シリアルポート設定エリア

        conn_frame = ttk.LabelFrame(self, text="Serial Bridge")
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

        self.btn_connect = ttk.Button(conn_frame, text="Connect", command=self.toggle_bridge)
        self.btn_connect.pack(side="left", padx=15)

        status_frame = ttk.Frame(self)
        status_frame.pack(fill="both",expand=True)

        # MAVLink Messages テーブル表示エリア

        messages_frame = ttk.LabelFrame(status_frame,text="Messages")
        messages_frame.pack(fill="both",side="left",expand=True, padx=10, pady=5)

        self.tree_columns = ("msgid", "msgname", "sysid", "compid", "timestamp")
        self.tree_messages = ttk.Treeview(messages_frame, columns=self.tree_columns, show="headings", selectmode="browse")

        self.tree_messages.heading("msgid", text="Msg ID")
        self.tree_messages.heading("msgname", text="Message Name")
        self.tree_messages.heading("sysid", text="Sys ID")
        self.tree_messages.heading("compid", text="Comp ID")
        self.tree_messages.heading("timestamp", text="Timestamp (us)")

        self.tree_messages.column("msgid", minwidth=30,width=30, anchor="center")
        self.tree_messages.column("msgname", minwidth=80,width=80, anchor="w")
        self.tree_messages.column("sysid", minwidth=30,width=30, anchor="center")
        self.tree_messages.column("compid", minwidth=30,width=30, anchor="center")
        self.tree_messages.column("timestamp", minwidth=120,width=120, anchor="e")

        self.tree_messages.bind("<<TreeviewSelect>>", self.on_select_tree)

        messages_scrollbar = ttk.Scrollbar(messages_frame, orient="vertical", command=self.tree_messages.yview)
        self.tree_messages.configure(yscrollcommand=messages_scrollbar.set)
        
        self.tree_messages.pack(side="left", fill="both", expand=True)
        messages_scrollbar.pack(side="right", fill="y")

        # MAVLink Fields テーブル表示エリア
        fields_frame=ttk.LabelFrame(status_frame,text="Fields")
        fields_frame.pack(side="right",fill="both",padx=10,pady=5,expand=True)
        self.tree_fields = ttk.Treeview(fields_frame, columns=("name","value","unit"), show="headings", selectmode="browse")
        self.tree_fields.heading("name", text="Field name")
        self.tree_fields.heading("value", text="Value")
        self.tree_fields.heading("unit", text="Unit")
        self.tree_fields.column("name",anchor="w",minwidth=40,width=40)
        self.tree_fields.column("value",anchor="e",minwidth=80,width=80)
        self.tree_fields.column("unit",anchor="w",minwidth=20,width=20)

        fields_scrollbar = ttk.Scrollbar(fields_frame, orient="vertical", command=self.tree_fields.yview)
        self.tree_fields.configure(yscrollcommand=fields_scrollbar.set)
        self.tree_fields.pack(side="left", fill="both", expand=True)
        fields_scrollbar.pack(side="right", fill="y")

        # ステータスバー
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = ttk.Label(self, textvariable=self.status_var)
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

    def _refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.set(ports[0])

    def toggle_bridge(self):
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        else:
            self.connect()

    def on_select_tree(self,event):
        selection=self.tree_messages.selection()
        if not selection:
            return
        item_id = selection[0]
        item = self.tree_messages.item(item_id)
        if self.mavlink_history:
            self.mavlink_topic.unsubscribe(self.mavlink_history)
        self.mavlink_history = self.mavlink_topic.create_history_subscriber(
            filter=lambda item,target_msgid=item["values"][0],target_sysid=item["values"][2],target_compid=item["values"][3]:
            item.message.get_msgId() == target_msgid and item.message.get_srcSystem() == target_sysid and item.message.get_srcComponent() == target_compid,
            duration=5_000_000
        )

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
            self.status_var.set(f"Bridge Failed: {e}")
            return

        transport = TransportSerial(serialport=self.serialport)
        bridge = MAVLinkBridge(transport=transport, topic=self.mavlink_topic)

        self.stop_event.clear()
        self.bridge_thread = threading.Thread(
            target=bridge.run, 
            args=(self.stop_event,), 
            name="bridge-serialport", 
            daemon=True
        )
        self.bridge_thread.start()

        # UI状態更新
        self.btn_connect.config(text="Disconnect")
        self.port_combo.config(state="disabled")
        self.baud_combo.config(state="disabled")
        self.status_var.set(f"Connected: {port} @ {baud}")

    def disconnect(self):
        self.stop_event.set()

        self.bridge_thread.join(0.1)

        self.bridge_thread = None
        self.serialport = None

        self.btn_connect.config(text="Connect")
        self.port_combo.config(state="normal")
        self.baud_combo.config(state="normal")
        self.status_var.set("Disconnected")

    def _update_status_display(self):
        """MAVLinkStatus の snapshot を取得してMessagesを更新"""
        snapshot = self.status.snapshot()

        for (msgid, sysid, compid) in snapshot.observed_messages:
            msg_name = definition.mavlink_map[msgid].msgname if msgid in definition.mavlink_map else "UNKNOWN"
            last_time = snapshot.last_received.get((msgid, sysid, compid), 0)

            item_id = f"{msgid=}|{sysid=}|{compid=}"
            if self.tree_messages.exists(item_id):
                self.tree_messages.item(item_id, values=(msgid, msg_name, sysid, compid, last_time))
            else:
                self.tree_messages.insert("", "end", iid=item_id, values=(msgid, msg_name, sysid, compid, last_time))

        # 次回の画面更新をスケジューリング
        self.after(100, self._update_status_display)

    def _update_subscriber(self):
        """MAVLinkStatus の snapshot を取得してFieldsを更新"""
        if self.mavlink_history is not None:
            self.mavlink_history.sync()
            msg=self.mavlink_history.latest()
            if msg is not None:
                fieldnames=msg.message.get_fieldnames()
                for name in fieldnames:
                    value=msg.message.format_attr(name)
                    unit=msg.message.fieldunits_by_name.get(name,"")
                    if self.tree_fields.exists(name):
                        self.tree_fields.item(name,values=(name,value,unit))
                    else:
                        self.tree_fields.insert("","end",iid=name,values=(name,value,unit))
                keys=self.tree_fields.get_children()
                for key in keys:
                    if key not in fieldnames:
                        self.tree_fields.delete(key)

        self.after(100,self._update_subscriber)


    def on_closing(self):
        if self.serialport and self.serialport.is_open:
            self.disconnect()
        self.destroy()


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s %(name)s] %(message)s")

    app = MAVLinkViewerApp()
    app.mainloop()
