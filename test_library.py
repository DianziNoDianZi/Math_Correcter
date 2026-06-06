"""
试卷库管理模块 - 增强版
支持考试管理、答题卡扫描、成绩审核等完整教学流程
"""
import os
import uuid
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import sys
from pathlib import Path

# 添加项目根目录到路径以便导入app模块
sys.path.insert(0, str(Path(__file__).parent))
from app.utils.helpers import get_timestamp

# 导入 AI 分析服务
from app.services.ai_analysis_service import (
    generate_exam_analysis as ai_generate_exam_analysis,
    generate_class_report as ai_generate_class_report,
    invalidate_exam_cache,
    invalidate_class_cache
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 目录配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEST_LIBRARY_DIR = os.path.join(DATA_DIR, 'test_library')
CLASSES_DIR = os.path.join(DATA_DIR, 'classes')
EXAMS_DIR = os.path.join(DATA_DIR, 'exams')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# 确保目录存在
for d in [DATA_DIR, TEST_LIBRARY_DIR, CLASSES_DIR, EXAMS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, 'images'), exist_ok=True)
    os.makedirs(os.path.join(d, 'scans'), exist_ok=True)

# ========== 配置文件读写 ==========

def load_json(filepath: str) -> Dict:
    """加载JSON文件"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f'加载JSON失败: {e}')
        return {}

def save_json(filepath: str, data: Dict) -> bool:
    """保存JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f'保存JSON失败: {e}')
        return False

# ========== 试卷库元数据 ==========

def load_library_metadata() -> Dict:
    """加载试卷库元数据"""
    return load_json(os.path.join(TEST_LIBRARY_DIR, 'metadata.json'))

def save_library_metadata(metadata: Dict) -> bool:
    """保存试卷库元数据"""
    return save_json(os.path.join(TEST_LIBRARY_DIR, 'metadata.json'), metadata)

def init_library_metadata() -> Dict:
    """初始化试卷库元数据"""
    metadata = load_library_metadata()
    if not metadata:
        metadata = {
            'papers': [],
            'total_uploaded': 0,
            'last_updated': datetime.now().isoformat()
        }
        save_library_metadata(metadata)
    return metadata

# ========== 班级元数据 ==========

def load_classes_metadata() -> Dict:
    """加载班级元数据"""
    return load_json(os.path.join(CLASSES_DIR, 'metadata.json'))

def save_classes_metadata(metadata: Dict) -> bool:
    """保存班级元数据"""
    return save_json(os.path.join(CLASSES_DIR, 'metadata.json'), metadata)

def init_classes_metadata() -> Dict:
    """初始化班级元数据"""
    metadata = load_classes_metadata()
    if not metadata:
        metadata = {
            'classes': [],
            'total_students': 0
        }
        save_classes_metadata(metadata)
    return metadata

# ========== 考试元数据 ==========

def load_exams_metadata() -> Dict:
    """加载考试元数据"""
    return load_json(os.path.join(EXAMS_DIR, 'metadata.json'))

def save_exams_metadata(metadata: Dict) -> bool:
    """保存考试元数据"""
    return save_json(os.path.join(EXAMS_DIR, 'metadata.json'), metadata)

def init_exams_metadata() -> Dict:
    """初始化考试元数据"""
    metadata = load_exams_metadata()
    if not metadata:
        metadata = {'exams': []}
        save_exams_metadata(metadata)
    return metadata

# ========== 试卷库管理 ==========

def get_all_papers() -> List[Dict[str, Any]]:
    """获取所有试卷"""
    metadata = load_library_metadata()
    return metadata.get('papers', [])

