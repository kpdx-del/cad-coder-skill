# 本地收口与审阅交付（最终 · 2026-11-27）

审核状态：**needs_user_visual_review**。本文件是收口清单，不自测通过代替用户目视认可。

## 可审阅文件

- 入口与说明：[README.md](../README.md)、[SKILL.md](../SKILL.md)、[implementation-status.md](implementation-status.md)、[validation.md](validation.md)、[collaboration.md](collaboration.md)。
- 零件库六类候选索引：[part-library.md](../references/part-library.md)、[catalog.json](../library/catalog.json)、[part_library.py](../scripts/part_library.py)（`list/search/show/check`）。
- 紧固件结构审图：[fasteners.py](../scripts/fasteners.py)、[drawing_checks.py](../scripts/drawing_checks.py)；FreeCAD 二维 Draft 导入/保存重开见 [freecad_import.py](../scripts/freecad_import.py)、[cad-backends.md](../references/cad-backends.md)。
- 两份演示：生成脚本 [engineering_annotations.py](../examples/engineering_annotations.py)、[fastener_views.py](../examples/fastener_views.py)；本轮输出 [examples/review-20261127/](../examples/review-20261127/)（各含 DXF/PNG/PDF/SVG，工程示例另含 parameters.json、inspection.json）。
- 预览：[docs/review-preview.png](review-preview.png)。
- 审阅包：[.local/closeout/cad-coder-skill-review-20261127-final.zip](../.local/closeout/cad-coder-skill-review-20261127-final.zip) 与 [MANIFEST-final.sha256](../.local/closeout/MANIFEST-final.sha256)（相对路径 + SHA256，84 个内容文件 + MANIFEST 自身 = 85 个 ZIP 成员）。第1轮包 [cad-coder-skill-review-20261127.zip](../.local/closeout/cad-coder-skill-review-20261127.zip) 与 `staging/` 保留未覆盖。以上 `.local/closeout/` 链接均为**仅工作副本可用**，不随 ZIP 分发。
- 移动目录重建核验（仅工作副本可用）：[.local/closeout/rebuild-verification-result.json](../.local/closeout/rebuild-verification-result.json)、重建产物与差异图在 `.local/closeout/rebuild-verification/`，不随 ZIP 分发。

## 关键改动（本轮）

1. 更新 4 份说明（README、.gitignore、docs/implementation-status.md、docs/validation.md）：写清已实现 DXF 审图、FreeCAD 二维 Draft 导入/保存重开、六类候选索引与 `list/search/show/check`、协作方式入口；把 154 项测试、41/18 项独立验收标为已实测历史记录（本轮未重跑）；如实保留未完成项并欢迎批评与可复现样例/数据集；README 明确本地无 `.git`、不冒称已保存完整 Git 历史；`.gitignore` 补 `.local/`。
2. 生成 `examples/review-20261127/` 两份演示（合成数据，姓名等留空），并新增 SVG；重读 DXF 结构审计与已声明标注检查均无报告项；生成 `docs/review-preview.png` 并更新 README 到新预览/新审阅链接。
3. 建立 `.local/closeout/` 审阅目录与白名单 ZIP（`cad-coder-skill/` + `replicas/`），产出相对路径/SHA256 清单并解包核验（84/84 匹配）；另带完整减速箱“当前修订06” DXF/FCStd/PNG/PDF 与关键局部。
4. 仅修改审阅包副本中 revision06 与 revision05 的 `D:/codex/cad-coder-integration/scripts` 三处绝对路径（revision06 两处、revision05 一处）为包内相对 `cad-coder-skill/scripts`；未改几何/尺寸，未替换旧 helper 为不同版本。

## 已验证（本轮实际执行）

