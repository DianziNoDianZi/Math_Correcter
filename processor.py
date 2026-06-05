# -*- coding: utf-8 -*-
"""处理逻辑：将图片任务分两步走，通过视觉模型提取题目/学生答案，再用文本模型批改。"""

import base64
import json
import logging
import os
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
import requests
from config import get_config, get_models_dict
from config import UPLOAD_FOLDER, PENDING_DIR, PROCESSING_DIR, RESULTS_DIR, PAUSE_FLAG_PATH, CANCELLED_DIR
from datetime import datetime
import shutil
_start_time = datetime.utcnow()

logger = logging.getLogger(__name__)

# 确保目录存在
os.makedirs(PENDING_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CANCELLED_DIR, exist_ok=True)

# Prompts
FIRST_PROMPT = (
    "请从这张图片中提取题目和学生的回答，保留原始符号和格式，并用简洁的语言总结。"
    "如果涉及数学公式，请用 LaTeX 格式表示，同时不对答案的正确性进行评判。"
)

SECOND_PROMPT = (
    "你是一位严谨的数学老师。请对以下学生的回答进行批改纠正，先分析题目和解题流程，再考虑学生的步骤逻辑，你的每一个数学公式都会换行，考虑学生的阅读方便和想法，并严格按照以下格式输出（保持标题不变）：\n\n"
    "批改结果：[正确/部分正确/错误]\n\n"
    "错误分析：[请详细分析学生的错误，指出错误原因，用中文]\n\n"
    "正确解答：[请给出完全正确的解答，所有数学公式必须用LaTeX格式（$$...$$）书写]\n\n"
    "学生回答内容："
)

EXPLANATION_PROMPT = (
    "你是一位耐心的数学老师。请基于以下批改结果，用口语化、亲切的方式生成一段语音讲解。"
    "要求：\n"
    "1. 先自我介绍，说是语音讲解\n"
    "2. 简洁概括题目内容\n"
    "3. 指出学生的对错情况\n"
    "4. 详细讲解正确解法\n"
    "5. 语速适中，方便学生理解\n"
    "6. 不要使用 LaTeX 公式，用文字描述数学表达式\n"
    "7. 总时长控制在2-3分钟的文字量\n"
    "8. 直接输出讲解内容，不要有额外格式标记\n"
    "批改结果如下："
)

def _load_config():
    cfg = get_config()
    return cfg

def pause_processing():
    with open(PAUSE_FLAG_PATH, 'w') as f:
        f.write('1')

def resume_processing():
    if os.path.exists(PAUSE_FLAG_PATH):
        os.remove(PAUSE_FLAG_PATH)

def is_paused():
    return os.path.exists(PAUSE_FLAG_PATH)

def cancel_task(query_code):
    # Cancel pending tasks first
    for fname in os.listdir(PENDING_DIR):
        try:
            _, code = _parse_pending_filename(fname)
        except Exception:
            code = fname.split('.', 1)[0]
        if code == query_code:
            src = os.path.join(PENDING_DIR, fname)
            dst = os.path.join(CANCELLED_DIR, fname)
            try:
                os.rename(src, dst)
            except FileNotFoundError:
                pass
            break
    # Mark as cancelled for any running task
    cancel_marker = os.path.join(CANCELLED_DIR, f"{query_code}.cancel")
    try:
        with open(cancel_marker, 'w') as f:
            f.write('cancel')
    except Exception:
        pass

def _parse_pending_filename(filename):
    base = os.path.basename(filename)
    if '_' in base:
        pref, rest = base.split('_', 1)
        if pref.isdigit():
            priority = int(pref)
            code = rest.split('.', 1)[0]
            return priority, code
    code = base.split('.', 1)[0]
    return 99999999, code

