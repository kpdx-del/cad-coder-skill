# GitHub复用评估：标注语义与CAD几何分开

核查日期：2026-11-26。继续在kpdx-del/cad-coder-skill现有Python/ezdxf分支上做必要改进；下面不是引入新CAD框架的建议。GitHub几何实现不能代替教材/标准决定被测要素、基准和倒角范围。

## 已核查的项目与模块

| 仓库/位置 | 可借鉴的具体内容 | 适配和代价 |
|---|---|---|
| [mozman/ezdxf，v1.4.5 render/dim_linear.py](https://github.com/mozman/ezdxf/blob/v1.4.5/src/ezdxf/render/dim_linear.py) | `add_arrows()`及其连接点；内外箭头与文字布局分开处理，尺寸线接实际箭头基部 | 已有依赖、MIT，直接调用，成本低；不是再实现一套箭头绘图 |
| [render/arrows.py](https://github.com/mozman/ezdxf/blob/v1.4.5/src/ezdxf/render/arrows.py) | ClosedArrowFilled、DatumTriangleFilled、virtual_entities、connection_point；检查实际实心几何，而不只计数INSERT | 可复用虚拟图元进行落点、面积和连接检查；基准三角形与普通箭头不能因同为三角就混用 |
| [tests/test_07_render/test_701_arrows.py](https://github.com/mozman/ezdxf/blob/v1.4.5/tests/test_07_render/test_701_arrows.py) | 实心箭头实际为SOLID、R12/R2000块及虚拟图元测试 | 借鉴测试对象，而不是只截一张看似正常的图 |
| [test_704_render_linear_dimension.py](https://github.com/mozman/ezdxf/blob/v1.4.5/tests/test_07_render/test_704_render_linear_dimension.py) | 单/双偏差、极限尺寸、DIMENSION插入变换、接近竖直的对齐尺寸 | 本地增加转动/位移/反向端点案例时可借鉴；不能以一个水平样例代替所有方向 |
| [qcad/qcad，src/entity/RDimensionData.cpp](https://github.com/qcad/qcad/blob/master/src/entity/RDimensionData.cpp) | 活跃代码中的`hasSpaceForArrows()`、文字包围范围、参考点移动；箭头空间单独判断 | C++/Qt、所核模块GPL-3.0-or-later。本项目借鉴行为/测试，用现有ezdxf实现，不复制代码进入MIT仓库 |
| [scripts/Modify/Bevel/Bevel.js](https://github.com/qcad/qcad/blob/master/scripts/Modify/Bevel/Bevel.js) | 求交、按两侧距离取得倒角端点、裁剪原边、增加倒角边；同一多段线的角专门处理，无法构造时明确失败 | 适合借鉴“真实裁剪”的行为，避免只画一根斜线盖在旧轮廓上。单个二维角倒角不等于自动识别轴端整圈 |
| [scripts/Modify/Lengthen/Lengthen.js](https://github.com/qcad/qcad/blob/master/scripts/Modify/Lengthen/Lengthen.js) | 按选择位置确定延长哪一端，再更新真实端点 | 借鉴端点选择与延长后的检查，避免把框格连线、中心线和尺寸界线一并拉长 |

维护情况：GitHub API核查，ezdxf仓库最新提交日期为2026-11-26，QCAD为2026-11-24，均未归档。日期是仓库级别，不能当作上述每个模块最近修改日期。ezdxf实现固定参考已安装的1.4.5标签；未因master更新而升级依赖。

许可证：ezdxf [MIT](https://github.com/mozman/ezdxf/blob/v1.4.5/LICENSE)；所读QCAD源文件首部声明GPL第3版或更高版本。本次没有复制QCAD代码。QCAD RDimensionData.cpp中旧的`getDimensionLineShapes()`大段位于块注释内，不能把它当作当前运行逻辑照搬。

`hasSpaceForArrows()`在所读版本中仅按尺寸线长度与箭头大小判断箭头空间，不是“完整尺寸+偏差+符号都放得下”的判据。文字与箭头须分别测量，不能把该阈值直接当本项目完整布局算法。

## 应优先补的语义与行为验证

1. 同一圆锥上：圆度径向箭头与斜向圆跳动的法向/指定方向箭头，检查不能互换。
2. 同一孔上：轴线直线度无基准，轴线垂直度有合理基准；不能按“导出要素”统一填基准。
3. 基准与尺寸线：组成要素错开、导出要素对齐；圆锥轴线需区分轴线方向与素线方向。
4. 普通尺寸端点按独立要求检查；NONE、无图元、隐藏图元、空块均失败。合法基准替代/共用另查实际图元，不能仅凭元数据放行。
5. 伸出量检查根据线的作用与符号范围，不统一写死6 mm；检查实际保存后的端点，禁止延长真实零件边界或让指引线穿框。
6. 文字外置与箭身内外分别测试；反向测量端点、旋转后的几何要保持相同语义。
7. 轴端整圈倒角应出现上下两条相应轮廓；多个独立棱边的倒角必须有完整范围、数量或明确统一要求。

上轮90项测试不等于上述所有新增语义场景均已实现；当前本轮整理规则与来源，绘图代码没有新增这些自动判断。生成前仍需确定被测要素、项目、公差带方向和倒角范围。
