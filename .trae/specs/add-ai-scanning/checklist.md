# Checklist

- [x] `app/services/ai_scan_service.py` 文件存在且可导入
- [x] `ai_scan_service.py` 能正确读取 `config.yaml` 中的 `vision_model` 配置
- [x] AI 可用时 `detect_student_number` 调用视觉模型返回识别结果
- [x] AI 不可用时 `detect_student_number` 降级为文件名正则提取
- [x] AI 可用时 `detect_answers` 调用视觉模型返回 JSON 格式答案映射
- [x] AI 不可用时 `detect_answers` 返回空字典（所有题目留空）
- [x] 扫描产生的成绩数据包含 `ai_scanned` 字段
- [x] 手动录入的成绩数据 `ai_scanned` 为 false
- [x] teacher.html 审核页能区分显示 AI 识别和手动录入的行
- [x] 现有扫描流程测试（文件名提取学号）不受影响
- [x] 完整端到端流程（创建考试 -> 添加题目 -> 上传 -> 扫描 -> 审核）可正常运行