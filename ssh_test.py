#!/usr/bin/env python3
import paramiko
import sys

# SSH connection parameters
hostname = '64.90.4.206'
port = 22
username = 'root'
password = 'cK7jK1uppWAPlHTJ'

try:
    # Create SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Connect to server
    print(f"正在连接到 {hostname}...")
    client.connect(hostname, port=port, username=username, password=password, timeout=10)
    print("✅ 连接成功！")
    
    # Create test directory
    test_dir = '/workspace/Math_Correcter_test'
    commands = [
        f"mkdir -p {test_dir}",
        f"echo '测试目录创建成功' > {test_dir}/test.txt",
        f"ls -la {test_dir}",
        "pwd",
        "uname -a",
        "python3 --version",
    ]
    
    print("\n执行测试命令：")
    print("=" * 60)
    
    for cmd in commands:
        print(f"\n$ {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if output:
            print(output.rstrip())
        if error:
            print(f"错误: {error.rstrip()}")
        
        if exit_status == 0:
            print("✅ 命令执行成功")
        else:
            print(f"❌ 命令执行失败 (退出码: {exit_status})")
    
    print("=" * 60)
    
    # Test git and clone project
    print("\n测试Git克隆：")
    clone_cmd = f"cd {test_dir} && git clone https://github.com/DianziNoDianZi/Math_Correcter.git ."
    print(f"$ {clone_cmd}")
    stdin, stdout, stderr = client.exec_command(clone_cmd)
    exit_status = stdout.channel.recv_exit_status()
    
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')
    
    if output:
        print(output.rstrip())
    if error:
        print(f"错误: {error.rstrip()}")
    
    if exit_status == 0:
        print("✅ Git克隆成功！")
    else:
        print(f"❌ Git克隆失败 (退出码: {exit_status})")
    
    # List cloned files
    list_cmd = f"ls -la {test_dir}"
    stdin, stdout, stderr = client.exec_command(list_cmd)
    output = stdout.read().decode('utf-8')
    print(f"\n目录内容：\n{output}")
    
    # Close connection
    client.close()
    print("\n✅ 测试完成！SSH连接正常。")
    
except paramiko.AuthenticationException:
    print("❌ 认证失败！请检查密码是否正确。")
    sys.exit(1)
except paramiko.SSHException as e:
    print(f"❌ SSH连接错误: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 连接失败: {str(e)}")
    sys.exit(1)
