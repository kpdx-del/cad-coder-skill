# 检查与改错

## 输入与动作

- 有生成脚本：优先修生成逻辑，在新输出位置重新生成，避免只改匿名尺寸块。
- 先记录采用的标准版本，按[standards.md](standards.md)核对适用差异。圆锥圆度的方向要素框格、辅助框格基准引用、版本间允许的替代形式须人工核实，不能由现有主框格的“形状公差无基准”检查直接判错。
- 有DXF：只读检查后在修订副本修改，保留原件。
- 只有截图：标出问题和依据；未知尺寸/公差不能从比例重建。需要对应DXF或参数才能精确修改。

`python scripts/drawing_checks.py input.dxf --spec parameters.json --report report.json`

`audit_annotations(msp)` 保留原来的字符串列表；`audit_drawing(msp, chains=...)` 返回包含 code、severity、entity、message、basis、suggestion 的问题。error必须修复，review需人工给依据，不能当作通过。没有给尺寸链/要素关系时会列出复核项。

`mark_annotation` 将辅助函数的说明保存在CAD_CODER XDATA，随DXF保存。导入外部文件不能凭线段猜这些信息。feature_control_frame的feature可提供kind=surface及surface_line、可选size_line；或kind=derived及size_line。目标点由target指定。

## 防止尺寸箭头被错误抑制

验收要求必须独立于生成样式。不能因为脚本设置了NONE并记录blank_ends，就自动认定该端允许没有普通尺寸箭头。先明确各端保留普通箭头，还是采用有依据的基准替代/共用；后者须另查实际替代图元、落点及方向。

对要求普通双箭头的直线尺寸，重新读取DXF后执行：

```python
required = {dim.dxf.handle: (1, 2) for dim in msp.query("DIMENSION")}
issues = audit_annotations(msp, required_arrows=required)
if issues:
    raise ValueError("\n".join(issues))
```

此示例仅适用于这些尺寸均已明确要求普通双箭头的图。合法替代端不要机械列为普通箭头要求。`audit_required_arrows(dim, required_ends=(1,2))` 检查实际端点上的箭头块、样式抑制、隐藏图层及空几何，不接受blank_ends豁免。它是生成逻辑检查，不能替代最终渲染和CAD软件内复核。回归测试应故意抑制或删除一个箭头，确认出图会被阻止；不要仅测试脚本自己生成的正常文件。

## 自动覆盖与边界

- 输入：缺项、来源字段、提议未确认、单位、上下偏差顺序。
- 原生直线尺寸：箭头实体、端部连接及非文字避让的内部断线；其他尺寸类型仍需视觉检查。
- 尺寸落点：传入witness_geometry时，检查defpoint2/defpoint3是否在声明的实际直线轮廓上。倒角前的虚拟角点不得冒充实际轮廓点。只把起点间隙设0，不能补偿错误的几何落点。
- 文字：TEXT按实际字形、MTEXT按完整分数/堆叠排版计算边界；检查文字互相重叠、轮廓/引线/箭头等穿过文字净空。尺寸MTEXT显式存储真实宽度，避免将堆叠公差摊平估宽导致错位。
- 整组布局：CAD_LAYOUT记录框格、粗糙度、剖切标识及标题栏范围；检查标题栏禁入、其他标注的线穿框、粗糙度与剖切组共线/交叉、独立引出线交叉。不存在通用全图自动求解器，复杂线型和未覆盖的关联仍需视觉复核。
- 剖切与断面：从实际图元检查共线，不仅检查方向平行；检查上下字母/符号镜像及断面名称居中。不要用两个写死的相同方向向量冒充关联检查。
- 文字方向：完整尺寸组应在水平线上方/竖直线左侧，检查净空；只有显式text_side=native才保留调用者选择的其他布局。
- 已标记框格：公差带前缀、部分项目的基准要求、基准存在性、表面/导出要素连接。
- 已声明尺寸链：循环冗余、矛盾；不给链就不猜功能。
- 倒角：辅助函数建立时检查真实倒角边共线性；有元数据的后续文件再次检查。
- 已标记紧固件：`audit_fasteners(msp)` 对带 `thread_end`/`fastener_hex_side` 元数据的图元检查结构（缺少图元、粗/细角色、半径、约270°细弧、中心偏移、sibling 互指与重复角色、外轮廓闭合与轴对齐、两面边按边界 e/4 投影位置、同组关联）。粗/细按有效线宽判断（实体覆盖优先、BYLAYER 取图层、BYBLOCK 走 review），默认 0.50/0.25 mm 不是唯一合法笔宽。只按显式 `major/minor` 校验，不按比例推断规格；不改变技术数据。中心线只记录不判定。已标记但缺关联的旧图元输出 review 供人工复核，不猜配对；完全未标记的外来DXF不推断螺栓/螺母。

框格文字宽度由实际字体计算，原始单位/偏差数据不因布局修改。任意外来DXF、不同标准版本、所有14项公差及复杂修饰符的完整语义，仍需有依据的人工复核。空问题列表不等于全部合规。

## 九类截图的回归要求

起线留白与意外断线分开；字母不能压倒角引线；外置数字在线上方；竖直数字在线左侧且箭头齐全；剖切与粗糙度分区；上下标识镜像；缺箭头与明确基准替代分开；断面与剖切位置共线；框格/引线避开标题栏。test_layout.py通过人为移动/破坏图元验证检查能报错，正常连接不得误报。

## 改错权限

字体、文字位置、明确的断线等不改变技术含义的修复可执行。公差值、配合、基准方案及功能尺寸增删须来源或确认；禁止自动“修正”为经验值。

`repair_dxf(source, output)` 提供可重复的字体样式修复，要求不同且未占用的输出路径，输出修改记录；其他问题回到脚本或有依据地编辑。不能把诊断报告称为全部问题已自动修复。修后重新开DXF、运行检查并看整图/局部。

## 尺寸链数据

```python
chains = {"shaft_axis": [
    {"start": "left", "end": "shoulder", "value": 40, "function": "locating"},
    {"start": "second_shoulder", "end": "right", "value": 35, "function": "coupling"},
    {"start": "left", "end": "right", "value": 125, "function": "overall"},
]}
```

节点是同一方向尺寸位置；value=end−start的有符号距离。参考尺寸用reference=True，不作独立制造约束，但仍校核矛盾。check_dimension_chain只报告，不自动挑选删哪个功能环。derive_difference用最坏情况区间计算，不能省掉输入偏差来源。