- 演示生成：`python -X utf8 examples/engineering_annotations.py examples/review-20261127/engineering_annotations` 与 `python -X utf8 examples/fastener_views.py examples/review-20261127/fastener_views`；两图均通过 `doc.audit()` 结构审计；engineering_annotations 10 个尺寸、6 条引出线、`audit_drawing` 与已声明双箭头检查均无报告项；fastener_views 为无尺寸画法对照，结构审计通过。
- 归档清单：审阅包 84 个内容文件（含顶层 `审阅包说明.md`，不含 MANIFEST 自身），新解包目录全量 SHA256 比对 84/84 一致。
- 移动目录重建：在含中文与空格的新目录 `…\Temp\opencode\审阅 解包 20261127` 用包内 revision06 生成器运行，返回码 0，无 stdout/stderr；重读 DXF 结构审计通过、9 组原始标注保留、两端箭头保留。
- 历史记录（本轮未重跑）：154 项 unittest、41 项紧固件独立验收、18 项零件库独立验收，见 `.local/closeout-input/`（只读）。
- 本轮收口 Codex 另独立运行 skill `quick_validate` 通过；三份 PDF（工程示例 A3、紧固件对照 A4、整机修订06 A3）已独立渲染并目视核验，源图哈希未变；新工程示例 10 尺寸 20 箭头端、整机 9 尺寸 18 箭头端检查通过。

## 需用户目视（未自称通过）

- 重建整机 PNG 与当前修订06 **非逐像素一致**：每次渲染均出现少量灰度像素差异（本工作副本一次记录为 3307×2338 中 24229 像素、0.31%、差 1–4 灰度级；Codex 另一次独立重建记录 32927 像素、最大通道差 5/255），差异不固定，因此不把某一次像素比例当作固定指标；几何检查一致，差异图保留在 `.local/closeout/rebuild-verification/完整减速箱_修订06_重建差异.png` 供 Codex/用户目视判断，**不声称一致**。抗锯齿只是可能解释之一，未证明是唯一原因。
- 重建 DXF 与存储修订06 DXF 非逐字节一致，但已比较的可见实体与匿名尺寸块属性一致（实体类型/坐标/尺寸匿名块属性均相同）；差异仅来自保存时间戳、保存时 UUID、以及当前 `fasteners.py` 写入的紧固件关联 XDATA 比存储修订06（旧版仅有 kind/part/bearing_y）更丰富（role/group/faces/centerline 等）。即元数据差异，非几何差异，不宣称“几何逐字节一致”。
- 完整减速箱“当前修订06”为 NTS 教学复绘，未指定轴承型号，未获用户视觉认可，不是制造图；FCStd 沿用原已保存重开检查，不冒充本轮 GUI 编辑验证。
- 字体：工程标注示例 `engineering_annotations.py` 用默认 ISOCP + 仿宋；紧固件画法对照 `fastener_views.py` 显式 `new_doc(font='times.ttf')`，装配复绘在 `revision-03/revise_known.py` 显式将 CAD_TEXT 覆写为 Times（衬线）以贴近参考图——后两者属显式例外，**不声称所有示例数字均 ISOCP、不声称所有字体完全合规**。字体缺失时生成器明确报错，不换字体、不打包字体。

## 未实现（如实保留）

六类候选索引正式尺寸表未核验、不是六套自动生成器；不能杜绝任意漏箭头/图元重叠；FreeCAD GUI 手工编辑与 SolidWorks 2023 原生草图/特征树/装配关系未验证；工作副本未同步安装版、未发布；按视图增量重建、3D转2D、装配拆件与 2D 反建 3D 属后续阶段。欢迎提供批评与可复现样例/数据集（含真实 DXF/位图与预期检查结果）。

## 完整整机与两份演示入口

- 完整减速箱“当前修订06”：`replicas/revision-06/`（审阅包内）DXF/FCStd/PNG/PDF + 螺栓侧视/止口配合局部；确切重建命令见审阅包顶层 `审阅包说明.md`（包内读者入口）。重建产物见 `.local/closeout/rebuild-verification/`（仅工作副本可用，不随 ZIP 分发）。
- 演示一（工程标注）：`examples/review-20261127/engineering_annotations/`（审阅包内 `cad-coder-skill/` 下）。
- 演示二（紧固件画法对照）：`examples/review-20261127/fastener_views/`（审阅包内 `cad-coder-skill/` 下）。

包内读者：从顶层 `审阅包说明.md` 出发，先看 `cad-coder-skill/README.md` 与两份示例脚本，再进 `replicas/revision-06/` 复现整机；包内**不含** `.local` 日志/ZIP/重建报告，也不含历史原始测试日志。
