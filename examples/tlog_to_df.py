from pathlib import Path
from mavlink import TLogReader
import pandas as pd

def log_to_dataframes(filepath:Path)->dict[str,dict[tuple[int,int],pd.DataFrame]]:
    reader=TLogReader(filepath=filepath)
    records:dict[str,dict[tuple[int,int],tuple[list[int],list[dict]]]]={}
    for timestamp,message in reader:
        if message.get_type() not in records.keys():
            records[message.get_type()]={}
        key=(message.get_srcSystem(),message.get_srcComponent())
        if key not in records[message.get_type()]:
            records[message.get_type()][key]=[],[]
        records[message.get_type()][key][0].append(timestamp)
        records[message.get_type()][key][1].append(message.to_dict())
    dict_df:dict[str,dict[tuple[int,int],pd.DataFrame]]={}
    for msg_type in records.keys():
        dict_df[msg_type]={}
        for key in records[msg_type].keys():
            dict_df[msg_type][key]=pd.DataFrame(
                records[msg_type][key][1],
                index=pd.to_datetime(records[msg_type][key][0],unit="us",utc=True)
            )
    return dict_df

if __name__ == "__main__":
    sysid,compid=1,1
    df=log_to_dataframes(Path("examples/sample.tlog"))["GPS_RAW_INT"][(sysid,compid)]
    print(df)