def get_paper_by_id(paper_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取试卷"""
    metadata = load_library_metadata()
    for paper in metadata.get('papers', []):
        if paper['id'] == paper_id:
            return paper
    return None

def load_paper_analysis(paper_id: str) -> Optional[Dict[str, Any]]:
    """加载试卷分析结果"""
    analysis_path = os.path.join(TEST_LIBRARY_DIR, 'analyses', f'{paper_id}.json')
    return load_json(analysis_path)

def save_paper_analysis(paper_id: str, analysis: Dict) -> bool:
    """保存试卷分析结果"""
    analysis_dir = os.path.join(TEST_LIBRARY_DIR, 'analyses')
    os.makedirs(analysis_dir, exist_ok=True)
    analysis_path = os.path.join(analysis_dir, f'{paper_id}.json')
    return save_json(analysis_path, analysis)

# ========== 班级管理 ==========

def get_all_classes() -> List[Dict[str, Any]]:
    """获取所有班级"""
    metadata = load_classes_metadata()
    return metadata.get('classes', [])

def get_class_by_id(class_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取班级"""
    metadata = load_classes_metadata()
    for cls in metadata.get('classes', []):
        if cls['id'] == class_id:
            return cls
    return None

def add_class(class_data: Dict[str, Any]) -> Dict[str, Any]:
    """添加班级"""
    class_id = str(uuid.uuid4())
    
    metadata = load_classes_metadata()
    new_class = {
        'id': class_id,
        'name': class_data.get('name', '未命名班级'),
        'grade': class_data.get('grade', '10-12'),
        'teacher_name': class_data.get('teacher_name', ''),
        'created_at': datetime.now().isoformat(),
        'students': [],
        'assigned_papers': []
    }
    
    metadata['classes'].append(new_class)
    save_classes_metadata(metadata)
    
    return {
        'success': True,
        'class_id': class_id,
        'class': new_class
    }

def add_student_to_class(class_id: str, student_data: Dict[str, Any]) -> bool:
    """添加学生到班级"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            student_id = str(uuid.uuid4())
            student = {
                'id': student_id,
                'name': student_data.get('name', ''),
                'student_number': student_data.get('student_number', ''),
                'added_at': datetime.now().isoformat(),
                'scores': []
            }
            cls['students'].append(student)
            metadata['total_students'] = metadata.get('total_students', 0) + 1
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

def delete_class(class_id: str) -> bool:
    """删除班级"""
    metadata = load_classes_metadata()
    initial_length = len(metadata['classes'])
    metadata['classes'] = [c for c in metadata['classes'] if c['id'] != class_id]
    
    if len(metadata['classes']) < initial_length:
        save_classes_metadata(metadata)
        return True
    return False

# ========== 学生成绩管理 ==========

def add_student_score(class_id: str, student_id: str, score_data: Dict[str, Any]) -> bool:
    """添加或更新学生成绩"""
    metadata = load_classes_metadata()
    for cls in metadata['classes']:
        if cls['id'] == class_id:
            for student in cls['students']:
                if student['id'] == student_id:
                    if 'scores' not in student:
                        student['scores'] = []
                    
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
                    'student_number': student.get('student_number', ''),
                    **score
                })
    return all_scores

def calculate_class_statistics(class_id: str, paper_id: str = None) -> Dict[str, Any]:
    """计算班级成绩统计"""
    scores = get_class_scores(class_id, paper_id)
    
    if not scores:
        return {'total_students': 0, 'participated': 0, 'statistics': {}}
    
    score_values = [s['score'] for s in scores]
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
        return {'has_progress': False, 'message': '成绩记录不足，无法分析进步情况'}
    
    sorted_scores = sorted(scores, key=lambda x: x.get('recorded_at', ''))
    
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

# ========== 考试管理 ==========

def create_exam(exam_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建考试"""
    exam_id = str(uuid.uuid4())
    
    exam = {
        'id': exam_id,
        'name': exam_data.get('name', '未命名考试'),
        'class_id': exam_data.get('class_id'),
        'grade': exam_data.get('grade'),
        'total_score': float(exam_data.get('total_score', 100)),
        'created_at': datetime.now().isoformat(),
        'status': 'draft',  # draft:草稿, ready:就绪, scanning:扫描中, reviewing:待审核, completed:已完成
        'questions': [],  # 题目信息
        'scores': [],  # 扫描后的成绩
        'statistics': {}
    }
    
    metadata = load_exams_metadata()
    metadata['exams'].append(exam)
    save_exams_metadata(metadata)
    
    return {'success': True, 'exam_id': exam_id, 'exam': exam}

def add_question_to_exam(exam_id: str, question_data: Dict[str, Any]) -> bool:
    """添加题目到考试"""
    metadata = load_exams_metadata()
    for exam in metadata['exams']:
        if exam['id'] == exam_id:
            question = {
                'number': len(exam['questions']) + 1,
                'type': question_data.get('type', 'choice'),  # choice, true_false, fill_blank, subjective
                'content': question_data.get('content', ''),
                'correct_answer': question_data.get('correct_answer'),
                'score': float(question_data.get('score', 5)),
                'knowledge_points': question_data.get('knowledge_points', []),
                'difficulty': question_data.get('difficulty', 'medium')
            }
            exam['questions'].append(question)
            save_exams_metadata(metadata)
            return True
    return False

def set_exam_ready(exam_id: str) -> bool:
    """设置考试就绪状态"""
    metadata = load_exams_metadata()
    for exam in metadata['exams']:
        if exam['id'] == exam_id:
            if len(exam['questions']) == 0:
                return False
            exam['status'] = 'ready'
            save_exams_metadata(metadata)
            return True
    return False

def get_exam_by_id(exam_id: str) -> Optional[Dict[str, Any]]:
    """获取考试详情"""
    metadata = load_exams_metadata()
    for exam in metadata['exams']:
        if exam['id'] == exam_id:
            return exam
    return None

def get_exams_by_class(class_id: str) -> List[Dict[str, Any]]:
    """获取班级的所有考试"""
    metadata = load_exams_metadata()
    return [e for e in metadata['exams'] if e.get('class_id') == class_id]

def delete_exam(exam_id: str) -> bool:
    """删除考试"""
    metadata = load_exams_metadata()
    initial_length = len(metadata['exams'])
    metadata['exams'] = [e for e in metadata['exams'] if e['id'] != exam_id]
    
    if len(metadata['exams']) < initial_length:
        save_exams_metadata(metadata)
        return True
    return False

# ========== 答题卡识别 ==========

def detect_student_number(image_path: str, original_filename: str = '') -> str:
    """识别学生考号（AI 优先，失败时从文件名提取）"""
    from app.services.ai_scan_service import detect_student_number_ai
    
    result = detect_student_number_ai(image_path, original_filename)
    if result:
        logger.info(f'学号识别结果: {result}')
        return result
    return ''

def detect_answers(image_path: str, questions: List[Dict]) -> Dict[int, Any]:
    """识别学生答题结果（AI 优先，失败时留空）"""
    from app.services.ai_scan_service import detect_answers_ai
    
    ai_answers = detect_answers_ai(image_path, questions)
    # 转换为兼容格式：{题号: 答案字符串}
    result = {}
    for q in questions:
        q_num = q['number']
        if q_num in ai_answers:
            result[q_num] = ai_answers[q_num].get('answer', '')
    return result

def scan_answer_sheet(exam_id: str, image_path: str, original_filename: str = '') -> Dict[str, Any]:
    """扫描单张答题卡"""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {'success': False, 'error': '考试不存在'}
    
    if exam['status'] not in ['ready', 'scanning']:
        return {'success': False, 'error': '考试状态不允许扫描'}
    
    try:
        student_number = detect_student_number(image_path, original_filename)
        answers = detect_answers(image_path, exam['questions'])
        
        results = []
        correct_count = 0
        total_score = 0
        knowledge_stats = {}
        
        for q in exam['questions']:
            q_num = q['number']
            student_answer = answers.get(q_num)
            is_correct = None
            score = 0
            
            if q['type'] in ['choice', 'true_false', 'fill_blank']:
                if student_answer is not None:
                    is_correct = (student_answer == q['correct_answer'])
                    if is_correct:
                        correct_count += 1
                        score = q['score']
                        total_score += q['score']
                    else:
                        score = 0
                else:
                    is_correct = False
                    score = 0
            
            for kp in q.get('knowledge_points', []):
                if kp not in knowledge_stats:
                    knowledge_stats[kp] = {'total': 0, 'correct': 0}
                knowledge_stats[kp]['total'] += 1
                if is_correct:
                    knowledge_stats[kp]['correct'] += 1
            
            results.append({
                'number': q_num,
                'type': q['type'],
                'student_answer': student_answer,
                'correct_answer': q['correct_answer'],
                'is_correct': is_correct,
                'score': score,
                'max_score': q['score'],
                'knowledge_points': q.get('knowledge_points', [])
            })
        
        return {
            'success': True,
            'student_number': student_number,
            'results': results,
            'total_score': total_score,
            'max_score': exam['total_score'],
            'correct_count': correct_count,
            'total_questions': len(exam['questions']),
            'accuracy': (total_score / exam['total_score'] * 100) if exam['total_score'] > 0 else 0,
            'knowledge_stats': knowledge_stats,
            'ai_scanned': True  # 标记为AI/程序扫描
        }
    except Exception as e:
        logger.error(f'答题卡扫描失败: {e}')
        return {'success': False, 'error': str(e)}

def batch_scan_answer_sheets(exam_id: str, image_files: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    """批量扫描答题卡"""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {'success': False, 'error': '考试不存在'}
    
    metadata = load_exams_metadata()
    for e in metadata['exams']:
        if e['id'] == exam_id:
            e['status'] = 'scanning'
            save_exams_metadata(metadata)
            break
    
    cls = get_class_by_id(exam.get('class_id'))
    student_map = {}
    if cls:
        for student in cls.get('students', []):
            student_map[student.get('student_number', '')] = student
    
    scanned_results = []
    matched_count = 0
    unmatched_count = 0
    
    for idx, (filename, image_data) in enumerate(image_files):
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        image_path = os.path.join(TEST_LIBRARY_DIR, 'scans', f'{exam_id}_{idx}.{ext}')
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        scan_result = scan_answer_sheet(exam_id, image_path, filename)
        if scan_result.get('success'):
            student_info = student_map.get(scan_result.get('student_number', ''))
            if student_info:
                scan_result['student_id'] = student_info['id']
                scan_result['student_name'] = student_info['name']
                matched_count += 1
            else:
                unmatched_count += 1
                scan_result['student_id'] = None
                scan_result['student_name'] = '未匹配'
            
            scan_result['image_path'] = image_path
            scanned_results.append(scan_result)
    
    for e in metadata['exams']:
        if e['id'] == exam_id:
            for r in scanned_results:
                r['confirmed'] = False
                r['created_at'] = get_timestamp()
            e['scores'] = scanned_results
            e['status'] = 'reviewing'
            save_exams_metadata(metadata)
            break
    
    return {
        'success': True,
        'total_scanned': len(scanned_results),
        'matched': matched_count,
        'unmatched': unmatched_count,
        'results': scanned_results
    }

def confirm_exam_scores(exam_id: str) -> Dict[str, Any]:
    """确认考试成绩"""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {'success': False, 'error': '考试不存在'}
    
    if exam['status'] != 'reviewing':
        return {'success': False, 'error': '考试状态不允许确认'}
    
    metadata = load_exams_metadata()
    for e in metadata['exams']:
        if e['id'] == exam_id:
            scores = [s['total_score'] for s in e['scores'] if s.get('student_id')]
            if scores:
                e['statistics'] = {
                    'total_students': len(scores),
                    'average_score': sum(scores) / len(scores),
                    'highest_score': max(scores),
                    'lowest_score': min(scores),
                    'pass_count': sum(1 for s in scores if s / e['total_score'] >= 0.6),
                    'pass_rate': sum(1 for s in scores if s / e['total_score'] >= 0.6) / len(scores) * 100
                }
            
            if e.get('class_id'):
                for score in e['scores']:
                    if score.get('student_id'):
                        add_student_score(
                            e['class_id'],
                            score['student_id'],
                            {
                                'paper_id': exam_id,
                                'paper_name': e['name'],
                                'score': score['total_score'],
                                'total_score': e['total_score'],
                                'notes': f"答题卡扫描 - {score.get('student_name', '未知')}"
                            }
                        )
            
            e['status'] = 'completed'
            save_exams_metadata(metadata)
            invalidate_exam_cache(exam_id)  # 清除 AI 分析缓存
            return {'success': True, 'statistics': e['statistics']}
    
    return {'success': False, 'error': '考试不存在'}

def adjust_score(exam_id: str, student_number: str, score: float) -> Dict[str, Any]:
    """调整单条成绩"""
    metadata = load_exams_metadata()
    for exam in metadata['exams']:
        if exam['id'] == exam_id:
            for s in exam['scores']:
                if s.get('student_number') == student_number:
                    s['total_score'] = score
                    s['adjusted'] = True
                    # 同步更新正确率
                    max_score = exam.get('total_score', s.get('max_score', 100))
                    if max_score > 0:
                        s['accuracy'] = (score / max_score) * 100
                    save_exams_metadata(metadata)
                    invalidate_exam_cache(exam_id)  # 清除 AI 分析缓存
                    return {'success': True}
            return {'success': False, 'error': '未找到该学生成绩'}
    return {'success': False, 'error': '考试不存在'}

def get_exam_analysis(exam_id: str) -> Dict[str, Any]:
    """获取考试详细分析"""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {'success': False, 'error': '考试不存在'}
    
    question_stats = []
    for q in exam['questions']:
        correct_count = 0
        for score in exam.get('scores', []):
            for r in score.get('results', []):
                if r['number'] == q['number'] and r.get('is_correct'):
                    correct_count += 1
        
        total = len(exam.get('scores', []))
        question_stats.append({
            'number': q['number'],
            'type': q['type'],
            'knowledge_points': q.get('knowledge_points', []),
            'correct_count': correct_count,
            'error_count': total - correct_count,
            'error_rate': ((total - correct_count) / total * 100) if total > 0 else 0
        })
    
    knowledge_stats = {}
    for q in exam['questions']:
        for kp in q.get('knowledge_points', []):
            if kp not in knowledge_stats:
                knowledge_stats[kp] = {'total': 0, 'correct': 0}
            knowledge_stats[kp]['total'] += len(exam.get('scores', []))
    
    for score in exam.get('scores', []):
        for r in score.get('results', []):
            for kp in r.get('knowledge_points', []):
                if kp in knowledge_stats and r.get('is_correct'):
                    knowledge_stats[kp]['correct'] += 1
    
    for kp, stats in knowledge_stats.items():
        stats['mastery_rate'] = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    return {
        'success': True,
        'exam': exam,
        'question_stats': question_stats,
        'knowledge_stats': knowledge_stats,
        'statistics': exam.get('statistics', {}),
        'ai_report': ai_generate_exam_analysis({
            'exam': exam,
            'question_stats': question_stats,
            'knowledge_stats': knowledge_stats,
            'statistics': exam.get('statistics', {})
        })
    }

# ========== 批量上传分析（兼容旧接口）==========

def get_all_wrong_questions(paper_ids: List[str] = None, grade: str = None) -> List[Dict[str, Any]]:
    """获取错题"""
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
        return {'success': True, 'suggestions': ['暂无数据，请先上传试卷'], 'stats': {}}
    
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    accuracy = correct_count / total_questions * 100 if total_questions > 0 else 0
    
    suggestions = []
    if accuracy < 60:
        suggestions.append({'type': '整体建议', 'priority': 'high', 'suggestion': '整体正确率较低，建议增加基础知识点的讲解'})
    elif accuracy < 80:
        suggestions.append({'type': '整体建议', 'priority': 'medium', 'suggestion': '整体情况尚可，建议针对薄弱知识点进行专项练习'})
    else:
        suggestions.append({'type': '整体建议', 'priority': 'low', 'suggestion': '整体掌握良好，可以适当增加拓展内容'})
    
    return {'success': True, 'suggestions': suggestions, 'stats': {'total_papers': len(papers), 'total_questions': total_questions, 'accuracy': round(accuracy, 1)}}

def batch_analyze_papers(image_files: List[Tuple[str, bytes]], 
                         grade: str, 
                         paper_name: str,
                         concurrency: int = 4,
                         class_id: str = None,
                         auto_detect_names: bool = True,
                         work_mode: str = 'auto') -> Dict[str, Any]:
    """批量分析试卷（兼容旧接口）"""
    paper_id = str(uuid.uuid4())
    
    metadata = load_library_metadata()
    paper_metadata = {
        'id': paper_id,
        'name': paper_name,
        'grade': grade,
        'upload_time': datetime.now().isoformat(),
        'image_count': len(image_files),
        'status': 'completed',
        'questions': [],
        'knowledge_points': [],
        'work_mode': work_mode
    }
    metadata['papers'].append(paper_metadata)
    save_library_metadata(metadata)
    
    for idx, (filename, image_data) in enumerate(image_files):
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        image_path = os.path.join(TEST_LIBRARY_DIR, 'images', f'{paper_id}_{idx}.{ext}')
        with open(image_path, 'wb') as f:
            f.write(image_data)
    
    return {
        'success': True,
        'paper_id': paper_id,
        'total_questions': 0,
        'detected_students': 0
    }

def delete_paper(paper_id: str) -> bool:
    """删除试卷"""
    metadata = load_library_metadata()
    initial_length = len(metadata['papers'])
    metadata['papers'] = [p for p in metadata['papers'] if p['id'] != paper_id]
    
    if len(metadata['papers']) < initial_length:
        save_library_metadata(metadata)
        return True
    return False

# ========== 知识图谱 ==========

def build_knowledge_point_graph() -> Dict[str, Any]:
    """构建知识点关联图谱"""
    papers = get_all_papers()
    knowledge_relations = {}
    knowledge_mastery = {}
    
    for paper in papers:
        analysis = load_paper_analysis(paper.get('id'))
        if not analysis:
            continue
        
        for question in analysis.get('questions', []):
            for kp in question.get('knowledge_points', []):
                if kp not in knowledge_relations:
                    knowledge_relations[kp] = {'total_questions': 0, 'correct_count': 0, 'students': []}
                
                knowledge_relations[kp]['total_questions'] += 1
                if question.get('is_correct', False):
                    knowledge_relations[kp]['correct_count'] += 1
    
    for kp, data in knowledge_relations.items():
        if data['total_questions'] > 0:
            knowledge_mastery[kp] = {
                'mastery_rate': data['correct_count'] / data['total_questions'] * 100,
                'total_questions': data['total_questions'],
                'correct_count': data['correct_count']
            }
    
    return {'success': True, 'knowledge_points': knowledge_mastery, 'relations': knowledge_relations}

# ========== 班级学情分析 ==========

def analyze_class_performance(class_id: str) -> Dict[str, Any]:
    """分析班级整体学情"""
    cls = get_class_by_id(class_id)
    if not cls:
        return {'success': False, 'error': '班级不存在'}
    
    scores = get_class_scores(class_id)
    
    if not scores:
        return {'success': True, 'class_id': class_id, 'data': None}
    
    score_values = [s['score'] for s in scores]
    percentages = [s['score'] / s['total_score'] * 100 if s['total_score'] > 0 else 0 for s in scores]
    
    return {
        'success': True,
        'class_id': class_id,
        'class_name': cls['name'],
        'total_students': len(cls.get('students', [])),
        'participated': len(scores),
        'statistics': {
            'average_score': round(sum(score_values) / len(score_values), 1) if score_values else 0,
            'average_percentage': round(sum(percentages) / len(percentages), 1) if percentages else 0,
            'highest_score': max(score_values) if score_values else 0,
            'lowest_score': min(score_values) if score_values else 0,
            'pass_rate': round(sum(1 for p in percentages if p >= 60) / len(percentages) * 100, 1) if percentages else 0
        }
    }

def generate_class_report(class_id: str) -> Dict[str, Any]:
    """生成班级报告"""
    performance = analyze_class_performance(class_id)
    if not performance.get('success'):
        return performance
    
    statistics = performance.get('statistics', {})
    
    suggestions = []
    if statistics.get('average_percentage', 0) < 60:
        suggestions.append('班级整体成绩偏低，建议加强基础教学')
    if statistics.get('pass_rate', 0) < 70:
        suggestions.append('及格率有待提高，关注中下游学生')
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'class_id': class_id,
        'class_name': performance.get('class_name'),
        'statistics': statistics,
        'suggestions': suggestions,
        'participated': performance.get('participated', 0)
    }
    
    # 保存报告
    reports_dir = os.path.join(REPORTS_DIR, class_id)
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    save_json(report_path, report)
    
    return {'success': True, 'report': report}


# ========== AI 分析接口 ==========

def generate_ai_exam_report(exam_id: str) -> Dict[str, Any]:
    """生成 AI 考试分析报告"""
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {'success': False, 'error': '考试不存在'}
    
    # 构建分析数据
    question_stats = []
    for q in exam['questions']:
        correct_count = 0
        for score in exam.get('scores', []):
            for r in score.get('results', []):
                if r['number'] == q['number'] and r.get('is_correct'):
                    correct_count += 1
        total = len(exam.get('scores', []))
        question_stats.append({
            'number': q['number'],
            'type': q['type'],
            'knowledge_points': q.get('knowledge_points', []),
            'correct_count': correct_count,
            'error_count': total - correct_count,
            'error_rate': ((total - correct_count) / total * 100) if total > 0 else 0
        })
    
    knowledge_stats = {}
    for q in exam['questions']:
        for kp in q.get('knowledge_points', []):
            if kp not in knowledge_stats:
                knowledge_stats[kp] = {'total': 0, 'correct': 0}
            knowledge_stats[kp]['total'] += len(exam.get('scores', []))
    
    for score in exam.get('scores', []):
        for r in score.get('results', []):
            for kp in r.get('knowledge_points', []):
                if kp in knowledge_stats and r.get('is_correct'):
                    knowledge_stats[kp]['correct'] += 1
    
    for kp, stats in knowledge_stats.items():
        stats['mastery_rate'] = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    analysis_data = {
        'exam': exam,
        'question_stats': question_stats,
        'knowledge_stats': knowledge_stats,
        'statistics': exam.get('statistics', {})
    }
    
    report = ai_generate_exam_analysis(analysis_data)
    return {
        'success': True,
        'exam_id': exam_id,
        'ai_report': report
    }


def generate_ai_class_report(class_id: str) -> Dict[str, Any]:
    """生成 AI 班级学情分析报告"""
    performance = analyze_class_performance(class_id)
    if not performance.get('success'):
        return performance
    
    report = ai_generate_class_report(performance)
    return {
        'success': True,
        'class_id': class_id,
        'class_name': performance.get('class_name'),
        'ai_report': report
    }
