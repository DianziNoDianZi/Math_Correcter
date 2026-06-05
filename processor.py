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
from config import get_config, get_models_dict, get_cross_platform_path
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
    "你是一位耐心且鼓励性的数学辅导老师。请对以下学生的回答进行批改纠正，先分析题目和解题流程，再考虑学生的步骤逻辑，"
    "用 Markdown 格式输出，并严格按照以下结构输出（保持标题不变）：\n\n"
    "# 📝 总体评价\n"
    "友好的开场白，给出总体评价（如：很棒！这次做得不错/继续加油，你正在进步/再仔细检查一下就更好了等）\n\n"
    "# ✅ 亮点回顾\n"
    "列出学生做得好的地方（即使全错也要找可肯定的地方，如书写清晰/思路有一定道理/尝试了多种方法等）\n\n"
    "# 🎯 批改结果\n"
    "结果：[完全正确/基本正确/部分正确/需要改进]\n"
    "得分：[估算一个合理的分数，满分100分]\n\n"
    "# ❌ 错误分析\n"
    "详细分析学生的错误，如果有错误：\n"
    "- 明确指出哪一步出错了\n"
    "- 分析错误原因（概念混淆/计算失误/粗心大意/思路偏差等）\n"
    "- 用学生容易理解的语言解释\n\n"
    "# 📚 正确解答\n"
    "给出完全正确的解答，每个数学公式都用 LaTeX 格式（$$...$$）书写，并适当加上注释说明每一步的目的\n\n"
    "# 💡 学习建议\n"
    "根据学生的错误，给出针对性的学习建议：\n"
    "- 需要重点复习的知识点\n"
    "- 具体的练习建议\n"
    "- 解题技巧或注意事项\n"
    "- 一道类似的练习题供巩固（可选）\n\n"
    "如果学生完全正确，也要给出肯定，并提供拓展建议或一道更有挑战性的题目。\n"
    "整体语气要温暖、鼓励，让学生感到被支持和理解，即使犯了错误也不气馁！\n\n"
    "学生回答内容："
)

# 逐步指导的提示词
GUIDE_HINTS_PROMPT = (
    "你是一位非常有耐心的数学辅导老师，你不会直接给出答案，而是通过引导让学生自己思考和发现解法。\n\n"
    "请根据以下题目和学生回答，生成 4 个逐步递进的提示，每个提示都用 Markdown 格式。\n\n"
    "4个提示的要求如下：\n\n"
    "1. **第1个提示（最宽泛）**：\n"
    "   - 不要直接讲解法，只引导学生思考题目考察的知识点是什么\n"
    "   - 可以问一些引导性的问题\n"
    "   - 不要给出任何计算过程\n\n"
    "2. **第2个提示（较具体）**：\n"
    "   - 给出解题思路的大致方向\n"
    "   - 说明应该先做什么，再做什么\n"
    "   - 但还是不要给出具体计算\n\n"
    "3. **第3个提示（更具体）**：\n"
    "   - 给出部分关键步骤或公式\n"
    "   - 引导学生自己完成剩余部分\n\n"
    "4. **第4个提示（接近答案）**：\n"
    "   - 给出更详细的步骤提示\n"
    "   - 但还是不要直接写出完整答案\n\n"
    "请将这4个提示用 JSON 数组格式返回，格式如下：\n"
    '["提示1内容", "提示2内容", "提示3内容", "提示4内容"]\n\n'
    "每个提示的内容都要用友好、鼓励的语气，用 Markdown 格式，适当使用表情符号。\n\n"
    "题目和学生回答如下：\n"
)

