"""
Gradio Web UI for AutoGLM
提供用户友好的Web界面来使用AutoGLM进行Android设备自动化操作
"""

import gradio as gr
import subprocess
import threading
import queue
import time
import os
import sys
import datetime

# --- 全局命令执行管理器 ---
class CommandRunner:
    def __init__(self):
        self.process = None
        self.logs = ""
        self.is_running = False
        self.log_lock = threading.Lock()
        
    def start(self, cmd_args, cwd=None, env=None):
        """启动新命令"""
        if self.is_running:
            return False, "当前已有任务在运行，请先停止"
            
        self.stop() # 确保清理
        
        # 重置状态
        with self.log_lock:
            # 清空旧日志，开始新日志
            self.logs = f"--- 任务开始: {' '.join(cmd_args)} ---\n"
            print(f"\n[WebUI] 启动任务: {' '.join(cmd_args)}")

        self.is_running = True
        
        # 启动后台线程
        thread = threading.Thread(target=self._run_thread, args=(cmd_args, cwd, env), daemon=True)
        thread.start()
        return True, "任务已启动"

    def stop(self):
        """停止当前任务"""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception as e:
                self._append_log(f"\n[系统] 停止进程失败: {e}\n")
        
        self.is_running = False
        return "任务停止指令已发送"

    def _run_thread(self, cmd_args, cwd, env):
        try:
            self.process = subprocess.Popen(
                cmd_args,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,  # 行缓冲
                universal_newlines=True
            )
            
            # 实时读取输出
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    # 1. 写入 Web UI 日志
                    self._append_log(line)
                    # 2. 同步打印到后台终端 (end="" 因为 line 自带换行)
                    print(line, end="", flush=True)
            
            self.process.wait()
            end_msg = f"\n--- 任务结束 (代码: {self.process.returncode}) ---\n"
            self._append_log(end_msg)
            print(end_msg)
            
        except Exception as e:
            err_msg = f"\n[系统错误] 执行异常: {str(e)}\n"
            self._append_log(err_msg)
            print(err_msg)
        finally:
            self.is_running = False
            self.process = None

    def _append_log(self, text):
        with self.log_lock:
            # 日志保留策略
            if len(self.logs) > 1000000:
                self.logs = self.logs[-800000:]
            self.logs += text

    def get_logs(self):
        with self.log_lock:
            return self.logs

    def get_status(self):
        return "🟢 运行中" if self.is_running else "⚪ 就绪"

# 全局单例
runner = CommandRunner()

# --- 辅助函数 ---

