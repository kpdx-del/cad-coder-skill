# 绘图前询问与输入约定

先读附件、现有 DXF、脚本、参数表及对话，列出已知条件，只问当前必需而缺失的信息，每轮1—3项。不要重复询问，不增加终端问卷。

## 模式与参数分类

- 版本优先级见[standards.md](standards.md)：指定版本优先，未指定默认已实施且现行最新版。课程模式不自动把旧教材版本作为默认标准；比较差异需具体出处。
- `course`：记录作业要求、教材和教师要求；冲突列出并澄清，不能自称某教材版式代表所有现行国标。
- `engineering`：记录标准名称及版本；无法取得原文的规则标待核实，不能猜接口或公差值。
- 必需：唯一确定当前几何、正式标注及输出所需的数据。
- 条件必需：存在对应特征或用户要求设计配合时才需要。
- 可选：姓名、学号等留空；不存在的结构不询问，未要求的加工说明不增加。
- 设计建议：与已给条件分开，说明来源，确认前不能成为正式制造要求。

## 脚本预检

`drawing_checks.assert_ready(spec, formal=True)` 在正式生成前运行。下面为结构示意，参数必须来自本次请求；示例数据不得作为用户零件默认值。

```python
spec = {
    "mode": "course", "part_type": "shaft", "units": "mm",
    "references": ["用户指定教材：版本与定位信息"],
    "parameters": {
        "diameters": {"value": [30, 40, 25],
                      "source": {"kind": "user", "statement": "本次请求明确给定的轴径"}},
        "axial_dimensions": {"value": [40, 35, 125],
                             "source": {"kind": "user", "statement": "两端功能长度及总长"}},
    },
    "required": [], "conditions": {},
}
```

通用入口：`validate_inputs(spec, formal=True)` 返回结构化问题；`assert_ready` 遇到 error 抛出 ValueError。`required` 补充具体零件的必需参数名，基础类别清单不能证明几何已唯一确定。嵌套特征要分别列入必需清单或人工逐项核对。

`parameters[name]` 包含 `value` 与 `source`；偏差可含成对的 `upper/lower`（有符号，upper≥lower）。来源种类：

| kind | 必需记录 |
|---|---|
| user | statement：本次给定条件或附件定位 |
| reference | document、edition、locator：文献、版本、页/表/行 |
| formula | expression、inputs：表达式、已提供的输入参数名；程序不执行任意表达式 |
| proposal | reason、confirmed：建议依据，明确确认后才允许正式出图 |

不根据图片比例推算精确尺寸；不默认补材料、热处理、载荷、配合、公差或粗糙度。来源字段只是追溯记录，不证明内容真实；仍须核对原文和计算。

## 草图与正式图

缺少条件时允许 `formal=False` 草图：只画能够确定的几何，省略未知特征，显著标“草图／条件待补齐”。缺失必需参数降为 warning，来源错误和单位错误仍报告。不能把未知值填0、伪造占位尺寸或将未确认建议画成制造要求。最终交付正式图须预检无 error，人工核对必需条件及报告的 review 项。

六类参数入口及条件见 [parts.md](parts.md)。