EXPLANATION_PROMPT = (
    "你是一位耐心且温暖的数学辅导老师。请基于以下批改结果，用口语化、亲切的方式生成一段语音讲解。"
    "要求：\n"
    "1. 先做一个友好的自我介绍\n"
    "2. 结合总体评价和亮点回顾，给予学生鼓励\n"
    "3. 简洁概括题目内容和批改结果\n"
    "4. 如果有错误，耐心讲解错误原因，但不要批评\n"
    "5. 详细讲解正确解法\n"
    "6. 适当提及学习建议\n"
    "7. 语速适中，方便学生理解\n"
    "8. 不要使用 LaTeX 公式，用文字描述数学表达式\n"
    "9. 总时长控制在2-4分钟的文字量\n"
    "10. 直接输出讲解内容，不要有额外格式标记\n"
    "11. 结尾一定要给予鼓励！\n"
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
    output_dir = get_cross_platform_path(tts_cfg.get('output_dir', 'outputs'))
    
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

def generate_guide_hints(query_code, custom_prompt=None, extracted_content=''):
    """生成逐步指导的4个提示"""
    cfg = _load_config()
    text_model = cfg.get('text_model', '')
    
    if not text_model:
        raise ValueError("未配置文本模型")
    
    # 使用自定义提示或默认提示
    if custom_prompt is None:
        prompt = GUIDE_HINTS_PROMPT + extracted_content
    else:
        prompt = custom_prompt + extracted_content
    
    # 生成4个提示
    hints_text = call_llm_api(
        text_model,
        [{"role": "user", "content": prompt}]
    )
    
    # 尝试解析 JSON
    try:
        # 清理一下响应
        hints_text = hints_text.strip()
        if hints_text.startswith('```json'):
            hints_text = hints_text[7:]
        if hints_text.startswith('```'):
            hints_text = hints_text[3:]
        if hints_text.endswith('```'):
            hints_text = hints_text[:-3]
        
        hints = json.loads(hints_text)
        
        # 确保是4个提示
        if not isinstance(hints, list) or len(hints) != 4:
            raise ValueError("返回格式不正确")
        
        # 保存提示
        hints_path = os.path.join(RESULTS_DIR, f"{query_code}_hints.json")
        with open(hints_path, 'w', encoding='utf-8') as f:
            json.dump(hints, f, ensure_ascii=False)
        
        return hints
    except Exception as e:
        logger.error(f"解析提示失败: {e}")
        # 如果解析失败，提供默认提示
        default_hints = [
            "💭 让我们先想一想，这道题主要考察什么知识点呢？",
            "📝 提示一下，我们可以先分析题目给出的条件，再思考需要用到什么公式或定理。",
            "🔍 再仔细看看，尝试写下第一步的计算过程，你可以的！",
            "💪 加油！如果还是有困难，可以查看完整解答，然后再自己做一遍哦！"
        ]
        hints_path = os.path.join(RESULTS_DIR, f"{query_code}_hints.json")
        with open(hints_path, 'w', encoding='utf-8') as f:
            json.dump(default_hints, f, ensure_ascii=False)
        return default_hints

def get_hints(query_code):
    """获取已生成的提示"""
    hints_path = os.path.join(RESULTS_DIR, f"{query_code}_hints.json")
    if os.path.exists(hints_path):
        with open(hints_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def extract_knowledge_points(query_code, extracted_content, grade_description):
    """提取知识点并生成知识点图谱数据"""
    cfg = _load_config()
    text_model = cfg.get('text_model', '')
    
    if not text_model:
        logger.warning("未配置文本模型，跳过知识点提取")
        return None
    
    # 知识点提取提示
    knowledge_prompt = (
        f"作为一位{grade_description}数学老师，请分析以下题目和学生回答，提取涉及的知识点。\n\n"
        "请用JSON数组格式返回知识点列表，每个知识点包含：\n"
        "- name: 知识点名称\n"
        "- type: 知识点类型（基础/核心/拓展）\n"
        "- mastered: 是否已掌握（基于学生回答判断）\n\n"
        "示例格式：\n"
        '[\n'
        '  {"name": "一元二次方程", "type": "核心", "mastered": false},\n'
        '  {"name": "配方法", "type": "基础", "mastered": true}\n'
        ']\n\n'
        "题目和学生回答如下：\n"
        f"{extracted_content}\n\n"
        "请只返回JSON数组，不要有其他内容。"
    )
    
    try:
        knowledge_text = call_llm_api(
            text_model,
            [{"role": "user", "content": knowledge_prompt}]
        )
        
        # 清理和解析
        knowledge_text = knowledge_text.strip()
        if knowledge_text.startswith('```json'):
            knowledge_text = knowledge_text[7:]
        if knowledge_text.startswith('```'):
            knowledge_text = knowledge_text[3:]
        if knowledge_text.endswith('```'):
            knowledge_text = knowledge_text[:-3]
        
        knowledge_points = json.loads(knowledge_text)
        
        # 保存知识点
        knowledge_path = os.path.join(RESULTS_DIR, f"{query_code}_knowledge.json")
        with open(knowledge_path, 'w', encoding='utf-8') as f:
            json.dump({
                'grade': grade_description,
                'knowledge_points': knowledge_points,
                'total': len(knowledge_points),
                'mastered': sum(1 for k in knowledge_points if k.get('mastered', False)),
                'not_mastered': sum(1 for k in knowledge_points if not k.get('mastered', True))
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"知识点提取完成: {len(knowledge_points)} 个知识点")
        return knowledge_points
    except Exception as e:
        logger.error(f"知识点提取失败: {e}")
        return None

def get_knowledge_points(query_code):
    """获取已提取的知识点"""
    knowledge_path = os.path.join(RESULTS_DIR, f"{query_code}_knowledge.json")
    if os.path.exists(knowledge_path):
        with open(knowledge_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def process_task(task_file_path, query_code, mode='quick', grade='10-12'):
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
            cancelled_path = os.path.join(CANCELLED_DIR, os.path.basename(processing_path))
            os.rename(processing_path, cancelled_path)
            processing_path = None
            return

        logger.info(f"开始处理任务 {query_code}，模式: {mode}，年级: {grade}")

        # 读取并编码图片
        with open(processing_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode('utf-8')
        image_data_url = f"data:image/png;base64,{base64_image}"

        cfg = _load_config()
        vision_model = cfg.get('vision_model', '')
        text_model = cfg.get('text_model', '')

        # 根据年级获取描述
        grade_description = {
            '1-2': '小学1-2年级',
            '3-4': '小学3-4年级', 
            '5-6': '小学5-6年级',
            '7-9': '初中',
            '10-12': '高中'
        }.get(grade, '高中')

        # 第一阶段：视觉模型提取题目/答案
        first_response = call_llm_api(vision_model, [{"role": "user", "content": FIRST_PROMPT}], image_url=image_data_url)
        
        # 保存提取的内容
        extracted_path = os.path.join(RESULTS_DIR, f"{query_code}_extracted.txt")
        with open(extracted_path, 'w', encoding='utf-8') as f:
            f.write(first_response)

        if mode == 'guided':
            # 逐步指导模式
            try:
                # 根据年级调整提示
                guided_prompt = GUIDE_HINTS_PROMPT.replace(
                    "请根据以下题目和学生回答",
                    f"学生所在年级是{grade_description}，请根据{grade_description}学生的认知水平，请根据以下题目和学生回答"
                )
                generate_guide_hints(query_code, guided_prompt, first_response)
            except Exception as e:
                logger.error(f"生成指导提示失败: {e}")
            
            # 生成完整批改结果
            combined_text = SECOND_PROMPT.replace(
                "你是一位耐心且鼓励性的数学辅导老师",
                f"你是一位专门教{grade_description}学生的耐心且鼓励性的数学辅导老师"
            ) + first_response
            final_result = call_llm_api(text_model, [{"role": "user", "content": combined_text}])
            
            result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
            if not os.path.exists(cancel_marker):
                with open(result_path, 'w', encoding='utf-8') as f:
                    f.write(final_result)
        else:
            # 快速批改模式
            combined_text = SECOND_PROMPT.replace(
                "你是一位耐心且鼓励性的数学辅导老师",
                f"你是一位专门教{grade_description}学生的耐心且鼓励性的数学辅导老师"
            ) + first_response
            final_result = call_llm_api(text_model, [{"role": "user", "content": combined_text}])
            
            result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
            if not os.path.exists(cancel_marker):
                with open(result_path, 'w', encoding='utf-8') as f:
                    f.write(final_result)

        # 提取知识点
        try:
            extract_knowledge_points(query_code, first_response, grade_description)
        except Exception as e:
            logger.error(f"提取知识点失败: {e}")

        logger.info(f"任务 {query_code} 处理完成")

        if os.path.exists(cancel_marker):
            if os.path.exists(result_path):
                os.remove(result_path)
            cancelled_path = os.path.join(CANCELLED_DIR, os.path.basename(processing_path))
            os.rename(processing_path, cancelled_path)
            processing_path = None

    except Exception as e:
        logger.error(f"处理任务 {query_code} 时发生错误: {e}")
        error_result_path = os.path.join(RESULTS_DIR, f"{query_code}.txt")
        with open(error_result_path, 'w', encoding='utf-8') as f:
            f.write(f"处理过程中发生错误: {str(e)}")
    finally:
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
                if os.path.isfile(fullpath) and not filename.endswith('_mode.txt') and not filename.endswith('_grade.txt'):
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
                        
                        # 读取模式和年级信息
                        mode = 'quick'
                        grade = '10-12'
                        
                        mode_file = os.path.join(PENDING_DIR, f"{code}_mode.txt")
                        if os.path.exists(mode_file):
                            try:
                                with open(mode_file, 'r', encoding='utf-8') as f:
                                    mode = f.read().strip()
                                os.rename(mode_file, os.path.join(PROCESSING_DIR, f"{code}_mode.txt"))
                            except Exception:
                                pass
                        
                        grade_file = os.path.join(PENDING_DIR, f"{code}_grade.txt")
                        if os.path.exists(grade_file):
                            try:
                                with open(grade_file, 'r', encoding='utf-8') as f:
                                    grade = f.read().strip()
                                os.rename(grade_file, os.path.join(PROCESSING_DIR, f"{code}_grade.txt"))
                            except Exception:
                                pass
                        
                        executor.submit(process_task, processing_path, code, mode, grade)
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
