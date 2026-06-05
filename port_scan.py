#!/usr/bin/env python3
import socket

hostname = '64.90.4.206'
ports = [22, 2222, 2200, 22000, 22222, 80, 443, 8080]

print(f"扫描 {hostname} 的常用端口...")
print("=" * 50)

for port in ports:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex((hostname, port))
    sock.close()
    
    if result == 0:
        print(f"✅ 端口 {port} - 开放")
    else:
        print(f"❌ 端口 {port} - 关闭")

print("=" * 50)
print("\n尝试SSH连接...")
