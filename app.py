"""工作台统一启动入口。"""
import argparse
import sys
import uvicorn
from paths import data_directory, state_directory
from webapp.api import create_app

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="QuantLab A股研究工作台")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--data")
    parser.add_argument("--state")
    args=parser.parse_args()
    data=data_directory(args.data)
    print(f"行情目录：{data}\n工作台：http://{args.host}:{args.port}")
    uvicorn.run(create_app(data,state_directory(args.state)),host=args.host,port=args.port)

if __name__=="__main__":
    main()
