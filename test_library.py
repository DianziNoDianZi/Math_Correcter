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

# ========== 批量上传分析 ==========

def batch_analyze_papers(image_files: List[Tuple[str, bytes]], 
                         grade: str, 
                         paper_name: str,
                         concurrency: int = 4) -> Dict[str, Any]:
    """批量分析试卷"""
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
        'knowledge_points': []
    }
    metadata['papers'].append(paper_metadata)
    save_library_metadata(metadata)
    
    # 保存图片文件
    for idx, (filename, image_data) in enumerate(image_files):
        ext = filename.split('.')[-1] if '.' in filename else 'jpg'
        image_path = os.path.join(TEST_LIBRARY_DIR, 'images', f'{paper_id}_{idx}.{ext}')
        with open(image_path, 'wb') as f:
            f.write(image_data)
    
    # 异步分析 - 这里简化为同步处理
    all_questions = []
    knowledge_points = set()
    
    # 这里简化处理，实际应该使用LLM进行分析
    # 为了演示，我们创建模拟数据
    for idx in range(len(image_files)):
        num_questions = 3 + idx % 3  # 模拟每卷3-5题
        for q_idx in range(num_questions):
            question = {
                'id': str(uuid.uuid4()),
                'content': f'第{q_idx+1}题：示例题目内容',
                'is_correct': (q_idx % 2 == 0),  # 模拟正确率
                'knowledge_points': ['示例知识点1', '示例知识点2'][(q_idx % 2):(q_idx % 2 + 1)],
                'error_type': '计算错误' if q_idx % 2 != 0 else None,
                'difficulty': '中等'
            }
            all_questions.append(question)
            knowledge_points.update(question['knowledge_points'])
    
    # 更新试卷数据
    paper_metadata['questions'] = all_questions
    paper_metadata['knowledge_points'] = list(knowledge_points)
    paper_metadata['status'] = 'completed'
    paper_metadata['total_questions'] = len(all_questions)
    paper_metadata['correct_count'] = sum(1 for q in all_questions if q.get('is_correct', False))
    
    save_library_metadata(metadata)
    save_paper_analysis(paper_id, paper_metadata)
    
    return {
        'success': True,
        'paper_id': paper_id,
        'total_questions': len(all_questions)
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
