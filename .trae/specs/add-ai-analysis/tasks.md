# Tasks

- [x] Task 1: 创建 AI 分析服务模块 `app/services/ai_analysis_service.py`
  - 封装从 config.yaml 读取 `text_model` 配置的逻辑
  - 实现 `_is_ai_available()` 检查 AI 是否可用
  - 实现 `generate_exam_analysis(exam_data)` 根据考试数据生成 AI 分析报告
  - 实现 `generate_class_report(class_data)` 根据班级数据生成 AI 学情报告
  - 实现分析结果缓存机制（`_get_cache` / `_set_cache` / `_invalidate_cache`）
  - 实现优雅降级：AI 不可用时返回 None 而非报错
  - **验证**: 单独运行测试，模拟 AI 可用和不可用两种场景

- [x] Task 2: 增强 `test_library.py` 的分析函数，接入 AI 分析
  - `get_exam_analysis` 返回结果中增加 `ai_report` 字段
  - 新增 `generate_ai_exam_report(exam_id)` 函数，调用 AI 分析服务
  - 新增 `generate_ai_class_report(class_id)` 函数，调用 AI 分析服务
  - 当成绩数据变更（add_score / adjust_score / confirm_scores）时清除缓存
  - **验证**: 分析接口返回数据包含 `ai_report` 字段

- [x] Task 3: 添加 AI 分析 API 路由
  - 在 `exam_routes.py` 添加 `GET /api/exams/<exam_id>/ai-report` 路由
  - 在 `class_routes.py` 添加 `GET /api/classes/<class_id>/ai-report` 路由
  - 返回 `ai_report` 字段（或 `null` 表示 AI 不可用）
  - **验证**: curl 测试两个新路由返回正确数据

- [x] Task 4: 前端分析页面展示 AI 报告
  - 在 teacher.html 的学情分析区域添加 AI 报告展示卡片
  - 实现 loading 状态（AI 分析中动画）
  - 实现 Markdown 渲染（使用简单的 Markdown 转 HTML）
  - 降级状态：AI 不可用时隐藏报告区域
  - 标注"AI 生成"标签
  - **验证**: 打开分析页面能看到 AI 报告卡片（有 AI 时）或隐藏（无 AI 时）

- [x] Task 5: 班级详情页添加 AI 分析入口
  - 在 teacher.html 班级详情模态框中添加"AI 学情分析"按钮
  - 点击后展示 AI 生成的班级报告
  - 支持 loading 和降级状态
  - **验证**: 打开班级详情，点击 AI 分析按钮能正常展示

# Task Dependencies
- Task 2 依赖 Task 1（AI 分析服务模块需要先创建）
- Task 3 依赖 Task 2（路由需要调用增强后的分析函数）
- Task 4 依赖 Task 3（前端需要后端 API 支持）
- Task 5 依赖 Task 3（班级分析需要后端 API 支持）
- Task 4 和 Task 5 可并行开发