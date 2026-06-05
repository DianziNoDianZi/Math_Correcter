

# ========== 考试管理 API ==========

@app.route('/api/exams', methods=['GET'])
@track_request_stats
def get_exams():
    """获取所有考试"""
    try:
        # 初始化元数据以确保目录存在
        test_library.init_exams_metadata()
        from test_library import load_exams_metadata
        all_exams = load_exams_metadata().get('exams', [])
        
        return jsonify({'success': True, 'exams': all_exams})
    except Exception as e:
        logger.error(f'获取考试列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams', methods=['POST'])
@admin_required
def create_exam():
    """创建考试"""
    try:
        data = request.get_json() or {}
        
        result = test_library.create_exam(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f'创建考试失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>', methods=['GET'])
@track_request_stats
def get_exam(exam_id):
    """获取考试详情"""
    try:
        exam = test_library.get_exam_by_id(exam_id)
        if exam:
            return jsonify({'success': True, 'exam': exam})
        else:
            return jsonify({'success': False, 'error': '考试不存在'}), 404
    except Exception as e:
        logger.error(f'获取考试详情失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>', methods=['DELETE'])
@admin_required
def delete_exam(exam_id):
    """删除考试"""
    try:
        success = test_library.delete_exam(exam_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        logger.error(f'删除考试失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/questions', methods=['POST'])
@admin_required
def add_exam_question(exam_id):
    """添加题目到考试"""
    try:
        data = request.get_json() or {}
        
        success = test_library.add_question_to_exam(exam_id, data)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '添加失败'}), 500
    except Exception as e:
        logger.error(f'添加题目失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/ready', methods=['POST'])
@admin_required
def set_exam_ready(exam_id):
    """设置考试就绪"""
    try:
        success = test_library.set_exam_ready(exam_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '设置失败'}), 500
    except Exception as e:
        logger.error(f'设置考试就绪失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/scan', methods=['POST'])
@admin_required
def scan_exam_answer_sheets(exam_id):
    """批量扫描答题卡"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400
        
        image_files = []
        for file in files:
            if file.filename == '':
                continue
            image_files.append((file.filename, file.read()))
        
        if not image_files:
            return jsonify({'success': False, 'error': '没有有效的图片文件'}), 400
        
        result = test_library.batch_scan_answer_sheets(exam_id, image_files)
        return jsonify(result)
    except Exception as e:
        logger.error(f'扫描答题卡失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/confirm', methods=['POST'])
@admin_required
def confirm_exam(exam_id):
    """确认考试成绩"""
    try:
        result = test_library.confirm_exam_scores(exam_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f'确认成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/adjust', methods=['POST'])
@admin_required
def adjust_exam_score(exam_id):
    """调整单条成绩"""
    try:
        data = request.get_json() or {}
        student_number = data.get('student_number')
        score = data.get('score')
        
        if not student_number or score is None:
            return jsonify({'success': False, 'error': '参数不完整'}), 400
        
        result = test_library.adjust_score(exam_id, student_number, float(score))
        return jsonify(result)
    except Exception as e:
        logger.error(f'调整成绩失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exams/<exam_id>/analysis', methods=['GET'])
@track_request_stats
def get_exam_analysis(exam_id):
    """获取考试详细分析"""
    try:
        result = test_library.get_exam_analysis(exam_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f'获取考试分析失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