def call_llm_api(model_name, messages, image_url=None):
    """调用 LLM API 的通用函数，读取模型配置并发送请求"""
    models = get_models_dict()
    model_info = models.get(model_name)
    if not model_info:
        raise ValueError(f"Model {model_name} not found in config.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model_info['api_key']}"
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": model_info.get('default_temperature', 0.7),
        "max_tokens": 4096
    }

    # 如果是多模态模型且提供了图片URL，则构建包含图片的消息
    if image_url:
        new_messages = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                new_content = [
                    {"type": "text", "text": content},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            else:
                new_content = content
            new_msg = msg.copy()
            new_msg["content"] = new_content
            new_messages.append(new_msg)
        payload["messages"] = new_messages

    response = requests.post(
        f"{model_info['api_base'].rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=model_info.get('timeout', 60)
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def call_tts_api(text, query_code):
    """调用 TTS API 生成语音"""
    cfg = _load_config()
    tts_cfg = cfg.get('tts', {})
    
    if not tts_cfg.get('enabled', False):
        raise ValueError("TTS 功能未启用")
    
    engine = tts_cfg.get('engine', 'qwen-tts')
    api_base = tts_cfg.get('api_base', 'http://127.0.0.1:7860')
    voice = tts_cfg.get('voice', 'default')
    speed = tts_cfg.get('speed', 1.0)
    model_name = tts_cfg.get('model_name', 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice')
    output_dir = tts_cfg.get('output_dir', 'D:\\qwen-tts-webui\\core\\outputs')
    
    output_path = os.path.join(RESULTS_DIR, f"{query_code}_audio.wav")
    
    if engine == 'qwen-tts':
        try:
            from gradio_client import Client
            
            client = Client(api_base)
            
            before_files = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()
            
            if 'CustomVoice' in model_name:
                result = client.predict(
                    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                    text,
                    voice,
                    "default",
                    "auto",
                    False,
                    api_name="/generate_voice_fn"
                )
            elif 'VoiceDesign' in model_name:
                result = client.predict(
                    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                    text,
                    voice,
                    "auto",
                    False,
                    api_name="/generate_design_fn"
                )
            else:
                raise ValueError(f"不支持的模型: {model_name}")
            
            print(f"TTS API result: {result}")
            
            import time
            time.sleep(8)
            
            after_files = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()
            new_files = after_files - before_files
            
            if not new_files:
                raise ValueError(f"未检测到新生成的音频文件，输出目录: {output_dir}")
            
            latest_file = sorted(new_files)[-1]
            src_audio = os.path.join(output_dir, latest_file)
            
            if os.path.exists(src_audio):
                shutil.copy(src_audio, output_path)
            else:
                raise ValueError(f"源音频文件不存在: {src_audio}")
                
        except Exception as e:
            raise ValueError(f"TTS 调用失败: {str(e)}")
    
    elif engine == 'gpt-sovits':
        refer_wav = tts_cfg.get('refer_wav', '')
        prompt_text = tts_cfg.get('prompt_text', '')
        prompt_language = tts_cfg.get('prompt_language', 'zh')
        sovits_model = tts_cfg.get('sovits_model', '')
        gpt_model = tts_cfg.get('gpt_model', '')
        
        if not refer_wav:
            raise ValueError("GPT-SoVITS 未配置参考音频路径")
        
        try:
            from gradio_client import Client, handle_file
            
            client = Client(api_base)
            
            if sovits_model:
                client.predict(
                    sovits_path=sovits_model,
                    prompt_language=prompt_language,
                    text_language=prompt_language,
                    api_name="/change_sovits_weights"
                )
            
            if gpt_model:
                client.predict(
                    weights_path=gpt_model,
                    api_name="/init_t2s_weights"
                )
            
            before_files = set(os.listdir(RESULTS_DIR)) if os.path.exists(RESULTS_DIR) else set()
            
            result = client.predict(
                text,
                prompt_language,
                handle_file(refer_wav),
                [],
                prompt_text,
                prompt_language,
                5,
                1,
                1,
                "按标点符号切",
                20,
                speed,
                False if prompt_text else True,
                True,
                0.3,
                -1,
                True,
                True,
                1.35,
                32,
                False,
                api_name="/inference"
)
            
            print(f"TTS result: {result}")
            print(f"TTS result type: {type(result)}")
            
            import time
            time.sleep(3)
            
            if isinstance(result, (list, tuple)) and len(result) > 0:
                audio_file = result[0]
                if audio_file and os.path.exists(audio_file):
                    shutil.copy(audio_file, output_path)
                else:
                    raise ValueError(f"音频文件路径无效: {audio_file}")
            else:
                raise ValueError(f"未检测到生成的音频文件，返回: {result}")
            
        except Exception as e:
            raise ValueError(f"TTS 调用失败: {str(e)}")
    
    else:
        raise ValueError(f"不支持的 TTS 引擎: {engine}")
    
    return output_path

def generate_explanation(query_code):
    """生成语音讲解文字并合成语音"""
    result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
    audio_path = os.path.join(RESULTS_DIR, f"{query_code}_audio.wav")
    
    if not os.path.exists(result_path):
        raise ValueError(f"结果文件不存在: {query_code}")
    
    with open(result_path, 'r', encoding='utf-8') as f:
        grading_result = f.read()
    
    cfg = _load_config()
    text_model = cfg.get('text_model', '')
    
    if not text_model:
        raise ValueError("未配置文本模型")
    
    explanation_text = call_llm_api(
        text_model,
        [{"role": "user", "content": EXPLANATION_PROMPT + grading_result}]
    )
    
    audio_path = call_tts_api(explanation_text, query_code)
    
    explanation_path = os.path.join(RESULTS_DIR, f"{query_code}_explanation.txt")
    with open(explanation_path, 'w', encoding='utf-8') as f:
        f.write(explanation_text)
    
    return audio_path, explanation_text

def process_task(task_file_path, query_code):
    processing_path = task_file_path
    try:
        # 检查文件是否已在 processing 目录
        if not task_file_path.startswith(PROCESSING_DIR):
            processing_path = os.path.join(PROCESSING_DIR, os.path.basename(task_file_path))
            try:
                os.rename(task_file_path, processing_path)
            except FileNotFoundError:
                pass

        # 取消前置检查
        cancel_marker = os.path.join(CANCELLED_DIR, f"{query_code}.cancel")
        if os.path.exists(cancel_marker):
            logger.info(f"任务 {query_code} 已取消（启动前标记），跳过处理。")
            # 将文件移到 cancelled 目录
            cancelled_path = os.path.join(CANCELLED_DIR, os.path.basename(processing_path))
            os.rename(processing_path, cancelled_path)
            processing_path = None  # 标记已移动，避免 finally 重复删除
            return

        logger.info(f"开始处理任务 {query_code}")

        # 读取并编码图片
        with open(processing_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode('utf-8')
        image_data_url = f"data:image/png;base64,{base64_image}"

        cfg = _load_config()
        vision_model = cfg.get('vision_model', '')
        text_model = cfg.get('text_model', '')

        # 第一阶段：视觉模型提取题目/答案
        first_response = call_llm_api(vision_model, [{"role": "user", "content": FIRST_PROMPT}], image_url=image_data_url)

        # 第二阶段：文本模型批改
        combined_text = SECOND_PROMPT + first_response
        final_result = call_llm_api(text_model, [{"role": "user", "content": combined_text}])

        # 保存最终结果
        result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
        if os.path.exists(cancel_marker):
            logger.info(f"任务 {query_code} 在完成前被取消，放弃结果写入。")
        else:
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write(final_result)

        logger.info(f"任务 {query_code} 处理完成")

        # 若处理完成后发现取消标记，清理结果并移动文件
        if os.path.exists(cancel_marker):
            if os.path.exists(result_path):
                os.remove(result_path)
            cancelled_path = os.path.join(CANCELLED_DIR, os.path.basename(processing_path))
            os.rename(processing_path, cancelled_path)
            processing_path = None  # 标记已移动

    except Exception as e:
        logger.error(f"处理任务 {query_code} 时发生错误: {e}")
        error_result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
        with open(error_result_path, 'w', encoding='utf-8') as f:
            f.write(f"处理过程中发生错误: {str(e)}")
    finally:
        # 清理 processing 目录中的原文件（仅当未被移动时）
        if processing_path and os.path.exists(processing_path):
            try:
                os.remove(processing_path)
                logger.debug(f"已删除 processing 文件: {processing_path}")
            except Exception as e:
                logger.warning(f"删除 processing 文件失败: {e}")

# 简单的后台扫描器，外部通过 start_scanner 启动
_executor = None

def _scan_loop(executor):
    while True:
        try:
            if is_paused():
                time.sleep(2)
                continue
            pending_list = []
            for filename in os.listdir(PENDING_DIR):
                fullpath = os.path.join(PENDING_DIR, filename)
                if os.path.isfile(fullpath):
                    try:
                        priority, code = _parse_pending_filename(filename)
                    except Exception:
                        code = filename.split('.', 1)[0]
                        priority = 99999999
                    pending_list.append((priority, code, fullpath, filename))
            pending_list.sort(key=lambda x: (x[0], x[1]))
            for priority, code, fullpath, filename in pending_list:
                if is_paused():
                    break
                processing_path = os.path.join(PROCESSING_DIR, filename)
                try:
                    if os.path.exists(fullpath):
                        os.rename(fullpath, processing_path)
                        executor.submit(process_task, processing_path, code)
                except FileExistsError:
                    pass
                except FileNotFoundError:
                    pass
        except Exception as e:
            logger.error(f"扫描 Pending 目录时出错: {e}")
        time.sleep(2)

def start_scanner(executor_instance):
    global _executor
    _executor = executor_instance
    t = threading.Thread(target=lambda: _scan_loop(executor_instance), daemon=True)
    t.start()
