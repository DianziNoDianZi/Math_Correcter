"""
AI 扫描服务模块
提供基于视觉模型的学号识别和答案识别功能，支持优雅降级。
"""
import os
import re
import json
import logging
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent


def _get_vision_model() -> str:
    """从 config.yaml 读取当前配置的视觉模型名称"""
    try:
        import yaml
        config_file = BASE_DIR / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get('vision_model', '')
    except Exception as e:
        logger.warning(f'读取 config.yaml 失败: {e}')
    return ''


def _is_ai_available() -> bool:
    """检查 AI 视觉模型是否可用"""
    model_name = _get_vision_model()
    if not model_name:
        return False
    try:
        import yaml
        config_file = BASE_DIR / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            models = cfg.get('models', [])
            for m in models:
                if m.get('name') == model_name:
                    return bool(m.get('api_key'))
    except Exception:
        pass
    return False


def image_to_base64_data_url(image_path: str) -> str:
    """将图片文件转为 base64 data URL"""
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    # 确定 MIME 类型
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
    mime = mime_map.get(ext, 'image/png')
    return f'data:{mime};base64,{image_data}'


def detect_student_number_ai(image_path: str, original_filename: str = '') -> str:
    """
    使用 AI 视觉模型识别学号，失败时降级为文件名提取。
    返回识别到的学号字符串，空字符串表示未识别。
    """
    # 先尝试 AI 识别
    if _is_ai_available():
        try:
            result = _call_vision_api('student_number', image_path)
            if result:
                logger.info(f'AI 识别学号成功: {result}')
                return result
        except Exception as e:
            logger.warning(f'AI 学号识别失败，降级为文件名提取: {e}')
    
    # 降级：从文件名提取
    filename = os.path.basename(original_filename or image_path)
    name_without_ext = os.path.splitext(filename)[0]
    match = re.search(r'(\d{5,})', name_without_ext)
    if match:
        return match.group(1)
    if name_without_ext.isdigit() and len(name_without_ext) >= 4:
        return name_without_ext
    return ''


def detect_answers_ai(image_path: str, questions: List[Dict]) -> Dict[int, Any]:
    """
    使用 AI 视觉模型识别答案，失败时返回空字典。
    
    Args:
        image_path: 答题卡图片路径
        questions: 题目列表 [{'number': 1, 'type': 'choice', 'correct_answer': 'A'}, ...]
    
    Returns:
        {题号: {'answer': str, 'confidence': float|None}} 的字典
    """
    if not _is_ai_available():
        return _empty_answers(questions)
    
    try:
        result = _call_vision_api('answers', image_path, questions=questions)
        if result:
            # 解析 AI 返回的 JSON 结果
            answers = _parse_answers_response(result, questions)
            if answers:
                logger.info(f'AI 识别答案成功，共 {len(answers)} 题')
                return answers
    except Exception as e:
        logger.warning(f'AI 答案识别失败，降级为空答案: {e}')
    
    return _empty_answers(questions)


def _empty_answers(questions: List[Dict]) -> Dict[int, Any]:
    """返回空答案字典（所有题目留空）"""
    return {
        q['number']: {'answer': '', 'confidence': None}
        for q in questions
        if q['type'] in ['choice', 'true_false', 'fill_blank']
    }


def _call_vision_api(task: str, image_path: str, questions: List[Dict] = None) -> Optional[str]:
    """
    调用视觉模型 API。
    
    Args:
        task: 'student_number' 或 'answers'
        image_path: 图片路径
        questions: 题目列表（仅答案识别时需要）
    
    Returns:
        AI 返回的文本内容
    """
    model_name = _get_vision_model()
    if not model_name:
        return None
    
    image_data_url = image_to_base64_data_url(image_path)
    
    if task == 'student_number':
        prompt = """请识别这张答题卡图片中填写的学生学号。
学号通常位于答题卡顶部的"学号"或"考号"栏，是一串数字。
请只返回学号数字本身，不要包含任何其他文字。
如果无法识别，请返回空字符串。"""
    elif task == 'answers':
        question_desc = '\n'.join(
            f'第{q["number"]}题（{q["type"]}）：正确答案是 {q.get("correct_answer", "?")}'
            for q in (questions or [])
        )
        prompt = f"""请识别这张答题卡图片中学生填写的答案。
题目信息如下：
{question_desc}

请以 JSON 格式返回每道题的识别结果，格式如下：
{{"answers": {{"1": "A", "2": "B"}}}}

要求：
- 选择题返回选项字母（A/B/C/D）
- 判断题返回"对"或"错"
- 填空题返回填写的文字内容
- 主观题不需要返回
- 无法识别的题目省略
只返回 JSON，不要包含任何解释文字。"""
    else:
        return None
    
    # 导入 processor 的 call_llm_api
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from processor import call_llm_api
    
    result = call_llm_api(
        model_name,
        [{"role": "user", "content": prompt}],
        image_url=image_data_url
    )
    return result


def _parse_answers_response(response: str, questions: List[Dict]) -> Dict[int, Any]:
    """解析 AI 返回的答案 JSON 字符串"""
    # 尝试提取 JSON
    json_str = response.strip()
    # 移除可能的 markdown 代码块标记
    if json_str.startswith('```'):
        lines = json_str.split('\n')
        json_str = '\n'.join(lines[1:]) if len(lines) > 1 else json_str
        if json_str.endswith('```'):
            json_str = json_str[:-3]
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # 尝试用正则提取
        match = re.search(r'\{[\s\S]*"answers"[\s\S]*\}', response)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return {}
        else:
            return {}
    
    raw_answers = data.get('answers', {})
    
    # 构建标准格式
    results = {}
    for q in questions:
        q_num = q['number']
        answer = str(raw_answers.get(str(q_num), ''))
        results[q_num] = {
            'answer': answer,
            'confidence': None
        }
    
    return results