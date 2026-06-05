# -*- coding: utf-8 -*-
"""试卷库管理和分析模块：批量上传、分析、知识点统计和提示词优化。"""
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

def init_library_directories():
    """初始化试卷库目录"""
    for dir_name in ['images', 'analyses', 'exports']:
        path = os.path.join(TEST_LIBRARY_DIR, dir_name)
        os.makedirs(path, exist_ok=True)

def get_library_metadata_path():
    """获取试卷库元数据文件路径"""
    return os.path.join(TEST_LIBRARY_DIR, 'library_metadata.json')

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

def analyze_single_image(base64_image: str, grade: str) -> Dict[str, Any]:
    """分析单张试卷图片"""
    try:
        # 使用视觉模型提取内容
        vision_model = processor._load_config().get('vision_model', '')
        text_model = processor._load_config().get('text_model', '')
        
        if not vision_model or not text_model:
            return {
                'success': False,
                'error': '模型未配置'
            }
        
        extracted_content = processor.call_llm_api(
            vision_model,
            [{"role": "user", "content": processor.FIRST_PROMPT}],
            image_url=base64_image
        )
        
        # 分析知识点
        analysis_prompt = f"""请分析以下数学题目，提取详细信息。学生年级是{grade}。

请按以下JSON格式返回（不要Markdown标记，只返回纯JSON）：
{{
    "questions": [
        {{
            "content": "题目内容",
            "answer": "学生答案",
            "correct_answer": "正确答案",
            "is_correct": true/false,
            "knowledge_points": ["知识点1", "知识点2"],
            "difficulty": "简单/中等/困难",
            "question_type": "选择题/填空题/解答题/证明题",
            "error_type": "概念错误/计算错误/审题错误/格式错误/其他（如正确）"
        }}
    ],
    "summary": {{
        "total_questions": 总数,
        "correct_count": 正确数量,
        "accuracy_rate": 正确率,
        "main_knowledge_gaps": ["主要知识缺陷1", "主要知识缺陷2"]
    }}
}}

题目内容：
{extracted_content}
"""
        
        analysis_result = processor.call_llm_api(
            text_model,
            [{"role": "user", "content": analysis_prompt}]
        )
        
        # 尝试解析JSON
        try:
            cleaned_result = analysis_result.strip()
            if cleaned_result.startswith('```json'):
                cleaned_result = cleaned_result[7:]
            if cleaned_result.startswith('```'):
                cleaned_result = cleaned_result[3:]
            if cleaned_result.endswith('```'):
                cleaned_result = cleaned_result[:-3]
            
            analysis_data = json.loads(cleaned_result)
            return {
                'success': True,
                'extracted': extracted_content,
                'analysis': analysis_data
            }
        except Exception as e:
            return {
                'success': True,
                'extracted': extracted_content,
                'analysis': None,
                'parse_error': str(e)
            }
            
    except Exception as e:
        logger.error(f'Error analyzing image: {e}')
        return {
            'success': False,
            'error': str(e)
        }

