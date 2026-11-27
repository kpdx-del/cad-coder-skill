# 首期实施记录（2026-11-27）

工作副本中已实现：兼容原render调用的`render_many`；带源文件、字体、渲染器及输出哈希校验的多格式缓存；短JSON任务入口；使用独立配置与ASCII临时输入的FreeCAD现代Draft导入（二维Draft导入/保存重开已验证，非三维特征树）；原件和已有输出保护；紧固件结构审图（显式标记图元的螺纹端视/六角侧视关联，保存重开后检出缺图元、粗细/半径错误、弧角、中心偏移、轮廓未闭合、面边缺失及关联断裂）；六类二维零件候选索引（螺栓、螺母、垫圈、单列圆锥滚子轴承、平键、隔套）与 `list/search/show/check` CLI。

协作分工见 [collaboration.md](collaboration.md)（Codex 拆分与独立审查，OpenCode+DeepSeek V4 Pro 实施；最多三轮、不递归委派）。

## 已实测历史记录（本轮未重跑）

Codex 独立运行 154 项 `python -X utf8 -m unittest discover -s tests -v` 全部通过（日志 `.local/closeout-input/codex-library-full-tests.log`）；紧固件 41 项变异/几何保持独立验收通过（`.local/closeout-input/independent-acceptance.json`）；零件库 18 项黑盒/语义独立验收通过（`.local/closeout-input/library-independent-results.json`）。以上 154/41/18 为既有历史记录，本轮收口未无理由重跑全套。本轮收口 Codex 另独立运行 skill `quick_validate` 通过，三份 PDF 已独立渲染并目视核验（页幅分别 A3/A4/A3）、源图哈希未变，新工程示例 10 尺寸 20 箭头端、整机 9 尺寸 18 箭头端检查通过；本轮新增验证为演示生成、归档清单、移动目录重建与图元/图像核验（见 [closeout-review.md](closeout-review.md)）。

FreeCAD 1.1.4保存后重开当前修订06，634个对象、24个文字对象和9个尺寸对象（历史记录）。FreeCAD可编辑二维Draft导入/保存重开不等于三维特征树，尚未验证GUI显示和手工编辑后的重生成，不能将此等同三维参数化。

单张当前DXF同时输出PNG/PDF首次耗时3.937秒；相同内容、字体和配置的5次已校验输出复用中位耗时0.206秒。这两项是特定历史条件下的测量，不是本轮实测，也不是整体工作流提速比例或token比例；无真实token用量数据。

SolidWorks安装文件为31.5.0.0052（2023 SP5）。限制环境内COM报E_ACCESSDENIED，环境外能激活COM对象但ISldWorks接口QueryInterface失败，报0x80029C4A TYPE_E_CANTLOADLIBRARY。因此尚未创建、验证SLDPRT原生特征样例，也未修改软件注册或安装。

## 修订06与收口

当前图纸修订06仍为NTS（非比例）教学复绘，另存于本地审阅目录，未充当公开的正确教材数据集，未获本轮用户视觉通过，未发布。已调整端部单圆头键、细点画分度线、局部剖开与闷盖部分剖面；φ100H7/f9记录箱体孔/端盖止口界面。箭头检查和局部材料正反例点检查通过，仍待用户视觉验收。收口审阅清单见 [closeout-review.md](closeout-review.md)，审阅包见 `.local/closeout/`。

## 尚未完成（如实保留）

六类候选索引的正式尺寸表未核验、不是六套自动生成器；不能杜绝任意漏箭头/图元重叠；GUI 手工编辑及 SolidWorks2023 原生草图/特征树/装配关系未验证；工作副本未同步安装版、未发布；按视图增量重建、3D转2D、装配拆件和2D反建3D属于后续阶段，当前无能力声明。欢迎提供批评与可复现样例/数据集（含真实 DXF/位图与预期检查结果）。
