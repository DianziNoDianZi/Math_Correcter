"""
AI 分析服务模块
提供基于文本 LLM 的考试深度分析和班级学情分析功能，支持结果缓存和优雅降级。
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent

# AI 分析缓存目录
CACHE_DIR = BASE_DIR / 'data' / 'ai_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_text_model() -> str:
    """从 config.yaml 读取当前配置的文本模型名称"""
    try:
        import yaml
        config_file = BASE_DIR / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get('text_model', '')
    except Exception as e:
        logger.warning(f'读取 config.yaml 失败: {e}')
    return ''


def _is_ai_available() -> bool:
    """检查 AI 文本模型是否可用"""
    model_name = _get_text_model()
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


def _get_cache(entity_id: str, entity_type: str) -> Optional[str]:
    """获取缓存的分析结果"""
    cache_file = CACHE_DIR / f'{entity_type}_{entity_id}.txt'
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('report')
        except Exception as e:
            logger.warning(f'读取缓存失败: {e}')
            return None
    return None


def _set_cache(entity_id: str, entity_type: str, report: str) -> None:
    """保存分析结果到缓存"""
    cache_file = CACHE_DIR / f'{entity_type}_{entity_id}.txt'
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'entity_id': entity_id,
                'entity_type': entity_type,
                'report': report,
                'generated_at': None
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f'写入缓存失败: {e}')


def _invalidate_cache(entity_id: str, entity_type: str) -> None:
    """清除缓存（数据变更时调用）"""
    cache_file = CACHE_DIR / f'{entity_type}_{entity_id}.txt'
    if cache_file.exists():
        try:
            os.remove(cache_file)
            logger.info(f'已清除 {entity_type} {entity_id} 的 AI 分析缓存')
        except Exception as e:
            logger.warning(f'清除缓存失败: {e}')


def _call_text_api(prompt: str) -> Optional[str]:
    """调用文本 LLM API"""
    model_name = _get_text_model()
    if not model_name:
        return None

    # 导入 processor 的 call_llm_api
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from processor import call_llm_api

    try:
        result = call_llm_api(
            model_name,
            [{"role": "user", "content": prompt}]
        )
        return result.strip() if result else None
    except Exception as e:
        logger.error(f'AI 调用失败: {e}')
        return None


def generate_exam_analysis(exam_data: Dict[str, Any]) -> Optional[str]:
    """
    根据考试数据生成 AI 分析报告。

    Args:
        exam_data: 考试完整数据，包含 statistics, question_stats, knowledge_stats

    Returns:
        Markdown 格式的分析报告，AI 不可用或失败时返回 None
    """
    # 检查是否有成绩数据
    scores = exam_data.get('exam', {}).get('scores', [])
    if not scores:
        return None

    # 检查 AI 是否可用
    if not _is_ai_available():
        return None

    # 检查缓存
    exam_id = exam_data.get('exam', {}).get('id', '')
    cached = _get_cache(exam_id, 'exam')
    if cached is not None:
        logger.info(f'使用缓存的考试分析: {exam_id}')
        return cached

    # 构建统计信息摘要
    stats = exam_data.get('statistics', {})
    question_stats = exam_data.get('question_stats', [])
    knowledge_stats = exam_data.get('knowledge_stats', {})

    # 找出错误率高的题目（错误率 > 50%）
    high_error_questions = [
        q for q in question_stats
        if q.get('error_rate', 0) > 50
    ]

    # 找出掌握率低的知识点（掌握率 < 50%）
    low_mastery_knowledge = []
    for kp, data in knowledge_stats.items():
        mastery = data.get('mastery_rate', 0)
        if mastery < 50:
            low_mastery_knowledge.append((kp, mastery))

    # 构建 prompt
    prompt = f"""作为一位经验丰富的中学数学教师，请根据以下考试统计数据，生成一份结构化的学情分析报告。

## 基本信息
考试名称：{exam_data.get('exam', {}).get('name', '未命名考试')}
班级：{exam_data.get('exam', {}).get('class_id', '未知班级')}
参与学生：{stats.get('total_scores', 0)} 人
平均分：{stats.get('average_score', 0):.1f}
及格率：{stats.get('pass_rate', 0):.1f}%
最高分：{stats.get('highest_score', 0)}
最低分：{stats.get('lowest_score', 0)}

