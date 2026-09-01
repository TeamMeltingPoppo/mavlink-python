"""
このモジュールは、MAVLinkのPythonバインディングを初期化するためのものです。
MAVLinkのXML定義ファイルからPythonコードを生成しpathが通るようにしています。
"""
from pathlib import Path
from logging import getLogger, basicConfig
from pymavlink.generator import mavgen

def generate_mavlink_bindings():

    ROOT_DIR = Path(__file__).parents[1].resolve() # global変数は汚したくないので、関数内で定義
    logger = getLogger("generate_mavlink_bindings")
    basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")

    mavlink_dir = ROOT_DIR / "src" / "mavlink"
    opts = mavgen.Opts( str(mavlink_dir / "definition" ),"2.0","Python3")
    mavgen.mavgen(opts,[ROOT_DIR / "mavlink-dialect" / "dialects" / "swingby.xml"])
    logger.info(f"mavlinkのPythonバインディングを生成しました: {mavlink_dir}")

if __name__ == "__main__":
    generate_mavlink_bindings()