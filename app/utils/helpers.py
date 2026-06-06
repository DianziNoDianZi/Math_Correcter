"""
通用工具函数
"""
import uuid
from datetime import datetime
from typing import Dict, Any

def generate_id() -> str:
    """生成唯一ID"""
    return str(uuid.uuid4())

def get_timestamp() -> str:
    """获取当前时间戳"""
    return datetime.now().isoformat()

def validate_student_number(student_number: str) -> bool:
    """
    验证学号格式
    
    Args:
        student_number: 学号
        
    Returns:
        是否有效
    """
    if not student_number or len(student_number) < 4:
        return False
    return student_number.isdigit()

def format_score(score: float, max_score: float = 100) -> Dict[str, Any]:
    """
    格式化分数信息
    
    Args:
        score: 得分
        max_score: 满分
        
    Returns:
        格式化后的分数信息
    """
    accuracy = (score / max_score * 100) if max_score > 0 else 0
    
    # 判断等级
    if accuracy >= 90:
        grade = 'A'
        level = '优秀'
    elif accuracy >= 80:
        grade = 'B'
        level = '良好'
    elif accuracy >= 70:
        grade = 'C'
        level = '中等'
    elif accuracy >= 60:
        grade = 'D'
        level = '及格'
    else:
        grade = 'F'
        level = '不及格'
    
    return {
        'score': score,
        'max_score': max_score,
        'accuracy': accuracy,
        'grade': grade,
        'level': level
    }

def sanitize_filename(filename: str) -> str:
    """
    清理文件名
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    import re
    # 移除非字母数字和点号的字符
    filename = re.sub(r'[^\w\s.-]', '', filename)
    # 替换空格为下划线
    filename = filename.replace(' ', '_')
    return filename