## 错题统计（错误率 > 50%）
"""

    if high_error_questions:
        for q in high_error_questions:
            prompt += f"- 第{q['number']}题：错误率 {q['error_rate']:.1f}%\n"
    else:
        prompt += "- 没有错误率超过50%的题目，整体掌握良好\n"

    prompt += f"""
## 薄弱知识点（掌握率 < 50%）
"""

    if low_mastery_knowledge:
        for kp, mastery in low_mastery_knowledge:
            prompt += f"- {kp}：掌握率 {mastery:.1f}%\n"
    else:
        prompt += "- 所有知识点掌握率均超过50%，整体掌握良好\n"

    prompt += """
请按照以下结构输出分析报告，使用 Markdown 格式：

# 📊 AI 考试分析报告

## 总体评价
一句话总结这次考试的整体表现。

## 高频错误分析
分析错误率较高的题目，指出学生普遍存在的问题。

## 薄弱知识点诊断
列出掌握不佳的知识点，分析可能的原因。

## 教学改进建议
给出具体、可操作的下一步教学建议，包括：
1. 需要重点巩固的内容
2. 建议的练习方式
3. 是否需要调整教学节奏

注意：语言要专业但易懂，面向教师读者，控制在 300-500 字。只输出报告内容，不要有其他解释。
"""

    # 调用 AI
    report = _call_text_api(prompt)
    if report:
        _set_cache(exam_id, 'exam', report)
        logger.info(f'AI 考试分析生成完成: {exam_id}')
        return report

    return None


def generate_class_report(class_data: Dict[str, Any]) -> Optional[str]:
    """
    根据班级数据生成 AI 学情分析报告。

    Args:
        class_data: 班级数据分析结果，包含 statistics 和各次考试信息

    Returns:
        Markdown 格式的班级学情报告，AI 不可用或失败时返回 None
    """
    # 检查是否有数据
    if not class_data.get('success'):
        return None

    stats = class_data.get('statistics', {})
    if not stats:
        return None

    # 检查 AI 是否可用
    if not _is_ai_available():
        return None

    # 检查缓存
    class_id = class_data.get('class_id', '')
    cached = _get_cache(class_id, 'class')
    if cached is not None:
        logger.info(f'使用缓存的班级分析: {class_id}')
        return cached

    # 构建 prompt
    prompt = f"""作为一位经验丰富的中学数学班主任，请根据以下班级学情统计数据，生成一份结构化的班级学情分析报告。

## 基本信息
班级名称：{class_data.get('class_name', '未命名班级')}
总学生数：{class_data.get('total_students', 0)} 人
最近一次考试参与：{class_data.get('participated', 0)} 人
平均分：{stats.get('average_score', 0):.1f}
平均分率：{stats.get('average_percentage', 0):.1f}%
及格率：{stats.get('pass_rate', 0):.1f}%
最高分：{stats.get('highest_score', 0)}
最低分：{stats.get('lowest_score', 0)}

请按照以下结构输出分析报告，使用 Markdown 格式：

# 📋 AI 班级学情分析

## 整体水平评估
评估班级当前的整体学习水平，分析分数分布特点。

## 共性问题分析
根据统计数据指出班级普遍存在的问题。

## 分层教学建议
分别针对：
- 优等生：如何进一步提升
- 中等生：如何突破瓶颈
- 后进生：如何夯实基础

## 下一阶段教学重点
给出具体的教学重点和改进方向。

注意：语言要专业但易懂，面向教师读者，控制在 300-500 字。只输出报告内容，不要有其他解释。
"""

    # 调用 AI
    report = _call_text_api(prompt)
    if report:
        _set_cache(class_id, 'class', report)
        logger.info(f'AI 班级分析生成完成: {class_id}')
        return report

    return None


def invalidate_exam_cache(exam_id: str) -> None:
    """清除考试的 AI 分析缓存（成绩变更时调用）"""
    _invalidate_cache(exam_id, 'exam')


def invalidate_class_cache(class_id: str) -> None:
    """清除班级的 AI 分析缓存（考试数据变更时调用）"""
    _invalidate_cache(class_id, 'class')
