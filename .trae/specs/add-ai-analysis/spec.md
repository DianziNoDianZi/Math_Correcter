# AI 智能分析 Spec

## Why
当前学情分析模块仅提供基础统计（平均分、及格率、最高/最低分），教师建议也只是基于固定阈值（如"平均分<60→建议加强基础教学"）。项目已有完整的 LLM 调用基础设施（`processor.call_llm_api`、`config.py` 模型配置），但分析模块完全没有接入 AI 能力。添加 AI 分析后，教师可以获得针对每次考试、每个班级、每个学生的深度分析报告和教学建议。

## What Changes
- 新增 `app/services/ai_analysis_service.py` AI 分析服务模块
- 考试分析接口返回 AI 生成的综合分析报告
- 班级分析接口返回 AI 生成的班级学情报告
- 前端分析页面展示 AI 分析报告（含 loading 状态和降级处理）
- 复用已有的 `processor.call_llm_api` 和 `config.py` 的 `text_model` 配置
- AI 不可用时优雅降级为纯统计展示
- **BREAKING**: 无，所有改动向后兼容

## Impact
- Affected specs: `add-ai-scanning`（互补关系，扫描+分析形成完整 AI 闭环）
- Affected code: `test_library.py`（增强分析函数）、`app/services/ai_analysis_service.py`（新增）、`templates/teacher.html`（前端展示）
- 新增文件: `app/services/ai_analysis_service.py`

## ADDED Requirements

### Requirement: AI 考试分析报告
系统 SHALL 支持使用配置的文本模型根据考试数据生成综合分析报告。

#### Scenario: 生成考试分析报告
- **WHEN** 教师查看已完成考试的分析页面
- **AND** `config.yaml` 中已配置 `text_model`
- **THEN** 系统调用文本模型生成包含以下内容的分析报告：
  - 整体表现概述
  - 高频错误题分析
  - 薄弱知识点诊断
  - 教学改进建议
- **AND** 报告以结构化 Markdown 格式呈现

#### Scenario: AI 不可用时降级
- **WHEN** `text_model` 未配置或 AI 调用失败
- **THEN** 系统仅展示基础统计数据
- **AND** 不显示 AI 分析报告区域
- **AND** 不影响其他分析功能

#### Scenario: 无成绩数据
- **WHEN** 考试尚未有任何成绩
- **THEN** 不触发 AI 分析
- **AND** 展示"暂无成绩数据"提示

### Requirement: AI 班级学情分析
系统 SHALL 支持使用 AI 分析班级整体学情。

#### Scenario: 班级报告生成
- **WHEN** 教师查看班级详情
- **AND** 该班级有已完成考试
- **THEN** 系统调用 AI 生成班级学情报告：
  - 班级整体水平评估
  - 共性错误分析
  - 分层教学建议（优等生/中等生/后进生）
  - 下阶段教学重点建议

#### Scenario: 无班级数据
- **WHEN** 班级没有考试记录
- **THEN** 不触发 AI 分析

### Requirement: AI 分析结果缓存
系统 SHALL 缓存 AI 分析结果，避免重复调用。

#### Scenario: 缓存命中
- **WHEN** 考试数据未变化且已有缓存的分析报告
- **THEN** 直接返回缓存结果
- **AND** 不重新调用 AI

#### Scenario: 数据变更后刷新
- **WHEN** 考试成绩被修改（新增/调整/确认）
- **THEN** 清除对应考试的分析缓存
- **AND** 下次访问时重新生成

### Requirement: 前端 AI 分析展示
系统 SHALL 在分析页面展示 AI 生成的分析报告。

#### Scenario: 加载中状态
- **WHEN** AI 分析正在生成中
- **THEN** 显示 loading 动画和"AI 正在分析中..."提示

#### Scenario: 分析报告展示
- **WHEN** AI 分析完成
- **THEN** 以卡片形式展示结构化报告
- **AND** 支持 Markdown 渲染（标题、列表、加粗等）
- **AND** 标注"AI 生成"以区别于统计图表

#### Scenario: 降级状态
- **WHEN** AI 不可用
- **THEN** 隐藏 AI 报告区域
- **AND** 仅展示基础统计图表
- **AND** 不显示错误信息