def batch_analyze_papers(
    image_files: List[Tuple[str, bytes]],  # (filename, bytes_data)
    grade: str,
    paper_name: str,
    concurrency: int = 4
) -> Dict[str, Any]:
    """批量分析试卷图片"""
    paper_id = str(uuid.uuid4())[:8]
    
    # 保存元数据
    metadata = load_library_metadata()
    
    paper_metadata = {
        'id': paper_id,
        'name': paper_name,
        'grade': grade,
        'upload_time': datetime.now().isoformat(),
        'image_count': len(image_files),
        'status': 'analyzing',
        'total_questions': 0,
        'correct_count': 0,
        'accuracy_rate': 0
    }
    metadata['papers'].append(paper_metadata)
    save_library_metadata(metadata)
    
    # 保存图片
    image_paths = []
    for i, (filename, image_bytes) in enumerate(image_files):
        ext = filename.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
            ext = 'png'
        image_filename = f'{paper_id}_{i:03d}.{ext}'
        image_path = os.path.join(TEST_LIBRARY_DIR, 'images', image_filename)
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        image_paths.append(image_path)
    
    # 批量分析
    all_questions = []
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        for image_path in image_paths:
            with open(image_path, 'rb') as f:
                base64_image = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            future = executor.submit(analyze_single_image, base64_image, grade)
            futures[future] = image_path
        
        for future in as_completed(futures):
            image_path = futures[future]
            try:
                result = future.result()
                if result['success'] and result.get('analysis'):
                    all_questions.extend(result['analysis'].get('questions', []))
                    success_count += 1
            except Exception as e:
                logger.error(f'Error analyzing {image_path}: {e}')
    
    # 统计结果
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    accuracy_rate = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # 保存完整分析
    paper_analysis = {
        'id': paper_id,
        'name': paper_name,
        'grade': grade,
        'upload_time': paper_metadata['upload_time'],
        'total_questions': total_questions,
        'correct_count': correct_count,
        'accuracy_rate': accuracy_rate,
        'questions': all_questions,
        'knowledge_points': analyze_knowledge_points(all_questions),
        'error_types': analyze_error_types(all_questions)
    }
    
    save_paper_analysis(paper_id, paper_analysis)
    
    # 更新元数据
    metadata = load_library_metadata()
    for p in metadata['papers']:
        if p['id'] == paper_id:
            p['status'] = 'completed'
            p['total_questions'] = total_questions
            p['correct_count'] = correct_count
            p['accuracy_rate'] = accuracy_rate
            break
    metadata['total_questions'] += total_questions
    save_library_metadata(metadata)
    
    return {
        'paper_id': paper_id,
        'success': True,
        'analyzed_count': success_count,
        'total_questions': total_questions,
        'accuracy_rate': accuracy_rate
    }

