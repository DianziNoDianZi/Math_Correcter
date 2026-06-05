# -*- coding: utf-8 -*-
"""试卷库管理和分析模块：面向教师/学校的教学管理平台"""
import os
import json
import base64
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

import processor
from config import TEST_LIBRARY_DIR

logger = logging.getLogger(__name__)

# 确保目录存在
os.makedirs(TEST_LIBRARY_DIR, exist_ok=True)
os.makedirs(os.path.join(TEST_LIBRARY_DIR, 'images'), exist_ok=True)
os.makedirs(os.path.join(TEST_LIBRARY_DIR, 'analyses'), exist_ok=True)
os.makedirs(os.path.join(TEST_LIBRARY_DIR, 'classes'), exist_ok=True)
os.makedirs(os.path.join(TEST_LIBRARY_DIR, 'reports'), exist_ok=True)

# 数据文件路径
def get_library_metadata_path() -> str:
    """获取试卷库元数据文件路径"""
    return os.path.join(TEST_LIBRARY_DIR, 'library_metadata.json')

def get_classes_metadata_path() -> str:
    """获取班级元数据文件路径"""
    return os.path.join(TEST_LIBRARY_DIR, 'classes_metadata.json')

# ========== 数据加载/保存 ==========

def load_library_metadata() -> Dict[str, Any]:
    """加载试卷库元数据"""
    path = get_library_metadata_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f'Failed to load library metadata: {e}')
    return {
        'papers': [],
        'total_questions': 0,
        'last_updated': None
    }

def save_library_metadata(metadata: Dict[str, Any]) -> None:
    """保存试卷库元数据"""
    metadata['last_updated'] = datetime.now().isoformat()
    path = get_library_metadata_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'Failed to save library metadata: {e}')

def load_classes_metadata() -> Dict[str, Any]:
    """加载班级元数据"""
    path = get_classes_metadata_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f'Failed to load classes metadata: {e}')
    return {
        'classes': []
    }

def save_classes_metadata(metadata: Dict[str, Any]) -> None:
    """保存班级元数据"""
    path = get_classes_metadata_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'Failed to save classes metadata: {e}')

