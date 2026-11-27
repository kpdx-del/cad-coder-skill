---
name: cad-coder
description: Generate and correct editable mechanical DXF drawings, export 2D FreeCAD documents, and inspect CAD backend capabilities. Use for dimensions, tolerances, datums, roughness, screenshot/DXF diagnosis and cached multi-format previews. Ask for missing technical parameters; never invent manufacturing data. SolidWorks parametric modeling is not yet verified; DXF is not native DWG.
---

# CAD-Coder：机械零件工程图加强版

Based on [alexzeng2014/cad-coder-skill](https://github.com/alexzeng2014/cad-coder-skill), secondarily developed by kpdx-del. Preserve upstream MIT license and attribution. This derivative adds engineering annotations, parameter preflight and evidence-based correction; it is not a universal standards-compliance engine.

## 先明确，再绘图

1. 读取本次附件、现有脚本/DXF、参数及对话，确认草图、正式图或改错。已知信息不重复问。
2. 先按[标准版本规则](references/standards.md)：明确指定版本则服从题设；未说明则查询并采用已实施且现行的最新版，核对注日期/不注日期引用。再按[输入规则](references/inputs.md)选择课程/通用工程模式，只询问影响交付的缺失参数，每轮1—3项。按[六类专项](references/parts.md)识别条件必需项。
3. 所有技术值记录用户给定/查表/计算/已确认建议的来源。禁止按图片比例猜精确值，禁止自动补材料、配合、公差、粗糙度等。条件不足只能交显著标记的草图，不能伪装正式图。
4. 正式生成前调用 `drawing_checks.assert_ready(spec)`，确认独立尺寸、功能和基准。先按[条件规则](references/feature-decisions.md)区分组成/导出要素、指示方向、基准有无及倒角覆盖范围，再采用[通用标注规则](references/annotation-rules.md)和当前类别专项；不机械套所有几何公差。
5. 生成并执行Python builder，保存DXF，重新读取并检查，再渲染整图与拥挤细节。修复后重复受影响检查；报告未覆盖的人工复核项。

来源索引及适用边界见 [sources.md](references/sources.md)。教材和指定/现行标准有差异时按条款说明，不把旧教材或项目偏好冒充唯一国标。教材第三章辅助解释连接关系，示例数值不能套入用户零件。

涉及螺栓、螺母或装配配合归属时，读取[紧固件画法](references/fasteners.md)：区分头部端视、螺纹端视、内外螺纹及轴向装配剖切；表示法标准与产品尺寸标准分别核对。

涉及螺栓、螺母、垫圈、单列圆锥滚子轴承、平键、隔套的二维画法、参数来源或审图规则时，先按[二维零件库](references/part-library.md)离线检索（`python scripts/part_library.py list/search/show/check`）：只报真正缺项/条件待确认，不填数值、不改输入；官方标准目录状态不等于尺寸表已核验，未核验尺寸不能标成正式尺寸库。

## 实现约定

FreeCAD二维导入、批量渲染、缓存与SolidWorks环境探测时，按需读取[CAD后端](references/cad-backends.md)。原生文件、导入实体和参数化特征树分别报告；未实际验证的软件能力不能宣称已支持。多格式预览优先调用`render_many()`，保留`render()`兼容接口。

- 毫米、R2010、模型1:1、dimlfac=1。图幅/打印比例与几何尺寸分开。图框标题栏按指定格式，放不下应调整布局或图幅，不静默缩小。个人字段缺失留空。
- `new_doc()` 创建 CAD_TEXT=ISOCP、CAD_CJK=仿宋，普通字3.5 mm、偏差2.5 mm。字体须安装或通过 CAD_FONT_DIRS 定位；禁止静默替换，不附字体。独立文字用 `typography.add_text`，不要漏样式。
- 轮廓0.50 mm；THIN、DIM、CENTER、HIDDEN、HATCH 0.25 mm。轴线点画、轮廓连续、键槽中心线伸出两端，剖面线裁剪到材料。
- 尺寸使用原生DIMENSION；公差框格是可编辑线/文字，不冒称原生TOLERANCE。图元可编辑不等于所有CAD软件重排一致。
- 箭头验收独立于生成样式：先明确各端的普通箭头或合法替代。要求普通箭头时，重读DXF调用`audit_annotations(msp,required_arrows={尺寸handle:(1,2)})`；禁止因脚本写了NONE就修改验收预期。见[防漏检查](references/checking.md)。
- 引出线优先直线或一次转折。框格默认左边中点进入、末段水平；倒角有箭头段与真实倒角延长线共线。黑实心基准三角形底边贴边界，不能用普通箭头替代。
- 表面公差连接与尺寸线错开；导出要素与对应尺寸线对齐，可共享箭头。φ由公差带形状决定。尺寸外置保持完整偏差组，不能缩字挤入。
- 不把旧教材的箭头方向当作2018版的通用公差带定义。圆锥圆度按1182—2018第15章和§17.4补方向要素；辅助方向框格可有基准引用，不等于圆度主框格有定位基准。详见版本规则。
- 总长和全部分段不同时作为独立约束。先保功能尺寸，省略经确认的可推导非功能尺寸；不自动删最短环。公称差值与公差区间分别计算。
- 剖切位置与断面中心使用同一定位来源，检查共线及上下标识对称。先预留标题栏和整组标注范围，再排文字/引线；粗糙度与剖切符号不能共用笔画。关联和分组写入CAD_LAYOUT，随DXF保存。
- 倒角或圆角移除了原始角点时，尺寸界线必须重新关联实际轮廓，不能只把extension_gap设为0。`dim_linear(...,witness_geometry=contour)`记录来源并检查落点；当前自动支持直线和无圆弧段多段线，其他轮廓明确列为复核。

## 辅助函数

安装 requirements.txt，将本skill的scripts目录加入Python导入路径。模板默认值仅为演示，不能作为用户零件参数。

- `new_doc(text_height=3.5,font="isocp___.ttf",*,cjk_font="simfang.ttf",extension_gap=1.0)`：本示例显式选extension_gap=0贴轮廓起线；不将允许的起点留白一概当断线。
- `dim_linear(msp,p1,p2,offset,angle=0,text=None,*,upper=None,lower=None,text_location=None,suppress_arrow=None,arrows="auto",reference=False,text_side="above")`：正offset水平向下、竖直向左。text="%%c<>"保留测量并加直径。upper/lower成对且有符号。arrows支持auto/inside/outside。text_side=above按完整MTEXT排版范围保证文字在水平线上方/竖直线左侧，native保留原生位置。suppress_arrow=1/2仅用于明确替代；需要双箭头时另布置基准，不能同点叠加。
- `dim_diameter`、`dim_radius`、`dim_angular`：原生尺寸；`tolerance_text`仅为独立堆叠MTEXT，不是测量尺寸。
- `leader`、`chamfer_note(...,chamfer_edge=(p1,p2),target=...,elbow=...)`：原生LEADER从箭尖开始，倒角函数校验共线，标注2×45°。
- `roughness_symbol(...,method=None,lay=None)`：课程图5-10布局，Ra在长横线下、方法在上；旋转整体符号。
- `datum_symbol(...,side="below",filled=True)`：三角形底边贴边界；轴线基准调用者负责尺寸线对齐/箭头替代。
- `feature_control_frame(...,target=None,elbow=None,arrow=True,zone=None,feature=None)`：支持symmetry、cylindricity、circular_runout、flatness、roundness、coaxiality、perpendicularity、parallelism；实际字宽定格宽，最多三基准格。zone=circle/cylinder/sphere按声明加φ/Sφ，feature保存表面或导出要素信息用于检查。`frame_leader`连接已有框格。
- `audit_annotations(msp)` 保留字符串问题列表。更全面检查用 `drawing_checks.audit_drawing(msp,chains=...)`；输入预检、尺寸链与区间计算见引用文档。
- `cutting_marks` 生成上下镜像标识并返回定位图元；`section_axes(msp,cut,cy,radius,label)`从真实剖切图元取位置，生成共线中心线及居中名称。`drawing_layout.choose_position`在有意义的候选位置中避让整组范围；无位置则报错重排，不随机绕线。

## 改错与交付

见[检查与改错](references/checking.md)。脚本修生成逻辑；DXF修订副本；截图只诊断已知信息。给出位置、依据和修改记录。排版可修，改变技术数值/基准/配合/功能尺寸须有依据或确认。`repair_dxf.py`只自动修字体样式，不能把全部报告项称为已修。

渲染：`python scripts/render_dxf.py part.dxf part.png`；固定图幅 `part.pdf --paper A3 --scale 1`（A4亦支持，--scale 0.5表示1:2）。预览保留字体填充轮廓的绕向，解决Ø错误填充，不再用空心描边替代所有字体。字体缺失/字形不全/图幅溢出明确报错。

交付DXF、builder、PNG/PDF及检查结果；图片不能替代可编辑CAD。只有实际在某CAD软件打开/编辑过，才能声称该兼容性已验证。

修改后运行 `python -m unittest discover -s tests -v` 和skill-creator的quick_validate；执行examples/engineering_annotations.py，重开DXF检查，并看整图和局部。自动检查不等于全标准合规，测试数量不是验收结论。
