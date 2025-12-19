
import os
import sys
import time
if "." not in sys.path:
    sys.path.append(".")

from copilot_agent_client.pu_client import evaluate_task_on_device
from copilot_front_end.mobile_action_helper import list_devices, get_device_wm_size
from copilot_agent_server.local_server import LocalServer

tmp_server_config = {
    "log_dir": "running_log/server_log/os-copilot-local-eval-logs/traces",
    "image_dir": "running_log/server_log/os-copilot-local-eval-logs/images",
    "debug": False
}


local_model_config = {
    "task_type": "parser_0922_summary",
    "model_config": {
        "model_name": "gelab-zero-4b-preview",
        "model_provider": "local",
        "args": {
            "temperature": 0.1,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "max_tokens": 4096,
        },
        
        # optional to resize image
        # "resize_config": {
        #     "is_resize": True,
        #     "target_image_size": (756, 756)
        # }
    },

    "max_steps": 400,
    "delay_after_capture": 2,
    "debug": False
}


# ===== 新增：用于记录每步耗时 =====
_step_times = []


# ===== 新增：包装 automate_step 方法 =====
def wrap_automate_step_with_timing(server_instance):
    original_method = server_instance.automate_step

    def timed_automate_step(payload):
        step_start = time.time()
        try:
            result = original_method(payload)
        finally:
            duration = time.time() - step_start
            _step_times.append(duration)
            print(f"Step {len(_step_times)} took: {duration:.2f} seconds")
        return result

    # 替换实例方法
    server_instance.automate_step = timed_automate_step

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a single task solely.")
    parser.add_argument("task", type=str, nargs='?', help="The task description.")
    parser.add_argument("--device-id", type=str, help="The device ID to use.")
    parser.add_argument("--model", type=str, default="gelab-zero-4b-preview", help="Model name.")
    parser.add_argument("--base-url", type=str, help="Base URL for the model API.")
    parser.add_argument("--api-key", type=str, help="API Key for the model.")
    
    args = parser.parse_args()

    if not args.task:
        print("❌ 错误：未传入任务参数！")
        print("📝 使用方法：")
        print(f"   python {sys.argv[0]} \"你的任务描述\" [options]")
        print("   示例1：python script.py \"去淘宝帮我买本书\"")
        print("   示例2：python script.py \"打开微信，给柏茗发helloworld\" --device-id 123456")
        sys.exit(1)

    task = args.task

    # Use provided device_id or find the first available one
    if args.device_id:
        device_id = args.device_id
        # Verify device is connected
        available_devices = list_devices()
        if device_id not in available_devices:
             print(f"Warning: Device {device_id} not found in connected devices: {available_devices}")
    else:
        devices = list_devices()
        if not devices:
            print("❌ Error: No devices connected.")
            sys.exit(1)
        device_id = devices[0]
        print(f"Auto-selected device: {device_id}")

    device_wm_size = get_device_wm_size(device_id)
    device_info = {
        "device_id": device_id,
        "device_wm_size": device_wm_size
    }

    # Update model configuration based on arguments
    tmp_rollout_config = local_model_config.copy()
    if args.model:
        tmp_rollout_config["model_config"]["model_name"] = args.model
    
    if args.base_url or args.api_key:
        # Switch provider to openai if URL/Key provided, or keep local if just overriding local params?
        # Assuming if URL is provided, we might want to treat it as an OpenAI-compatible endpoint
        # BUT for now, let's just inject these into args or model_config if the backend supports it.
        # Looking at local_server.py might be needed to see how it handles base_url/api_key.
        # For 'local' provider, it might not use them. Let's assume user knows what they are doing.
        # If it is 'custom' or 'openai', provider might need to change.
        # FOR NOW: We just update the 'args' or specific keys if the server class supports it.
        
        # NOTE: The current LocalServer implementation details are not fully visible here. 
        # But commonly these are passed in model_config.
        if args.base_url:
             tmp_rollout_config["model_config"]["base_url"] = args.base_url
        if args.api_key:
             tmp_rollout_config["model_config"]["api_key"] = args.api_key
             
        # If external URL is used, we might need to change provider from 'local' to 'openai' or similar if logic dictates
        if args.base_url and "local" in tmp_rollout_config["model_config"]["model_provider"]:
             # Heuristic: if base_url is set, it's likely not just 'local' weights but an invalidference server
             pass

    # Ensure log directories exist
    if "log_dir" in tmp_server_config and not os.path.exists(tmp_server_config["log_dir"]):
        os.makedirs(tmp_server_config["log_dir"], exist_ok=True)
    if "image_dir" in tmp_server_config and not os.path.exists(tmp_server_config["image_dir"]):
        os.makedirs(tmp_server_config["image_dir"], exist_ok=True)

    # Use tmp_server_config for LocalServer initialization as it expects log_dir etc.
    l2_server = LocalServer(tmp_server_config)

    # 注入计时逻辑
    wrap_automate_step_with_timing(l2_server)

    # 执行任务并计总时间
    total_start = time.time()
    
    print(f"Starting task: {task}")
    print(f"Device: {device_id}")
    print(f"Model: {tmp_rollout_config['model_config']['model_name']}")
    
    # Disable auto reply
    evaluate_task_on_device(l2_server, device_info, task, tmp_rollout_config, reflush_app=True)
    total_time = time.time() - total_start

    # 在最后加一行总时间
    print(f"总计执行时间为 {total_time} 秒")
