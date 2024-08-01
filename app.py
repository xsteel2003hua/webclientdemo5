import os
import subprocess
import threading
import socket
import streamlit as st

# 下载 cloudflared 二进制文件
@st.cache_resource
def download_cloudflared():
    os.makedirs(os.path.expanduser('~/cloudflared'), exist_ok=True)
    os.chdir(os.path.expanduser('~/cloudflared'))
    subprocess.run('curl -LO https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', shell=True, check=True)

# 给 cloudflared 二进制文件添加执行权限
@st.cache_resource
def add_execute_permission():
    subprocess.run('chmod +x cloudflared-linux-amd64', shell=True, check=True)

# 将 cloudflared 二进制文件移动到用户的 bin 目录
@st.cache_resource
def move_binary_to_bin():
    os.makedirs(os.path.expanduser('~/bin'), exist_ok=True)
    subprocess.run('mv cloudflared-linux-amd64 ~/bin/cloudflared', shell=True, check=True)

# 更新 PATH 环境变量
@st.cache_resource
def update_path():
    # 更新当前 Python 环境的 PATH 变量
    os.environ["PATH"] = os.path.expanduser('~/bin') + os.pathsep + os.environ["PATH"]

# 验证 cloudflared 安装
@st.cache_resource
def verify_installation():
    result = subprocess.run('cloudflared --version', shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(result.stderr)
        raise Exception("cloudflared 安装失败")

# 运行 cloudflared 隧道命令
@st.cache_resource
def run_cloudflared_tunnel():
    token = "eyJhIjoiOTkzNjQxZjM4M2I0OGQxNGJjMmIzMGVlOGVlNDdlNzciLCJ0IjoiZDc4NTJhZDYtOWM0OC00MGNhLWE3NzItYzQyMjRmYjQ4ZWUxIiwicyI6Ik5EWTJNMk0yWVRZdFpURXpOUzAwT1RVM0xUZ3pOalV0TnpVMlpEUm1NVEV4T0RBNCJ9"  # 请替换为实际的token
    subprocess.Popen(f'nohup cloudflared tunnel --no-autoupdate run --token {token} > cloudflared.log 2>&1 &', shell=True)

# 在独立线程中运行 cloudflared
@st.cache_resource
def run_cloudflared_in_thread():
    thread = threading.Thread(target=run_cloudflared_tunnel)
    thread.start()

# 处理客户端连接的函数
def handle_client(client_socket):
    request = client_socket.recv(4096)
    if not request:
        client_socket.close()
        return

    # 解析 CONNECT 请求
    request_lines = request.split(b'\r\n')
    if len(request_lines) < 1:
        client_socket.close()
        return

    request_line = request_lines[0].decode('utf-8')
    method, url, version = request_line.split()

    if method != 'CONNECT':
        client_socket.close()
        return

    host, port = url.split(':')
    port = int(port)

    # 发送 200 Connection Established 响应
    client_socket.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')

    # 连接到远程服务器
    remote_socket = socket.create_connection((host, port))

    # 开始在客户端和远程服务器之间转发数据
    def forward(source, destination):
        while True:
            try:
                data = source.recv(4096)
                if not data:
                    break
                destination.sendall(data)
            except Exception as e:
                print(f"Error: {e}")
                break
        source.close()
        destination.close()

    client_to_remote = threading.Thread(target=forward, args=(client_socket, remote_socket))
    remote_to_client = threading.Thread(target=forward, args=(remote_socket, client_socket))

    client_to_remote.start()
    remote_to_client.start()

    client_to_remote.join()
    remote_to_client.join()

# 启动代理服务器
@st.cache_resource
def start_proxy_server():
    def start_proxy(host, port):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f'Proxy server listening on {host}:{port}')

        while True:
            client_socket, addr = server_socket.accept()
            print(f'Accepted connection from {addr}')
            client_handler = threading.Thread(target=handle_client, args=(client_socket,))
            client_handler.start()

    proxy_thread = threading.Thread(target=start_proxy, args=('0.0.0.0', 8083))
    proxy_thread.start()
    return proxy_thread

# 启动 Streamlit 应用
def start_streamlit_app():
    def main():
        st.title("Streamlit Demo")
        st.write("Welcome to the Streamlit demo application!")

    main()

# 主函数
if __name__ == '__main__':
    # 执行 cloudflared 安装和运行步骤
    download_cloudflared()
    add_execute_permission()
    move_binary_to_bin()
    update_path()
    verify_installation()
    run_cloudflared_in_thread()

    # 启动代理服务器
    proxy_thread = start_proxy_server()

    # 启动 Streamlit 应用
    start_streamlit_app()

    # 等待所有线程完成
    proxy_thread.join()