def get_adb_devices():
    """获取所有已连接的设备（包括USB和无线）"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        devices = []
        device_details = []

        if result.returncode == 0:
            lines = result.stdout.split('\n')[1:]  # 跳过标题行
            for line in lines:
                if '\tdevice' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
                    # 判断是USB还是无线连接
                    if ':' in device_id:
                        # 无线设备（IP:端口格式）
                        device_type = "📶 无线"
                    else:
                        # USB设备
                        device_type = "🔌 USB"
                    device_details.append(f"{device_type}: {device_id}")

        if not device_details:
            return ["未找到设备"], ""

        # 格式化设备列表
        device_list = "\n".join(device_details)
        all_devices = ", ".join(devices)

        return devices, f"已连接设备 ({len(devices)}个):\n\n{device_list}\n\n默认设备: {devices[0]}"
    except Exception as e:
        return [f"错误: {str(e)}"], f"获取设备列表失败: {str(e)}"

def connect_wireless_device(ip_address, port="5555"):
    """连接无线设备"""
    try:
        # 验证IP地址格式
        parts = ip_address.strip().split('.')
        if len(parts) != 4 or not all(0 <= int(p) <= 255 for p in parts if p.isdigit()):
            return False, "无效的IP地址格式"

        # 构造连接地址
        connect_addr = f"{ip_address}:{port}"

        # 执行连接命令
        result = subprocess.run(
            ["adb", "connect", connect_addr],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )

        if result.returncode == 0:
            # 验证是否真正连接成功
            devices_result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            if connect_addr in devices_result.stdout and "device" in devices_result.stdout:
                return True, f"成功连接到无线设备: {connect_addr}"
            else:
                return False, f"连接失败，请检查:\n1. 手机是否开启无线调试\n2. IP地址是否正确\n3. 手机和电脑是否在同一网络"
        else:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            return False, f"连接失败: {error_msg}"

    except subprocess.TimeoutExpired:
        return False, "连接超时，请检查网络连接"
    except Exception as e:
        return False, f"连接出错: {str(e)}"

def disconnect_wireless_device(device_id):
    """断开无线设备"""
    try:
        # 如果设备ID包含端口，直接使用；否则尝试断开所有无线连接
        if ':' in device_id:
            # 断开特定设备
            result = subprocess.run(
                ["adb", "disconnect", device_id],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
        else:
            # 断开所有无线连接
            result = subprocess.run(
                ["adb", "disconnect"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

        if result.returncode == 0:
            return True, "已断开无线设备连接"
        else:
            return False, "断开连接失败"

    except Exception as e:
        return False, f"断开连接出错: {str(e)}"

def enable_tcpip(device_id, port="5555"):
    """在USB连接的设备上启用TCP/IP模式（用于无线调试）"""
    try:
        # 确保设备是USB连接且在线
        devices_result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )

        if device_id not in devices_result.stdout:
            return False, f"设备 {device_id} 未连接"

        # 启用TCP/IP
        result = subprocess.run(
            ["adb", "-t", "tcpip", str(port)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )

        if result.returncode == 0:
            # 尝试获取设备IP
            ip_result = subprocess.run(
                ["adb", "shell", "ip", "route", "get", "8.8.8.8"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            device_ip = "未知"
            if ip_result.returncode == 0:
                for line in ip_result.stdout.split('\n'):
                    if "src" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "src" and i + 1 < len(parts):
                                device_ip = parts[i + 1]
                                break

            return True, f"TCP/IP已启用在端口 {port}\n设备IP地址: {device_ip}\n现在可以使用无线连接了"
        else:
            return False, f"启用TCP/IP失败: {result.stderr}"

    except Exception as e:
        return False, f"启用TCP/IP出错: {str(e)}"

def get_available_apps():
    try:
        result = subprocess.run(
            ["adb", "shell", "pm", "list", "packages", "-3"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        if result.returncode != 0:
            return "获取失败"
        apps = [line.replace('package:', '').strip() for line in result.stdout.splitlines() if line.strip()]
        apps.sort()
        return "\n".join(apps)
    except Exception as e:
        return str(e)

# --- Scrcpy 启动器 ---
def start_scrcpy():
    """启动 scrcpy 屏幕镜像"""
    try:
        # scrcpy 可执行文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(current_dir)
        scrcpy_path = os.path.join(project_dir, "scrcpy-win64-v3.3.3", "scrcpy.exe")

        # 调试信息
        print(f"[DEBUG] 项目目录: {project_dir}")
        print(f"[DEBUG] scrcpy 路径: {scrcpy_path}")
        print(f"[DEBUG] 文件存在: {os.path.exists(scrcpy_path)}")

        if not os.path.exists(scrcpy_path):
            return False, f"未找到 scrcpy.exe: {scrcpy_path}"

        # 检查是否有设备连接
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, encoding='utf-8')
        devices = []
        for line in result.stdout.split('\n')[1:]:
            if '\tdevice' in line:
                device_id = line.split('\t')[0]
                # 判断是USB还是无线设备
                if ':' in device_id:
                    device_type = "无线"
                else:
                    device_type = "USB"
                devices.append(f"{device_type}: {device_id}")

        if not devices:
            return False, "没有检测到已连接的设备，请先连接设备"

        # 准备启动命令
        scrcpy_cmd = [scrcpy_path]

        # 如果有多个设备，使用第一个
        if len(devices) > 1:
            first_device = devices[0].split(': ')[1]
            # 尝试指定设备
            scrcpy_cmd.extend(['-s', first_device])
            device_info = f"使用第一个设备 ({first_device})"
        else:
            device_info = devices[0]

        # 启动 scrcpy
        def run_scrcpy():
            try:
                print(f"[INFO] 启动 scrcpy: {' '.join(scrcpy_cmd)}")
                # Windows 下在新控制台窗口中启动
                if os.name == 'nt':
                    subprocess.Popen(scrcpy_cmd,
                                   creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(scrcpy_cmd)
                print(f"[INFO] scrcpy 启动成功")
            except Exception as e:
                print(f"[ERROR] 启动 scrcpy 失败: {e}")

        # 在新线程中启动，避免阻塞 UI
        thread = threading.Thread(target=run_scrcpy, daemon=True)
        thread.start()

        # 等待一下让进程启动
        time.sleep(0.5)

        return True, f"✅ scrcpy 已启动\n{device_info}"

    except Exception as e:
        print(f"[ERROR] start_scrcpy 异常: {e}")
        return False, f"启动 scrcpy 失败: {str(e)}"

def check_adb_connection():
    """检查ADB连接状态和设备列表"""
    try:
        # 检查ADB服务器状态
        result = subprocess.run(["adb", "start-server"],
                              capture_output=True, text=True, timeout=5)

        # 获取设备列表
        result = subprocess.run(["adb", "devices"],
                              capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            devices = []

            for line in lines[1:]:  # 跳过第一行标题
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        device_id = parts[0].strip()
                        status = parts[1].strip()
                        devices.append(f"📱 {device_id} - {status}")

            if devices:
                device_info = "\n".join(devices)
                return True, f"✅ ADB服务正常\n已连接设备:\n{device_info}"
            else:
                return False, "⚠️ ADB服务正常但无设备连接\n请检查:\n- 手机是否开启USB调试\n- 数据线是否连接正常\n- 是否已授权此电脑"
        else:
            return False, f"❌ ADB命令执行失败\n错误信息: {result.stderr}"

    except FileNotFoundError:
        return False, "❌ ADB未安装或未添加到PATH\n请安装Android Platform Tools"
    except subprocess.TimeoutExpired:
        return False, "❌ ADB命令超时\n请尝试重启ADB服务"
    except Exception as e:
        return False, f"❌ 检查ADB连接时出错: {str(e)}"

def restart_adb():
    """重启ADB服务"""
    try:
        # 执行 adb kill-server
        result_kill = subprocess.run(["adb", "kill-server"],
                                   capture_output=True, text=True, timeout=10)

        # 等待1秒确保服务完全停止
        import time
        time.sleep(1)

        # 执行 adb start-server
        result_start = subprocess.run(["adb", "start-server"],
                                    capture_output=True, text=True, timeout=10)

        if result_kill.returncode == 0 and result_start.returncode == 0:
            # 再次检查设备列表
            result_devices = subprocess.run(["adb", "devices"],
                                          capture_output=True, text=True, timeout=5)

            if result_devices.returncode == 0:
                lines = result_devices.stdout.strip().split('\n')
                devices = []

                for line in lines[1:]:  # 跳过第一行标题
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            device_id = parts[0].strip()
                            status = parts[1].strip()
                            devices.append(f"📱 {device_id} - {status}")

                if devices:
                    device_info = "\n".join(devices)
                    return True, f"✅ ADB服务重启成功\n\n当前连接设备:\n{device_info}"
                else:
                    return True, "✅ ADB服务重启成功\n\n当前无设备连接\n请连接设备并开启USB调试"
            else:
                return True, "✅ ADB服务重启成功\n\n注意：无法获取设备列表"
        else:
            error_msg = ""
            if result_kill.returncode != 0:
                error_msg += f"停止ADB失败: {result_kill.stderr}\n"
            if result_start.returncode != 0:
                error_msg += f"启动ADB失败: {result_start.stderr}"
            return False, f"❌ ADB重启失败\n{error_msg}"

    except FileNotFoundError:
        return False, "❌ ADB未安装或未添加到PATH\n请安装Android Platform Tools"
    except subprocess.TimeoutExpired:
        return False, "❌ ADB命令超时\n请手动执行:\nadb kill-server\nadb start-server"
    except Exception as e:
        return False, f"❌ 重启ADB时出错: {str(e)}"

# --- Gradio 界面 ---

def create_ui():
    with gr.Blocks(title="AutoGLM Web Controller") as demo:

        gr.Markdown("## 🤖 Open-AutoGLM 控制台")

        with gr.Tabs():
            with gr.TabItem("控制台"):

        with gr.Row():
            # --- 左列：设备管理、配置与工具 ---
            with gr.Column(scale=1, min_width=300):
                
                # 1. 设备管理
                with gr.Group():
                    gr.Markdown("### 📱 设备管理")
                    
                    device_status = gr.Textbox(
                        label="设备状态",
                        value="❓ 未检查",
                        interactive=False,
                        lines=4
                    )
                    with gr.Row():
                        check_status_btn = gr.Button("🔄 检查", size="sm")
                        adb_devices_btn = gr.Button("📋 列表", size="sm")
                        restart_adb_btn = gr.Button("🔄 重启ADB", size="sm")

                    with gr.Accordion("📶 无线调试", open=True):
                        gr.Markdown("#### 连接无线设备")
                        with gr.Row():
                            wireless_ip = gr.Textbox(label="IP", placeholder="192.168.1.x", scale=3)
                            wireless_port = gr.Textbox(label="端口", value="5555", scale=1)
                        
                        with gr.Row():
                            connect_wireless_btn = gr.Button("🔗 连接", variant="primary", size="sm")
                            disconnect_wireless_btn = gr.Button("✂️ 断开", size="sm")

                        gr.Markdown("#### USB转无线")
                        enable_tcpip_btn = gr.Button("📡 启用TCP/IP模式", size="sm")
                        
                        wireless_status = gr.Textbox(label="状态", interactive=False, lines=2)

                # 2. 参数配置
                with gr.Group():
                    gr.Markdown("### ⚙️ 参数配置")
                    with gr.Tabs() as config_tabs:
                        with gr.TabItem("智谱AI"):
                            api_key = gr.Textbox(label="API Key", type="password", value=os.environ.get("PHONE_AGENT_API_KEY", ""))
                            model_name = gr.Textbox(label="Model", value="autoglm-phone", visible=False)
                            base_url = gr.Textbox(label="Base URL", value="https://open.bigmodel.cn/api/paas/v4", visible=False)

                        with gr.TabItem("自定义"):
                            custom_base_url = gr.Textbox(label="Base URL", value="http://localhost:11434/v1")
                            custom_model = gr.Dropdown(
                                label="Model",
                                choices=["gelab-zero-4b-preview", "autoglm-phone-9b"],
                                value="gelab-zero-4b-preview",
                                allow_custom_value=True,
                                interactive=True
                            )
                            custom_api_key = gr.Textbox(label="API Key", type="password")
                    
                    with gr.Row():
                        device_dd = gr.Dropdown(label="当前设备", choices=[], value=None, scale=3)
                        refresh_dev_btn = gr.Button("🔄", scale=1)

                # 3. 实用工具
                with gr.Group():
                    gr.Markdown("### 🛠 实用工具")
                    scrcpy_btn = gr.Button("🖥️ 启动屏幕镜像", variant="secondary")
                    scrcpy_status = gr.Textbox(label="状态", interactive=False, lines=1)
                    
                    with gr.Accordion("📲 第三方应用列表", open=False):
                        list_apps_btn = gr.Button("获取应用列表", size="sm")
                        app_list_output = gr.Textbox(label="应用列表", lines=5, interactive=False)

            # --- 右列：日志与命令 ---
            with gr.Column(scale=2, min_width=450):
                
                # 1. 实时日志 (Top)
                with gr.Group():
                    gr.Markdown("### 📋 实时日志")
                    log_output = gr.Textbox(
                        label="终端实时日志",
                        value="",
                        lines=20,
                        max_lines=30,
                        interactive=False,
                        elem_id="log-window"
                    )
                    with gr.Row():
                        copy_log_btn = gr.Button("📋 复制日志", size="sm")
                        clear_log_btn = gr.Button("🗑 清空日志", size="sm")
                    gr.HTML("""
                    <div style='margin-top: 10px; font-size: 0.8em; color: #888;'>
                    💡 日志会自动滚动到最新位置
                    </div>
                    """)

                # 2. 命令执行 (Bottom)
                with gr.Group():
                    gr.Markdown("### 🎯 命令执行")
                    
                    task_status = gr.Textbox(
                        label="任务状态",
                        value="⚪ 就绪",
                        interactive=False,
                        lines=1
                    )
                    
                    user_input = gr.Textbox(
                        label="输入指令",
                        placeholder="例如：打开微信给文件传输助手发你好...",
                        lines=4
                    )
                    
                    with gr.Row():
                        submit_btn = gr.Button("▶ 执行任务", variant="primary", scale=2)
                        stop_btn = gr.Button("⏹ 停止任务", variant="stop", scale=1)

                    with gr.Accordion("💡 命令示例", open=False):
                        gr.Markdown("""
                        - 打开美团搜索附近的火锅店
                        - 发送微信消息给张三
                        - 打开抖音搜索美食视频
                        - 设置明天早上8点的闹钟
                        - 拍照并发送给联系人
                        """)

        # --- 逻辑绑定 ---
        
        # 刷新设备
        def refresh_devices():
            devices, _ = get_adb_devices()
            # 确保设备列表不包含错误信息
            valid_devices = [d for d in devices if not d.startswith("错误") and d != "未找到设备"]
            return gr.Dropdown(choices=valid_devices, value=valid_devices[0] if valid_devices else None)
        
        refresh_dev_btn.click(refresh_devices, outputs=device_dd)
        demo.load(refresh_devices, outputs=device_dd)

        # 列出应用
        list_apps_btn.click(get_available_apps, outputs=app_list_output)

        # 启动 scrcpy
        scrcpy_btn.click(
            fn=start_scrcpy,
            outputs=[scrcpy_status]
        )

      
        # 核心：提交命令 - 修改为使用更简单的逻辑
        def submit_command(prompt, z_key, z_model, z_url, c_url, c_model, c_key, device):
            if not prompt.strip():
                return

            # 判断应该使用哪个API配置
            # 如果智谱AI的API Key有值，优先使用智谱AI，否则使用自定义配置
            if z_key and z_key.strip():
                final_url = z_url
                final_model = z_model
                final_key = z_key
                print(f"[WebUI] 使用智谱AI配置: {final_url}")
            else:
                final_url = c_url
                final_model = c_model
                final_key = c_key
                print(f"[WebUI] 使用自定义配置: {final_url}")

            # 构造命令
            # 使用 examples/run_single_task.py 而不是 main.py
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "run_single_task.py")
            cmd_list = [sys.executable, script_path]
            
            # 添加任务描述 (位置参数)
            cmd_list.append(prompt)
            
            # 添加可选参数
            if final_url: cmd_list.extend(["--base-url", final_url])
            if final_model: cmd_list.extend(["--model", final_model])
            if final_key: cmd_list.extend(["--api-key", final_key])
            if device and device != "未找到设备": 
                # 从 "📶 无线: 192.168.1.5:5555" 或 "📱 123456 - device" 提取ID
                # 简单提取: 取冒号或空格前的部分，或者依赖 get_adb_devices 的原始ID
                # 注意：Dropdown的值是通过 refresh_devices 设置的，它只包含ID
                # 再次确认 refresh_devices 的逻辑
                # The dropdown values come from refresh_devices -> get_adb_devices -> device_id only (valid_devices list)
                cmd_list.extend(["--device-id", device])

            # 启动
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            
            # 确保 examples 目录在 PYTHONPATH 中，或者脚本自己处理了
            # run_single_task.py 必须在项目根目录下运行或者能找到依赖
            # 我们在 cwd=os.getcwd() (即项目根目录, 假设 start_web_ui.py 在根目录运行)
            # start_web_ui.py 确实在根目录
            
            runner.start(cmd_list, cwd=os.getcwd(), env=env)

        # 提交动作
        submit_btn.click(
            submit_command,
            inputs=[
                user_input,
                api_key, model_name, base_url,
                custom_base_url, custom_model, custom_api_key,
                device_dd
            ]
        )
        user_input.submit(
            submit_command,
            inputs=[
                user_input,
                api_key, model_name, base_url,
                custom_base_url, custom_model, custom_api_key,
                device_dd
            ]
        )

        # 停止动作
        stop_btn.click(runner.stop, outputs=None)

        # 清除日志
        def clear_logs():
            with runner.log_lock:
                runner.logs = ""
            return ""
        
        # 检查状态
        def check_status_handler():
            try:
                # 使用新的设备获取函数
                devices, device_info = get_adb_devices()
                if device_info:
                    return device_info
                else:
                    return "❌ 未发现设备"
            except Exception as e:
                return f"❌ 错误: {e}"

        check_status_btn.click(check_status_handler, outputs=device_status)

        # 无线调试 - 连接设备
        def handle_connect_wireless(ip, port):
            success, message = connect_wireless_device(ip, port)
            if success:
                # 连接成功后刷新设备状态
                devices, device_info = get_adb_devices()
                return device_info, f"✅ {message}"
            else:
                return "", f"❌ {message}"

        connect_wireless_btn.click(
            handle_connect_wireless,
            inputs=[wireless_ip, wireless_port],
            outputs=[device_status, wireless_status]
        )

        # 无线调试 - 断开设备
        def handle_disconnect_wireless():
            # 获取当前无线设备列表
            devices, _ = get_adb_devices()
            wireless_devices = [d for d in devices if ':' in d]

            if wireless_devices:
                # 断开所有无线设备
                success, message = disconnect_wireless_device("")
                # 刷新设备状态
                devices, device_info = get_adb_devices()
                return device_info, f"✅ 已断开所有无线设备" if success else f"❌ {message}"
            else:
                return "", "ℹ️ 没有连接的无线设备"

        disconnect_wireless_btn.click(
            handle_disconnect_wireless,
            outputs=[device_status, wireless_status]
        )

        # USB转无线 - 启用TCP/IP
        def handle_enable_tcpip():
            try:
                # 获取当前USB设备
                devices, _ = get_adb_devices()
                usb_devices = [d for d in devices if ':' not in d and d != "未找到设备" and not d.startswith("错误")]

                if not usb_devices:
                    return "", "❌ 没有找到USB连接的设备"

                # 使用第一个USB设备
                usb_device = usb_devices[0]
                success, message = enable_tcpip(usb_device)

                if success:
                    return f"✅ {message}", "✅ TCP/IP已启用，现在可以无线连接了"
                else:
                    return "", f"❌ {message}"

            except Exception as e:
                return "", f"❌ 启用TCP/IP失败: {str(e)}"

        enable_tcpip_btn.click(
            handle_enable_tcpip,
            outputs=[device_status, wireless_status]
        )

        # ADB设备列表按钮
        def handle_adb_devices():
            success, message = check_adb_connection()
            # 刷新设备状态显示
            if success:
                # 只返回设备信息部分
                lines = message.split('\n')
                device_lines = []
                for line in lines:
                    if line.startswith('📱'):
                        device_lines.append(line)
                if device_lines:
                    return '\n'.join(device_lines), message
                else:
                    return "无设备连接", message
            else:
                return "检查失败", message

        adb_devices_btn.click(
            handle_adb_devices,
            outputs=[device_status, wireless_status]
        )

        # 重启ADB服务按钮
        def handle_restart_adb():
            success, message = restart_adb()
            # 刷新设备状态显示
            if success:
                lines = message.split('\n')
                device_lines = []
                for line in lines:
                    if line.startswith('📱'):
                        device_lines.append(line)
                if device_lines:
                    return '\n'.join(device_lines), message
                else:
                    return "ADB服务已重启", message
            else:
                return "重启失败", message

        restart_adb_btn.click(
            handle_restart_adb,
            outputs=[device_status, wireless_status]
        )

            # --- 可视化 Tab ---
            with gr.TabItem("📊 轨迹可视化"):
                gr.Markdown("### 任务轨迹回放")
                gr.Markdown("在下方输入 Session ID 查看任务执行详情 (Session ID 可在“控制台”的日志中找到)")
                
                # 获取 Streamlit URL，默认为 localhost:8501
                streamlit_url = os.environ.get("STREAMLIT_URL", "http://localhost:8501")
                
                # 使用 HTML iframe 嵌入 Streamlit
                # 注意：Streamlit 需要允许跨域或相同来源，通常 localhost 没问题
                gr.HTML(f"""
                    <iframe src="{streamlit_url}" width="100%" height="800px" frameborder="0"></iframe>
                """)

        # 复制日志 (JS实现)
        copy_log_btn.click(
            fn=None,
            inputs=[],
            outputs=[],
            js="""() => {
                // Gradio 6.x 中尝试多种选择器
                let el = document.querySelector('#log-window textarea');
                if (!el) {
                    el = document.querySelector('#log-window');
                }
                if (!el) {
                    el = document.querySelector('[data-testid="log-window"] textarea');
                }
                if (!el) {
                    el = document.querySelector('[data-testid="log-window"]');
                }

                if (el) {
                    let text = el.value || el.textContent || el.innerText;
                    if (text) {
                        navigator.clipboard.writeText(text).then(() => {
                            alert('日志已复制到剪贴板');
                        }).catch(err => {
                            // 降级方案：使用传统方法
                            try {
                                const textarea = document.createElement('textarea');
                                textarea.value = text;
                                document.body.appendChild(textarea);
                                textarea.select();
                                document.execCommand('copy');
                                document.body.removeChild(textarea);
                                alert('日志已复制到剪贴板');
                            } catch (fallbackErr) {
                                console.error('复制失败:', err);
                                alert('复制失败，请手动选择文本复制');
                            }
                        });
                    } else {
                        alert('没有可复制的日志内容');
                    }
                } else {
                    alert('找不到日志窗口');
                }
            }"""
        )

        clear_log_btn.click(clear_logs, outputs=log_output)

        # 实时轮询 (0.2s = 5fps)
        timer = gr.Timer(0.2)
        timer.tick(
            fn=lambda: (runner.get_logs(), runner.get_status()),
            outputs=[log_output, task_status],
            js="""(logs, status) => {
                // 简单的 JS 技巧：延迟一下确保DOM更新，然后滚动到底部
                setTimeout(() => {
                    // Gradio 6.x 中选择器可能不同
                    let el = document.querySelector('#log-window textarea');
                    if (!el) {
                        // 尝试其他可能的选择器
                        el = document.querySelector('#log-window');
                        if (!el) {
                            el = document.querySelector('[data-testid="log-window"] textarea');
                        }
                    }
                    if (el && el.scrollTop !== undefined) {
                        el.scrollTop = el.scrollHeight;
                    }
                }, 50);
                return [logs, status];
            }"""
        )

    return demo

if __name__ == "__main__":
    ui = create_ui()
    # Gradio 6.x 兼容的启动参数
    ui.launch(
        server_name="0.0.0.0",
        server_port=8870,
        show_error=True,
        # Gradio 6.x 中一些参数被移动或移除
        # theme 和 css 参数现在在 Blocks() 中指定
    )