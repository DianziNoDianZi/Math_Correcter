#!/usr/bin/env python3
import paramiko
import socket
import sys

# SSH connection parameters
hostname = '64.90.4.206'
username = 'root'
password = 'cK7jK1uppWAPlHTJ'

def test_port(host, port, timeout=5):
    """Test if a port is open"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

# Test common ports
ports = [22, 2222, 8022, 22022, 22222]
print("检查服务器端口：")
for port in ports:
    status = "开放" if test_port(hostname, port) else "关闭"
    print(f"  端口 {port}: {status}")

# Try to connect on different ports
for port in ports:
    if test_port(hostname, port):
        print(f"\n尝试连接端口 {port}...")
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname, port=port, username=username, password=password, timeout=10)
            print("✅ 连接成功！")
            
            # Test commands
            commands = [
                "echo '测试成功'",
                "pwd",
                "whoami",
                "python3 --version 2>/dev/null || python --version",
                "mkdir -p /workspace/Math_Correcter_test",
                "ls -la /workspace",
            ]
            
            print("\n执行测试命令：")
            for cmd in commands:
                stdin, stdout, stderr = client.exec_command(cmd)
                output = stdout.read().decode('utf-8').strip()
                if output:
                    print(f"  {cmd}: {output}")
            
            client.close()
            print("\n✅ SSH连接和基本操作测试成功！")
            sys.exit(0)
        except Exception as e:
            print(f"端口 {port} 连接失败: {str(e)}")
            continue

print("\n❌ 所有端口都无法连接")
sys.exit(1)