def analyze_knowledge_points(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析知识点统计"""
    kp_counter = Counter()
    kp_mastery = {}
    
    for q in questions:
        kps = q.get('knowledge_points', [])
        is_correct = q.get('is_correct', False)
        
        for kp in kps:
            kp_counter[kp] += 1
            if kp not in kp_mastery:
                kp_mastery[kp] = {'correct': 0, 'total': 0}
            kp_mastery[kp]['total'] += 1
            if is_correct:
                kp_mastery[kp]['correct'] += 1
    
    result = []
    for kp, count in kp_counter.most_common():
        mastery = kp_mastery[kp]
        result.append({
            'knowledge_point': kp,
            'appearance_count': count,
            'correct_count': mastery['correct'],
            'mastery_rate': (mastery['correct'] / mastery['total'] * 100) if mastery['total'] > 0 else 0
        })
    
    return result

def analyze_error_types(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """分析错误类型统计"""
    error_counter = Counter()
    
    for q in questions:
        error_type = q.get('error_type', '其他')
        if not q.get('is_correct', False):
            error_counter[error_type] += 1
    
    result = []
    total_errors = sum(error_counter.values())
    for error_type, count in error_counter.most_common():
        result.append({
            'error_type': error_type,
            'count': count,
            'percentage': (count / total_errors * 100) if total_errors > 0 else 0
        })
    
    return result

def generate_prompt_optimization_suggestions(
    paper_ids: Optional[List[str]] = None,
    grade: Optional[str] = None
) -> Dict[str, Any]:
    """生成提示词优化建议"""
    metadata = load_library_metadata()
    
    # 收集所有题目
    all_questions = []
    target_papers = paper_ids if paper_ids else [p['id'] for p in metadata['papers']]
    
    for paper_id in target_papers:
        analysis = load_paper_analysis(paper_id)
        if analysis and analysis.get('questions'):
            all_questions.extend(analysis['questions'])
    
    if grade:
        target_papers = [p['id'] for p in metadata['papers'] if p.get('grade') == grade]
    
    if not all_questions:
        return {
            'success': False,
            'error': '没有可分析的数据'
        }
    
    # 分析统计
    knowledge_analysis = analyze_knowledge_points(all_questions)
    error_analysis = analyze_error_types(all_questions)
    
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    overall_accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0
    
    # 生成优化建议
    suggestions = []
    
    # 知识点优化建议
    weak_points = [kp for kp in knowledge_analysis if kp['mastery_rate'] < 60][:5]
    if weak_points:
        suggestions.append({
            'category': '知识点',
            'priority': '高',
            'suggestion': f"针对薄弱知识点：{', '.join([kp['knowledge_point'] for kp in weak_points])}，建议在提示词中增加这些知识点的详细讲解和常见错误提醒。"
        })
    
    # 错误类型优化建议
    common_errors = error_analysis[:3]
    if common_errors:
        error_desc = '，'.join([f"{e['error_type']}({e['percentage']:.0f}%)" for e in common_errors])
        suggestions.append({
            'category': '错误类型',
            'priority': '高',
            'suggestion': f"常见错误类型：{error_desc}，建议在提示词中特别强调避免这些错误，并增加相应的检查步骤。"
        })
    
    # 题型分布建议
    question_types = Counter()
    for q in all_questions:
        qt = q.get('question_type', '未知')
        question_types[qt] += 1
    
    main_types = [t for t, _ in question_types.most_common(3)]
    suggestions.append({
        'category': '题型适配',
        'priority': '中',
        'suggestion': f"主要题型：{', '.join(main_types)}，建议在提示词中针对这些题型优化批改方式和评分标准。"
    })
    
    # 整体风格建议
    if overall_accuracy < 50:
        suggestions.append({
            'category': '鼓励风格',
            'priority': '中',
            'suggestion': "整体正确率较低，建议采用更鼓励性的教学风格，增加正面反馈和循序渐进的学习建议。"
        })
    
    # 生成优化后的提示词
    optimized_prompt = generate_optimized_prompt(
        weak_points, 
        common_errors, 
        main_types, 
        overall_accuracy,
        grade
    )
    
    return {
        'success': True,
        'statistics': {
            'total_papers': len(target_papers),
            'total_questions': total_questions,
            'overall_accuracy': overall_accuracy,
            'knowledge_analysis': knowledge_analysis[:10],
            'error_analysis': error_analysis
        },
        'suggestions': suggestions,
        'optimized_prompt': optimized_prompt
    }

def generate_optimized_prompt(
    weak_points: List[Dict[str, Any]],
    common_errors: List[Dict[str, Any]],
    main_types: List[str],
    overall_accuracy: float,
    grade: Optional[str] = None
) -> str:
    """生成优化后的提示词"""
    grade_desc = f"{grade}学生" if grade else "学生"
    
    weak_point_desc = "\n".join([
        f"- {kp['knowledge_point']}: 掌握率 {kp['mastery_rate']:.0f}%" 
        for kp in weak_points[:5]
    ]) if weak_points else "暂未发现明显薄弱知识点"
    
    error_desc = "\n".join([
        f"- {e['error_type']}: {e['percentage']:.0f}%" 
        for e in common_errors[:3]
    ]) if common_errors else "暂未发现特定错误类型"
    
    style = "非常耐心和鼓励性" if overall_accuracy < 50 else "鼓励性"
    
    return f"""你是一位{style}的{grade_desc}数学辅导老师。

## 重点关注的薄弱知识点：
{weak_point_desc}

## 常见错误类型：
{error_desc}

## 主要题型：
{', '.join(main_types)}

## 批改要求：
1. 对于薄弱知识点的题目，要特别仔细检查并给出详细的讲解
2. 注意避免{[e['error_type'] for e in common_errors[:2]]}等常见错误
3. 用温和的语气指出错误，用具体的步骤说明如何改进
4. 每个题目的批改都要包括：总体评价、亮点指出、得分、错误分析、正确解答、学习建议

现在，请根据这些要求批改以下题目：
"""

def delete_paper(paper_id: str) -> bool:
    """删除试卷"""
    try:
        # 删除图片
        for filename in os.listdir(os.path.join(TEST_LIBRARY_DIR, 'images')):
            if filename.startswith(f'{paper_id}_'):
                filepath = os.path.join(TEST_LIBRARY_DIR, 'images', filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
        
        # 删除分析
        analysis_path = os.path.join(TEST_LIBRARY_DIR, 'analyses', f'{paper_id}.json')
        if os.path.exists(analysis_path):
            os.remove(analysis_path)
        
        # 更新元数据
        metadata = load_library_metadata()
        removed_questions = 0
        for paper in metadata['papers']:
            if paper['id'] == paper_id:
                removed_questions = paper.get('total_questions', 0)
                break
        metadata['papers'] = [p for p in metadata['papers'] if p['id'] != paper_id]
        metadata['total_questions'] = max(0, metadata['total_questions'] - removed_questions)
        save_library_metadata(metadata)
        
        return True
    except Exception as e:
        logger.error(f'Failed to delete paper {paper_id}: {e}')
        return False

def export_library_statistics() -> Dict[str, Any]:
    """导出整个试卷库的统计数据"""
    metadata = load_library_metadata()
    
    all_questions = []
    for paper in metadata['papers']:
        analysis = load_paper_analysis(paper['id'])
        if analysis and 'questions' in analysis:
            all_questions.extend(analysis['questions'])
    
    total_questions = len(all_questions)
    correct_count = sum(1 for q in all_questions if q.get('is_correct', False))
    
    return {
        'total_papers': len(metadata['papers']),
        'total_questions': total_questions,
        'correct_count': correct_count,
        'overall_accuracy': (correct_count / total_questions * 100) if total_questions > 0 else 0,
        'knowledge_analysis': analyze_knowledge_points(all_questions),
        'error_analysis': analyze_error_types(all_questions),
        'papers': [
            {
                'id': p['id'],
                'name': p['name'],
                'grade': p.get('grade', ''),
                'total_questions': p.get('total_questions', 0),
                'accuracy_rate': p.get('accuracy_rate', 0),
                'upload_time': p.get('upload_time', '')
            }
            for p in metadata['papers']
        ]
    }

# 错题整理功能
def get_all_wrong_questions(paper_ids: Optional[List[str]] = None, 
                            grade: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取所有错题"""
    metadata = load_library_metadata()
    target_papers = paper_ids if paper_ids else [p['id'] for p in metadata['papers']]
    
    if grade:
        target_papers = [p['id'] for p in metadata['papers'] if p.get('grade') == grade]
    
    all_wrong_questions = []
    
    for paper_id in target_papers:
        analysis = load_paper_analysis(paper_id)
        if analysis and analysis.get('questions'):
            paper_name = analysis.get('name', '未知试卷')
            for i, question in enumerate(analysis['questions']):
                if not question.get('is_correct', True):
                    question_copy = question.copy()
                    question_copy['paper_id'] = paper_id
                    question_copy['paper_name'] = paper_name
                    question_copy['question_index'] = i
                    all_wrong_questions.append(question_copy)
    
    return all_wrong_questions

def get_wrong_questions_by_knowledge_point(knowledge_point: str) -> List[Dict[str, Any]]:
    """按知识点获取错题"""
    wrong_questions = get_all_wrong_questions()
    return [q for q in wrong_questions if knowledge_point in q.get('knowledge_points', [])]

# 搜索和筛选功能
def search_questions(keyword: str, 
                     paper_ids: Optional[List[str]] = None,
                     knowledge_point: Optional[str] = None,
                     question_type: Optional[str] = None,
                     is_correct: Optional[bool] = None) -> List[Dict[str, Any]]:
    """搜索题目"""
    metadata = load_library_metadata()
    target_papers = paper_ids if paper_ids else [p['id'] for p in metadata['papers']]
    
    all_questions = []
    keyword_lower = keyword.lower()
    
    for paper_id in target_papers:
        analysis = load_paper_analysis(paper_id)
        if analysis and analysis.get('questions'):
            paper_name = analysis.get('name', '未知试卷')
            for i, question in enumerate(analysis['questions']):
                question_copy = question.copy()
                question_copy['paper_id'] = paper_id
                question_copy['paper_name'] = paper_name
                question_copy['question_index'] = i
                
                # 检查搜索条件
                match = True
                
                if keyword:
                    content = question_copy.get('content', '')
                    if keyword_lower not in content.lower():
                        match = False
                
                if knowledge_point and knowledge_point not in question_copy.get('knowledge_points', []):
                    match = False
                
                if question_type and question_type != question_copy.get('question_type'):
                    match = False
                
                if is_correct is not None and is_correct != question_copy.get('is_correct'):
                    match = False
                
                if match:
                    all_questions.append(question_copy)
    
    return all_questions

def get_all_knowledge_points(paper_ids: Optional[List[str]] = None) -> List[str]:
    """获取所有出现过的知识点"""
    metadata = load_library_metadata()
    target_papers = paper_ids if paper_ids else [p['id'] for p in metadata['papers']]
    
    knowledge_points = set()
    
    for paper_id in target_papers:
        analysis = load_paper_analysis(paper_id)
        if analysis and analysis.get('knowledge_points'):
            for kp in analysis['knowledge_points']:
                knowledge_points.add(kp['knowledge_point'])
    
    return sorted(list(knowledge_points))

# 标签系统
def update_paper_tags(paper_id: str, tags: List[str]) -> bool:
    """更新试卷标签"""
    metadata = load_library_metadata()
    
    found = False
    for paper in metadata['papers']:
        if paper['id'] == paper_id:
            paper['tags'] = tags
            found = True
            break
    
    if found:
        save_library_metadata(metadata)
        return True
    return False

def get_papers_by_tag(tag: str) -> List[Dict[str, Any]]:
    """按标签获取试卷"""
    metadata = load_library_metadata()
    return [p for p in metadata['papers'] if tag in p.get('tags', [])]

def get_all_tags() -> List[str]:
    """获取所有标签"""
    metadata = load_library_metadata()
    all_tags = set()
    for paper in metadata['papers']:
        all_tags.update(paper.get('tags', []))
    return sorted(list(all_tags))

# 导出功能
def export_questions_to_json(questions: List[Dict[str, Any]], paper_name: str = "导出题目") -> str:
    """导出题目为JSON格式"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{paper_name}_{timestamp}.json"
    filepath = os.path.join(TEST_LIBRARY_DIR, 'exports', filename)
    
    export_data = {
        'paper_name': paper_name,
        'export_time': datetime.now().isoformat(),
        'total_questions': len(questions),
        'questions': questions
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    return filename

def generate_wrong_questions_practice(paper_ids: Optional[List[str]] = None, 
                                     max_questions: int = 50) -> Dict[str, Any]:
    """生成错题练习"""
    wrong_questions = get_all_wrong_questions(paper_ids)
    
    # 随机选取一些题目（如果超过 max_questions）
    import random
    if len(wrong_questions) > max_questions:
        selected_questions = random.sample(wrong_questions, max_questions)
    else:
        selected_questions = wrong_questions
    
    # 按知识点分组
    by_knowledge = {}
    for q in selected_questions:
        kps = q.get('knowledge_points', ['未知知识点'])
        for kp in kps:
            if kp not in by_knowledge:
                by_knowledge[kp] = []
            by_knowledge[kp].append(q)
    
    return {
        'total_wrong': len(wrong_questions),
        'selected_count': len(selected_questions),
        'by_knowledge_point': by_knowledge,
        'questions': selected_questions
    }

# 知识点关系图谱
def build_knowledge_point_graph() -> Dict[str, Any]:
    """构建知识点关联图谱"""
    metadata = load_library_metadata()
    all_papers = metadata['papers']
    
    # 知识点共同出现频率
    cooccurrence = Counter()
    kp_to_papers = {}
    
    for paper_id in [p['id'] for p in all_papers]:
        analysis = load_paper_analysis(paper_id)
        if not analysis or not analysis.get('questions'):
            continue
            
        for question in analysis['questions']:
            kps = sorted(question.get('knowledge_points', []))
            for i in range(len(kps)):
                for j in range(i+1, len(kps)):
                    key = tuple(sorted([kps[i], kps[j]]))
                    cooccurrence[key] += 1
    
    # 获取所有知识点的统计
    all_knowledge_points = get_all_knowledge_points()
    kp_stats = []
    
    for kp in all_knowledge_points:
        all_questions_with_kp = []
        for paper_id in [p['id'] for p in all_papers]:
            analysis = load_paper_analysis(paper_id)
            if analysis:
                for q in analysis.get('questions', []):
                    if kp in q.get('knowledge_points', []):
                        all_questions_with_kp.append(q)
        
        total = len(all_questions_with_kp)
        correct = sum(1 for q in all_questions_with_kp if q.get('is_correct', False))
        mastery_rate = (correct / total * 100) if total > 0 else 0
        
        kp_stats.append({
            'name': kp,
            'appearance_count': total,
            'mastery_rate': mastery_rate
        })
    
    # 构建节点和边
    nodes = [{'id': kp['name'], 'masteryRate': kp['mastery_rate'], 
             'count': kp['appearance_count']} for kp in kp_stats]
    edges = [{'source': pair[0], 'target': pair[1], 'weight': count} 
             for pair, count in cooccurrence.most_common()]
    
    return {
        'nodes': nodes,
        'edges': edges,
        'statistics': kp_stats
    }

# 初始化
init_library_directories()
