# CAD-Coder Skill · 机械零件工程图加强版

## 二次开发声明 / Attribution

本仓库是 [alexzeng2014/cad-coder-skill](https://github.com/alexzeng2014/cad-coder-skill) 的二次开发版本，原作者为 **alexzeng2014**，本次改进由 **kpdx-del** 维护。保留原项目的 MIT 许可证、作者署名及上游历史。本项目不代表原作者或论文作者的官方版本。

上游提供了“自然语言 → Python ezdxf 脚本 → 可编辑 DXF → 图片预览”的技能、零件模板和辅助函数。本次二次开发增加机械图样标注规则、改进辅助函数、提供可运行示例和回归测试。原始版权与本次修改版权见 [LICENSE](LICENSE)。

上游说明其设计受到论文 [CAD-Coder: Text-Guided CAD Files Code Generation](https://arxiv.org/abs/2505.08686) 启发。本仓库提供代理技能及 Python 绘图工具，不包含论文模型权重或训练数据。

## 本次改进

- 统一为毫米与真实尺寸倍率 1，修正原有单位和尺寸倍率不一致的问题。
- 使用原生 DIMENSION 实体，支持线性、直径、半径和三点角度尺寸；上下偏差按带符号的数值输入，支持上下堆叠显示。
- 引出线优先直线或一次转折。几何公差框的引出线固定连接左边中点；关联中心平面时可使用无箭头的尺寸界线延伸连接。
- 倒角辅助函数可验证箭头段与真实倒角线共线。线性尺寸数字外置时，箭头位于尺寸界线外侧、朝测量区间内指；处理端点输入顺序相反的情况。
- 增加实心基准三角形、粗糙度完整符号、对称度/圆柱度/圆跳动/平面度公差框。基准及粗糙度布局采用本例选用的 GB/教材表达约定，其他制图体系应按其规范调整。
- PNG/PDF 黑白预览，支持 A3/A4 固定纸张与比例；超出纸张范围直接报错，避免无提示缩放。
- 17 项回归测试：数值、偏差、箭头实体方向、连接点、DXF 保存后重读、模板单位，以及 PDF 实际纸张尺寸。

![工程标注示例](examples/preview.png)

示例为合成的标注演示，数值用于说明布局；不包含个人姓名、学号或课程原文件。

## 安装与运行

Python 3.10+：

```bash
python -m pip install -r requirements.txt
python examples/engineering_annotations.py out
```

输出 `out/engineering_annotations.dxf`、`.png` 和 `.pdf`。DXF 中尺寸保留为 DIMENSION，引出线保留为 LEADER；公差框、基准与粗糙度由可编辑的线、文字和填充组成。

生成基础零件：

```bash
python scripts/part_templates.py flange out/flange.dxf
python scripts/render_dxf.py out/flange.dxf out/flange.png
python scripts/render_dxf.py out/flange.dxf out/flange.pdf --paper A3 --scale 1
```

`--scale 1` 表示 1:1，`--scale 0.5` 表示 1:2。固定纸张输出要求 DXF 单位为毫米；按边距校验是否放得下。该选项设置纸张和比例，不会自动画图框或标题栏。

中文图样需使用本机已安装且具有对应字形的字体。`new_doc(font="字体文件名.ttf")` 设置 DXF 字体；`render_dxf.py --font 字体路径` 仅覆盖预览字体。仓库不分发字体文件。

## 作为技能使用

将仓库目录安装或复制为技能目录中的 `cad-coder` 文件夹，使 `SKILL.md` 位于该文件夹根目录。可提出：

> 画一个阶梯轴，带尺寸与上下偏差、公差框和粗糙度。引出线最多一次转折，公差框从左边中点接线，生成可编辑 DXF 和预览图。

具体工作规则、辅助函数和验收步骤见 [SKILL.md](SKILL.md)。示例见 [examples/engineering_annotations.py](examples/engineering_annotations.py)。

```python
import sys
sys.path.insert(0, "scripts")
from sketch_helpers import new_doc, dim_linear, feature_control_frame, chamfer_note

doc = new_doc()
m = doc.modelspace()
dim_linear(m, (0,0), (35,0), 12, upper=0.042, lower=0.026)
feature_control_frame(m, (45,-30), "circular_runout", 0.025, "A", target=(35,0))
chamfer_note(m, (-20,-5), target=(0,0), elbow=(-5,-5),
             chamfer_edge=((0,0),(2,2)))
doc.saveas("part.dxf")
```

`upper`、`lower` 都是带符号偏差，不是偏差绝对值。上下限必须同时提供。部分辅助函数的可选参数为仅关键字参数。

## 验证与范围

```bash
python -m unittest discover -s tests -v
```

已在 Python 3.12、ezdxf 1.4.5、matplotlib 3.10.3 上运行测试并检查示例预览。测试包含 DXF 重读和 A3 PDF 页面宽高验证。外置箭头的绘制扩展使用 ezdxf 1.4.x 渲染接口，因此依赖范围限定到 `<1.5`。

仍有以下边界：

- 提供 2D DXF，不直接输出原生 DWG 或 3D 参数模型。
- 不自动选择工程公差，不自动规划无碰撞引出线，不自动证明整张图符合全部 GB 标准。必须结合给定装配要求及标准版本检查。
- 公差框不是原生 TOLERANCE 对象；文字、线和图形可分别编辑。
- 尚未在 AutoCAD/CAXA 等应用中逐个验证打开及重新生成的结果。文件内包含已渲染的尺寸块和箭头翻转属性；各 CAD 重新生成后的显示仍需实际检查。重新读入 DXF 后如需用本项目规则重新渲染，应重新设置本项目的尺寸渲染器。
- 基础零件模板属于示意起点，不能替代螺纹、强度和制造设计。

## 来源

原始技能：[alexzeng2014/cad-coder-skill](https://github.com/alexzeng2014/cad-coder-skill)。

论文引用沿用上游提供的信息：

```bibtex
@misc{he2025cadcoder,
  title={CAD-Coder: Text-Guided CAD Files Code Generation},
  author={Changqi He and Shuhan Zhang and Liguo Zhang and Jiajun Miao},
  year={2025},
  eprint={2505.08686},
  archivePrefix={arXiv},
  primaryClass={cs.GR},
  url={https://arxiv.org/abs/2505.08686}
}
```

辅助函数依据适用版本的 [ezdxf 尺寸文档](https://ezdxf.readthedocs.io/en/stable/tutorials/linear_dimension.html) 及其实现进行验证。代码与技能继续使用 [MIT License](LICENSE)；论文内容的权利归其作者。