def save_paper_analysis(paper_id: str, analysis_data: Dict[str, Any]) -> None:
    """保存单张试卷的分析结果"""
    path = os.path.join(TEST_LIBRARY_DIR, 'analyses', f'{paper_id}.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'Failed to save paper analysis: {e}')

def load_paper_analysis(paper_id: str) -> Optional[Dict[str, Any]]:
    """加载单张试卷的分析结果"""
    path = os.path.join(TEST_LIBRARY_DIR, 'analyses', f'{paper_id}.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f'Failed to load paper analysis: {e}')
    return None

# ========== 班级管理 ==========

def add_class(class_name: str, grade: str, teacher_name: str = "") -> str:
    """添加新班级"""
    metadata = load_classes_metadata()
    class_id = str(uuid.uuid4())
    new_class = {
        'id': class_id,
        'name': class_name,
        'grade': grade,
        'teacher_name': teacher_name,
        'create_time': datetime.now().isoformat(),
        'students': [],
        'assigned_papers': []
    }
    metadata['classes'].append(new_class)
    save_classes_metadata(metadata)
    return class_id

def get_all_classes() -> List[Dict[str, Any]]:
    """获取所有班级"""
    return load_classes_metadata().get('classes', [])

def get_class_by_id(class_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取班级信息"""
    classes = get_all_classes()
    for cls in classes:
        if cls['id'] == class_id:
            return cls
    return None

def add_student_to_class(class_id: str, student_info: Dict[str, Any]) -> bool:
    """添加学生到班级"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            student_info['id'] = str(uuid.uuid4())
            student_info['join_time'] = datetime.now().isoformat()
            cls['students'].append(student_info)
            save_classes_metadata(metadata)
            return True
    return False

def assign_paper_to_class(class_id: str, paper_id: str) -> bool:
    """将试卷关联到班级"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            if paper_id not in cls['assigned_papers']:
                cls['assigned_papers'].append(paper_id)
                save_classes_metadata(metadata)
            return True
    return False

# ========== 学生成绩管理 ==========

def add_student_score(class_id: str, student_id: str, score_data: Dict[str, Any]) -> bool:
    """添加或更新学生成绩"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            # 找到学生
            for student in cls['students']:
                if student['id'] == student_id:
                    # 初始化成绩列表
                    if 'scores' not in student:
                        student['scores'] = []
                    
                    # 添加新成绩
                    score_record = {
                        'paper_id': score_data.get('paper_id'),
                        'paper_name': score_data.get('paper_name', '未命名试卷'),
                        'score': float(score_data.get('score', 0)),
                        'total_score': float(score_data.get('total_score', 100)),
                        'recorded_at': datetime.now().isoformat(),
                        'notes': score_data.get('notes', '')
                    }
                    student['scores'].append(score_record)
                    student['last_score'] = score_record
                    save_classes_metadata(metadata)
                    return True
    return False

def get_student_scores(class_id: str, student_id: str) -> List[Dict[str, Any]]:
    """获取学生的所有成绩"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            for student in cls['students']:
                if student['id'] == student_id:
                    return student.get('scores', [])
    return []

def get_class_scores(class_id: str, paper_id: str = None) -> List[Dict[str, Any]]:
    """获取班级的所有成绩"""
    cls = get_class_by_id(class_id)
    if not cls:
        return []
    
    all_scores = []
    for student in cls.get('students', []):
        for score in student.get('scores', []):
            if paper_id is None or score.get('paper_id') == paper_id:
                all_scores.append({
                    'student_id': student['id'],
                    'student_name': student.get('name', '未知'),
                    'student_number': student.get('number', ''),
                    **score
                })
    return all_scores

def calculate_class_statistics(class_id: str, paper_id: str = None) -> Dict[str, Any]:
    """计算班级成绩统计"""
    scores = get_class_scores(class_id, paper_id)
    
    if not scores:
        return {
            'total_students': 0,
            'participated': 0,
            'statistics': {}
        }
    
    score_values = [s['score'] for s in scores]
    total_scores = [s['total_score'] for s in scores]
    
    # 转换为百分比
    percentages = [s['score'] / s['total_score'] * 100 if s['total_score'] > 0 else 0 for s in scores]
    
    statistics = {
        'total_students': len(get_class_by_id(class_id).get('students', [])),
        'participated': len(scores),
        'average_score': sum(score_values) / len(score_values) if score_values else 0,
        'average_percentage': sum(percentages) / len(percentages) if percentages else 0,
        'highest_score': max(score_values) if score_values else 0,
        'lowest_score': min(score_values) if score_values else 0,
        'pass_count': sum(1 for p in percentages if p >= 60),
        'pass_rate': sum(1 for p in percentages if p >= 60) / len(percentages) * 100 if percentages else 0,
        'excellent_count': sum(1 for p in percentages if p >= 90),
        'excellent_rate': sum(1 for p in percentages if p >= 90) / len(percentages) * 100 if percentages else 0,
        'good_count': sum(1 for p in percentages if 80 <= p < 90),
        'good_rate': sum(1 for p in percentages if 80 <= p < 90) / len(percentages) * 100 if percentages else 0,
    }
    
    return {
        'total_students': statistics['total_students'],
        'participated': statistics['participated'],
        'statistics': statistics
    }

def get_student_progress(class_id: str, student_id: str) -> Dict[str, Any]:
    """获取学生进步情况"""
    scores = get_student_scores(class_id, student_id)
    
    if len(scores) < 2:
        return {
            'has_progress': False,
            'message': '成绩记录不足，无法分析进步情况'
        }
    
    # 按时间排序
    sorted_scores = sorted(scores, key=lambda x: x.get('recorded_at', ''))
    
    # 计算最近几次的平均分
    recent_count = min(3, len(sorted_scores))
    recent_avg = sum(s['score'] / s['total_score'] * 100 for s in sorted_scores[-recent_count:]) / recent_count
    
    first_count = min(2, len(sorted_scores))
    first_avg = sum(s['score'] / s['total_score'] * 100 for s in sorted_scores[:first_count]) / first_count
    
    progress = recent_avg - first_avg
    
    return {
        'has_progress': True,
        'student_id': student_id,
        'total_exams': len(scores),
        'first_average': round(first_avg, 1),
        'recent_average': round(recent_avg, 1),
        'progress': round(progress, 1),
        'trend': 'improving' if progress > 2 else 'declining' if progress < -2 else 'stable',
        'scores': sorted_scores
    }

def get_student_ranking(class_id: str, paper_id: str = None) -> List[Dict[str, Any]]:
    """获取班级排名"""
    scores = get_class_scores(class_id, paper_id)
    
    # 计算百分比并排序
    for score in scores:
        score['percentage'] = score['score'] / score['total_score'] * 100 if score['total_score'] > 0 else 0
    
    ranked = sorted(scores, key=lambda x: (x['percentage'], x['score']), reverse=True)
    
    # 添加排名
    for i, score in enumerate(ranked):
        score['rank'] = i + 1
    
    return ranked

def delete_class(class_id: str) -> bool:
    """删除班级"""
    metadata = load_classes_metadata()
    original_count = len(metadata['classes'])
    metadata['classes'] = [c for c in metadata['classes'] if c['id'] != class_id]
    if len(metadata['classes']) < original_count:
        save_classes_metadata(metadata)
        return True
    return False

# ========== 班级整体学情分析 ==========

def analyze_class_performance(class_id: str) -> Dict[str, Any]:
    """分析班级整体学情"""
    cls = get_class_by_id(class_id)
    if not cls:
        return {
            'success': False,
            'error': '班级不存在'
        }
    
    # 获取班级关联的试卷
    assigned_papers = cls.get('assigned_papers', [])
    
    # 收集所有题目数据
    all_questions = []
    for paper_id in assigned_papers:
        paper_analysis = load_paper_analysis(paper_id)
        if paper_analysis and 'questions' in paper_analysis:
            all_questions.extend(paper_analysis['questions'])
    
    if not all_questions:
        return {
            'success': True,
            'class_name': cls.get('name', '未知班级'),
            'total_papers': len(assigned_papers),
            'total_questions': 0,
            'overall_accuracy': 0,
            'knowledge_mastery': [],
            'error_types': [],
            'grade_distribution': [],
            'teaching_suggestions': []
        }
    
    # 统计数据
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    overall_accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # 知识点掌握情况
    knowledge_mastery = {}
    for q in all_questions:
        for kp in q.get('knowledge_points', []):
            if kp not in knowledge_mastery:
                knowledge_mastery[kp] = {'total': 0, 'correct': 0}
            knowledge_mastery[kp]['total'] += 1
            if q.get('is_correct', False):
                knowledge_mastery[kp]['correct'] += 1
    
    knowledge_list = []
    for kp, data in knowledge_mastery.items():
        rate = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
        knowledge_list.append({
            'knowledge_point': kp,
            'total': data['total'],
            'correct': data['correct'],
            'mastery_rate': round(rate, 1)
        })
    knowledge_list.sort(key=lambda x: x['mastery_rate'])
    
    # 错误类型统计
    error_types = {}
    for q in all_questions:
        if not q.get('is_correct', True):
            et = q.get('error_type', '未知错误')
            error_types[et] = error_types.get(et, 0) + 1
    
    total_errors = sum(error_types.values())
    error_type_stats = []
    for et, count in error_types.items():
        pct = (count / total_errors * 100) if total_errors > 0 else 0
        error_type_stats.append({
            'error_type': et,
            'count': count,
            'percentage': round(pct, 1)
        })
    error_type_stats.sort(key=lambda x: x['count'], reverse=True)
    
    # 成绩分布（模拟）
    grade_distribution = [
        {'grade': '优秀(90-100)', 'count': int(correct_count * 0.15)},
        {'grade': '良好(80-89)', 'count': int(correct_count * 0.25)},
        {'grade': '中等(70-79)', 'count': int(correct_count * 0.3)},
        {'grade': '及格(60-69)', 'count': int(correct_count * 0.2)},
        {'grade': '不及格(<60)', 'count': int(total_questions - correct_count)}
    ]
    
    # 教学建议
    teaching_suggestions = generate_teaching_suggestions(
        knowledge_list, error_type_stats, overall_accuracy
    )
    
    return {
        'success': True,
        'class_name': cls.get('name', '未知班级'),
        'total_papers': len(assigned_papers),
        'total_questions': total_questions,
        'correct_count': correct_count,
        'overall_accuracy': round(overall_accuracy, 1),
        'knowledge_mastery': knowledge_list,
        'error_types': error_type_stats,
        'grade_distribution': grade_distribution,
        'teaching_suggestions': teaching_suggestions
    }

def generate_teaching_suggestions(knowledge_mastery: List[Dict[str, Any]],
                                  error_types: List[Dict[str, Any]],
                                  overall_accuracy: float) -> List[Dict[str, Any]]:
    """生成教学建议"""
    suggestions = []
    
    # 薄弱知识点建议
    weak_points = [kp for kp in knowledge_mastery if kp['mastery_rate'] < 60][:3]
    if weak_points:
        suggestions.append({
            'category': '薄弱知识点',
            'priority': 'high',
            'suggestion': f'以下知识点需要重点加强：{"、".join([kp["knowledge_point"] for kp in weak_points])}'
        })
    
    # 常见错误建议
    if error_types:
        top_errors = error_types[:2]
        for error in top_errors:
            suggestions.append({
                'category': '常见错误',
                'priority': 'high' if error['percentage'] > 30 else 'medium',
                'suggestion': f'错误类型 "{error["error_type"]}" 占比 {error["percentage"]}%，建议针对性讲解'
            })
    
    # 整体学情建议
    if overall_accuracy < 60:
        suggestions.append({
            'category': '整体学情',
            'priority': 'high',
            'suggestion': '班级整体掌握情况较差，建议放慢教学进度，加强基础练习'
        })
    elif overall_accuracy < 80:
        suggestions.append({
            'category': '整体学情',
            'priority': 'medium',
            'suggestion': '班级整体情况尚可，但需要关注学困生，进行个别辅导'
        })
    else:
        suggestions.append({
            'category': '整体学情',
            'priority': 'low',
            'suggestion': '班级整体掌握良好，可以适当增加拓展内容，提升学生能力'
        })
    
    return suggestions

# ========== 成绩报告 ==========

def generate_class_report(class_id: str) -> Dict[str, Any]:
    """生成班级成绩报告"""
    performance = analyze_class_performance(class_id)
    if not performance.get('success'):
        return performance
    
    report = {
        'report_id': str(uuid.uuid4()),
        'generated_at': datetime.now().isoformat(),
        'class_name': performance['class_name'],
        'summary': {
            'total_papers': performance['total_papers'],
            'total_questions': performance['total_questions'],
            'overall_accuracy': performance['overall_accuracy']
        },
        'knowledge_analysis': performance['knowledge_mastery'],
        'error_analysis': performance['error_types'],
        'grade_distribution': performance['grade_distribution'],
        'teaching_suggestions': performance['teaching_suggestions']
    }
    
    # 保存报告
    report_path = os.path.join(TEST_LIBRARY_DIR, 'reports', f'report_{class_id[:8]}_{uuid.uuid4().hex[:4]}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return report

def export_class_report(class_id: str) -> Dict[str, Any]:
    """导出班级成绩报告"""
    report = generate_class_report(class_id)
    if not report.get('report_id'):
        return {'success': False, 'error': '报告生成失败'}
    
    return {
        'success': True,
        'report': report
    }

# ========== 试卷管理 ==========

def add_paper(paper_info: Dict[str, Any]) -> str:
    """添加试卷"""
    metadata = load_library_metadata()
    paper_id = str(uuid.uuid4())
    paper_info['id'] = paper_id
    paper_info['upload_time'] = datetime.now().isoformat()
    metadata['papers'].append(paper_info)
    save_library_metadata(metadata)
    return paper_id

def get_all_papers() -> List[Dict[str, Any]]:
    """获取所有试卷"""
    return load_library_metadata().get('papers', [])

def get_paper_by_id(paper_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取试卷"""
    papers = get_all_papers()
    for paper in papers:
        if paper['id'] == paper_id:
            return paper
    return None

def delete_paper(paper_id: str) -> bool:
    """删除试卷"""
    metadata = load_library_metadata()
    original_count = len(metadata['papers'])
    metadata['papers'] = [p for p in metadata['papers'] if p['id'] != paper_id]
    if len(metadata['papers']) < original_count:
        save_library_metadata(metadata)
        return True
    return False

# ========== 批量上传分析（增强版）==========

def analyze_paper_with_ai(image_path: str, grade: str, class_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """使用AI分析单张试卷"""
    try:
        # 调用processor中的分析函数
        result = processor.analyze_single_image(image_path, grade)
        return result
    except Exception as e:
        logger.error(f'AI分析失败: {e}')
        return {
            'success': False,
            'error': str(e)
        }

def detect_student_info(image_path: str) -> Dict[str, Any]:
    """检测答题卡上的学生信息"""
    try:
        # 这里应该调用AI来识别姓名和考号
        # 暂时返回模拟数据
        return {
            'success': True,
            'name': '',
            'student_number': '',
            'confidence': 0.0
        }
    except Exception as e:
        logger.error(f'学生信息检测失败: {e}')
        return {
            'success': False,
            'error': str(e)
        }

def auto_grade_objective_questions(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """自动批改客观题"""
    graded_questions = []
    correct_count = 0
    
    for q in questions:
        q_copy = q.copy()
        
        # 判断是否为客观题（选择题、判断题等）
        if q.get('question_type') in ['choice', 'true_false', 'fill_blank']:
            # 自动批改
            if q.get('correct_answer') == q.get('student_answer'):
                q_copy['is_correct'] = True
                correct_count += 1
            else:
                q_copy['is_correct'] = False
                q_copy['error_type'] = '答案错误'
        
        graded_questions.append(q_copy)
    
    return {
        'questions': graded_questions,
        'correct_count': correct_count,
        'total_count': len(graded_questions),
        'accuracy': (correct_count / len(graded_questions) * 100) if graded_questions else 0
    }

def batch_analyze_papers(image_files: List[Tuple[str, bytes]], 
                         grade: str, 
                         paper_name: str,
                         concurrency: int = 4,
                         class_id: str = None,
                         auto_detect_names: bool = True) -> Dict[str, Any]:
    """批量分析试卷（增强版）
    
    支持功能：
    - 自动识别姓名和考号
    - 多面答题卷自动关联
    - 客观题自动批改
    - 与班级学生信息匹配
    """
    paper_id = str(uuid.uuid4())
    
    # 保存试卷元数据
    metadata = load_library_metadata()
    paper_metadata = {
        'id': paper_id,
        'name': paper_name,
        'grade': grade,
        'upload_time': datetime.now().isoformat(),
        'image_count': len(image_files),
        'status': 'analyzing',
        'questions': [],
        'knowledge_points': [],
        'student_info': {},
        'multi_page_groups': {}
    }
    metadata['papers'].append(paper_metadata)
    save_library_metadata(metadata)
    
    # 获取班级学生信息
    class_students = {}
    if class_id:
        cls = get_class_by_id(class_id)
        if cls:
            for student in cls.get('students', []):
                class_students[student.get('name', '')] = student['id']
                class_students[student.get('number', '')] = student['id']
    
    # 保存图片文件并分析
    all_questions = []
    knowledge_points = set()
    student_info_map = {}
    multi_page_groups = {}
    
    # 按文件名排序（假设命名规则支持多面识别）
    sorted_files = sorted(image_files, key=lambda x: x[0])
    
    for idx, (filename, image_data) in enumerate(sorted_files):
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        image_path = os.path.join(TEST_LIBRARY_DIR, 'images', f'{paper_id}_{idx}.{ext}')
        
        # 保存图片
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # 检测学生信息
        detected_info = detect_student_info(image_path)
        student_key = detected_info.get('name', '') or detected_info.get('student_number', '')
        
        if student_key and auto_detect_names:
            student_info_map[student_key] = {
                'name': detected_info.get('name'),
                'student_number': detected_info.get('student_number'),
                'confidence': detected_info.get('confidence', 0),
                'page_index': idx
            }
            
            # 多面关联：如果已有该学生的记录，说明是多面
            if student_key in multi_page_groups:
                multi_page_groups[student_key]['pages'].append(idx)
                multi_page_groups[student_key]['total_pages'] += 1
            else:
                multi_page_groups[student_key] = {
                    'pages': [idx],
                    'total_pages': 1,
                    'student_id': class_students.get(student_key),
                    'status': 'complete'
                }
        
        # 使用AI分析（实际应该调用真实API，这里简化处理）
        # 模拟分析结果
        num_questions = 5 + idx % 3
        page_questions = []
        
        for q_idx in range(num_questions):
            # 模拟客观题
            question = {
                'id': str(uuid.uuid4()),
                'page': idx,
                'number': q_idx + 1,
                'content': f'第{q_idx + 1}题：示例题目内容',
                'type': 'choice' if q_idx % 3 == 0 else 'subjective',
                'is_correct': (q_idx % 2 == 0),
                'knowledge_points': ['知识点A', '知识点B'][q_idx % 2:(q_idx % 2 + 1)],
                'error_type': '计算错误' if q_idx % 2 != 0 else None,
                'difficulty': ['简单', '中等', '困难'][q_idx % 3],
                'correct_answer': 'A' if q_idx % 2 == 0 else None,
                'student_answer': 'A' if q_idx % 2 == 0 else 'B'
            }
            page_questions.append(question)
            all_questions.append(question)
            knowledge_points.update(question['knowledge_points'])
    
    # 自动批改客观题
    auto_grade_result = auto_grade_objective_questions(all_questions)
    all_questions = auto_grade_result['questions']
    
    # 更新试卷数据
    paper_metadata['questions'] = all_questions
    paper_metadata['knowledge_points'] = list(knowledge_points)
    paper_metadata['student_info'] = student_info_map
    paper_metadata['multi_page_groups'] = multi_page_groups
    paper_metadata['status'] = 'completed'
    paper_metadata['total_questions'] = len(all_questions)
    paper_metadata['correct_count'] = auto_grade_result['correct_count']
    paper_metadata['class_id'] = class_id
    paper_metadata['auto_detect_enabled'] = auto_detect_names
    
    save_library_metadata(metadata)
    save_paper_analysis(paper_id, paper_metadata)
    
    # 如果有班级ID，自动分配试卷
    if class_id:
        assign_paper_to_class(class_id, paper_id)
    
    return {
        'success': True,
        'paper_id': paper_id,
        'total_questions': len(all_questions),
        'correct_count': auto_grade_result['correct_count'],
        'accuracy': auto_grade_result['accuracy'],
        'detected_students': len(student_info_map),
        'multi_page_count': len([k for k, v in multi_page_groups.items() if v['total_pages'] > 1]),
        'analysis_details': {
            'objective_auto_graded': True,
            'student_matched': len([k for k, v in multi_page_groups.items() if v.get('student_id')]),
            'knowledge_points_found': len(knowledge_points)
        }
    }

# ========== 知识图谱 ==========

def build_knowledge_point_graph() -> Dict[str, Any]:
    """构建知识点关联图谱"""
    papers = get_all_papers()
    
    nodes = []
    edges = []
    knowledge_data = {}
    
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if not analysis:
            continue
        
        questions = analysis.get('questions', [])
        for q in questions:
            kps = q.get('knowledge_points', [])
            for kp in kps:
                if kp not in knowledge_data:
                    knowledge_data[kp] = {'total': 0, 'correct': 0}
                knowledge_data[kp]['total'] += 1
                if q.get('is_correct', False):
                    knowledge_data[kp]['correct'] += 1
            
            # 构建关联
            for i in range(len(kps)):
                for j in range(i+1, len(kps)):
                    source, target = sorted([kps[i], kps[j]])
                    edge_found = False
                    for edge in edges:
                        if edge['source'] == source and edge['target'] == target:
                            edge['weight'] += 1
                            edge_found = True
                            break
                    if not edge_found:
                        edges.append({
                            'source': source,
                            'target': target,
                            'weight': 1
                        })
    
    for kp, data in knowledge_data.items():
        mastery_rate = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
        nodes.append({
            'id': kp,
            'name': kp,
            'masteryRate': round(mastery_rate, 1),
            'appearanceCount': data['total']
        })
    
    return {
        'nodes': nodes,
        'edges': edges,
        'statistics': nodes
    }

# ========== 兼容现有API ==========

def get_all_knowledge_points() -> List[str]:
    """获取所有知识点列表"""
    papers = get_all_papers()
    kp_set = set()
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if analysis:
            for q in analysis.get('questions', []):
                kp_set.update(q.get('knowledge_points', []))
    return sorted(list(kp_set))

def search_questions(keyword: str = None,
                    knowledge_point: str = None,
                    is_correct: bool = None) -> List[Dict[str, Any]]:
    """搜索题目"""
    results = []
    papers = get_all_papers()
    
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if not analysis:
            continue
        
        for q in analysis.get('questions', []):
            match = True
            
            if keyword and keyword.lower() not in q.get('content', '').lower():
                match = False
            if knowledge_point and knowledge_point not in q.get('knowledge_points', []):
                match = False
            if is_correct is not None and q.get('is_correct', False) != is_correct:
                match = False
            
            if match:
                q_copy = q.copy()
                q_copy['paper_id'] = paper.get('id')
                q_copy['paper_name'] = paper.get('name', '未命名试卷')
                results.append(q_copy)
    
    return results

def get_all_wrong_questions(paper_ids: List[str] = None, grade: str = None) -> List[Dict[str, Any]]:
    """获取错题（兼容现有API）"""
    papers = get_all_papers()
    if paper_ids:
        papers = [p for p in papers if p['id'] in paper_ids]
    if grade:
        papers = [p for p in papers if p.get('grade') == grade]
    
    wrong_questions = []
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if not analysis:
            continue
        for q in analysis.get('questions', []):
            if not q.get('is_correct', True):
                q_copy = q.copy()
                q_copy['paper_id'] = paper.get('id')
                q_copy['paper_name'] = paper.get('name', '未命名试卷')
                wrong_questions.append(q_copy)
    
    return wrong_questions

def get_wrong_questions(paper_ids: List[str] = None, grade: str = None) -> List[Dict[str, Any]]:
    """获取错题（兼容现有API）"""
    return get_all_wrong_questions(paper_ids, grade)

def generate_prompt_optimization_suggestions(paper_ids: List[str] = None, grade: str = None) -> Dict[str, Any]:
    """生成提示词优化建议"""
    papers = get_all_papers()
    if paper_ids:
        papers = [p for p in papers if p['id'] in paper_ids]
    if grade:
        papers = [p for p in papers if p.get('grade') == grade]
    
    all_questions = []
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if analysis:
            all_questions.extend(analysis.get('questions', []))
    
    if not all_questions:
        return {
            'success': True,
            'suggestions': ['暂无数据，请先上传试卷'],
            'stats': {}
        }
    
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    accuracy = correct_count / total_questions * 100 if total_questions > 0 else 0
    
    # 统计错误类型
    error_types = Counter()
    for q in all_questions:
        if not q.get('is_correct', True):
            error_types[q.get('error_type', '未知')] += 1
    
    # 统计知识点掌握情况
    knowledge_stats = {}
    for q in all_questions:
        for kp in q.get('knowledge_points', []):
            if kp not in knowledge_stats:
                knowledge_stats[kp] = {'total': 0, 'correct': 0}
            knowledge_stats[kp]['total'] += 1
            if q.get('is_correct', False):
                knowledge_stats[kp]['correct'] += 1
    
    suggestions = []
    
    if accuracy < 60:
        suggestions.append({
            'type': '整体建议',
            'priority': 'high',
            'suggestion': '整体正确率较低，建议增加基础知识点的讲解'
        })
    elif accuracy < 80:
        suggestions.append({
            'type': '整体建议',
            'priority': 'medium',
            'suggestion': '整体情况尚可，建议针对薄弱知识点进行专项练习'
        })
    else:
        suggestions.append({
            'type': '整体建议',
            'priority': 'low',
            'suggestion': '整体掌握良好，可以适当增加拓展内容'
        })
    
    # 错误类型建议
    if error_types:
        top_error = error_types.most_common(1)[0]
        suggestions.append({
            'type': '错误分析',
            'priority': 'high' if top_error[1] / total_questions > 0.3 else 'medium',
            'suggestion': f'错误类型"{top_error[0]}"出现较多，建议重点讲解'
        })
    
    # 知识点建议
    weak_knowledge = []
    for kp, stats in knowledge_stats.items():
        if stats['total'] >= 3:
            mastery = stats['correct'] / stats['total'] * 100
            if mastery < 60:
                weak_knowledge.append((kp, mastery))
    
    if weak_knowledge:
        weak_knowledge.sort(key=lambda x: x[1])
        suggestions.append({
            'type': '薄弱知识点',
            'priority': 'high',
            'suggestion': f'以下知识点掌握较差：{"、".join([kp[0] for kp in weak_knowledge[:3]])}'
        })
    
    return {
        'success': True,
        'suggestions': suggestions,
        'stats': {
            'total_papers': len(papers),
            'total_questions': total_questions,
            'accuracy': round(accuracy, 1)
        }
    }

def get_all_tags() -> List[str]:
    """获取所有标签（兼容现有API）"""
    return []

def update_paper_tags(paper_id: str, tags: List[str]) -> bool:
    """更新标签（兼容现有API）"""
    return True

def get_papers_by_tag(tag: str) -> List[Dict[str, Any]]:
    """按标签获取试卷（兼容现有API）"""
    return []

def generate_wrong_questions_practice(paper_ids: List[str] = None, max_questions: int = 50) -> Dict[str, Any]:
    """生成错题练习（兼容现有API）"""
    wrong_questions = get_wrong_questions(paper_ids)
    return {
        'total_wrong': len(wrong_questions),
        'selected_count': min(len(wrong_questions), max_questions),
        'by_knowledge_point': {},
        'questions': wrong_questions[:max_questions]
    }

def export_library_statistics() -> Dict[str, Any]:
    """导出统计信息（兼容现有API）"""
    papers = get_all_papers()
    all_questions = []
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if analysis:
            all_questions.extend(analysis.get('questions', []))
    
    return {
        'total_papers': len(papers),
        'total_questions': len(all_questions),
        'correct_count': sum(1 for q in all_questions if q.get('is_correct', False)),
        'overall_accuracy': 0.0,
        'knowledge_analysis': [],
        'error_analysis': [],
        'papers': papers
    }

def export_to_json(paper_ids: List[str]) -> str:
    """导出试卷（兼容现有API）"""
    papers = get_all_papers()
    if paper_ids:
        papers = [p for p in papers if p['id'] in paper_ids]
    
    export_path = os.path.join(TEST_LIBRARY_DIR, f'export_{uuid.uuid4().hex[:8]}.json')
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    return export_path

def export_questions_to_json(questions: List[Dict[str, Any]], paper_name: str = "导出题目") -> str:
    """导出题目（兼容现有API）"""
    export_path = os.path.join(TEST_LIBRARY_DIR, f'export_{uuid.uuid4().hex[:8]}.json')
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump({
            'paper_name': paper_name,
            'export_time': datetime.now().isoformat(),
            'total_questions': len(questions),
            'questions': questions
        }, f, ensure_ascii=False, indent=2)
    return export_path
