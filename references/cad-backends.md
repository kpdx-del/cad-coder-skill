# CAD后端与高效出图

当前阶段：FreeCAD二维导入适配器已实际保存重开验证；SolidWorks连接探测正在本机2023 SP5验证。三维参数化、关联出图、装配拆件尚未交付，不因存在脚本就报告已支持。

## 本地命令

`python scripts/cad_job.py doctor --freecad <FreeCADCmd路径>`只检查环境，不安装、不启动软件。注册信息不等于可运行或已授权连接。

`python scripts/cad_job.py render input.dxf output_dir --formats png pdf --paper A3`一次解析、一次字体与图形上下文，输出多种格式。缓存同时核对源文件、字体内容、参数、渲染器和依赖版本及输出哈希；命中后报告cache_hit，不冒称重新渲染。

`python scripts/cad_job.py freecad input.dxf output.FCStd --executable <FreeCADCmd路径>`使用独立配置和临时ASCII输入路径，启用现代导入器的Draft、文字、尺寸与填充，拒绝覆盖输出，保存后重开并写inspection.json。GUI显示仍需复核；二维Draft对象不是三维参数化模型。启动FreeCAD时清除宿主PYTHONHOME/PYTHONPATH，避免混用运行时。

## 实施纪律

- 首期输出限定PNG/PDF/SVG与FCStd；DWG及SolidWorks原生文件须在真实软件验证后启用，不能改扩展名伪造。
- 只有确定性渲染结果可复用缓存，不能把旧技术审查结果随意标为通过。
- 修改技术参数、字体、全局样式或剖切关系时重新计算受影响图元；当前实现是整文件缓存，尚不声称已有按视图增量重建。
- 工具stdout仅返回状态、产物和关键问题，详细CAD日志写文件。平台未提供token计量时标为不可测。
- 原件不覆盖；字体不静默替换；最终整图和局部预览仍必须查看，用户认可本轮版本后才上传。
- 当前教材复刻仍未验收；局部剖面与完整材料包络分开处理，φ100H7/f9绑定箱体孔/端盖止口，端部键不得统一套用封闭长圆。

## 来源

现有ezdxf脚本及MIT来源保留。参考FreeCAD 1.1.4 Draft/importDXF.py真实参数与接口；语义差异和短报告思路参考numikel/cad-drawings（MIT），本轮未复制其代码；规则审查参考beiming183-cloud/AutoCAD-skills，不能将规则文字当作已实现的检查。
