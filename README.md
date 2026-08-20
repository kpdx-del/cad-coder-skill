# CAD-Coder Skill

Text-guided generation of editable 2D CAD sketches (`.dxf`) from natural-language descriptions, implemented as a Codex/Cindy agent skill. The agent writes a Python [ezdxf](https://ezdxf.readthedocs.io/) script for the requested part, executes it to produce a DXF file, and renders a PNG preview for verification.

This project is an independent, skill-based reimplementation inspired by the paper:

> **CAD-Coder: Text-Guided CAD Files Code Generation**
> Changqi He, Shuhan Zhang, Liguo Zhang, Jiajun Miao
> College of Computer Science and Technology, Harbin Engineering University
> arXiv:2505.08686 [cs.GR], May 2025. <https://arxiv.org/abs/2505.08686>

The original CAD-Coder fine-tunes `DeepSeek-R1-Distill-Llama-8B` with LoRA on a purpose-built CFSC dataset (29,130 DXF + script pairs) to map natural language to ezdxf script code. This skill keeps the same core idea — *natural language -> Python ezdxf script -> DXF -> preview* — but replaces the fine-tuned model with an agent driven by the reusable templates and annotation helpers in this repository. No model weights or dataset from the paper are used here (the authors state the dataset will be released upon acceptance).

## Repository layout

```
SKILL.md                  # skill manifest: triggers, workflow, rules
scripts/
  part_templates.py       # parameterized part builders (hex_nut, stepped_shaft, flange, plate_with_holes)
  sketch_helpers.py       # dimension & annotation helpers (linear/radius/diameter/angle dims, tolerance, roughness, chamfer, leader)
  render_dxf.py           # DXF -> PNG preview renderer (white background)
```

## Requirements

- Python 3.10+
- `pip install ezdxf matplotlib`

## Usage (standalone, without an agent)

Generate a DXF from a built-in template with default parameters:

```bash
python scripts/part_templates.py flange out/flange.dxf
python scripts/render_dxf.py out/flange.dxf out/flange.png
```

Customize parameters in your own script:

```python
import sys
sys.path.insert(0, "scripts")
from part_templates import flange, stepped_shaft, hex_nut, plate_with_holes

flange(d_outer=120.0, d_inner=50.0, n_bolts=6, d_bolt=12.0, d_pcd=85.0).saveas("flange.dxf")
stepped_shaft(segments=[(20.0, 30.0), (30.0, 40.0), (16.0, 25.0)]).saveas("shaft.dxf")
```

For parts not covered by the templates, write a builder following the same structure (imports / builder function with free parameters / main) and use the annotation helpers from `sketch_helpers.py` for dimensions, tolerances, chamfers, and surface-roughness symbols.

## Usage (as an agent skill)

Point your Codex/Cindy skill directory at this repository (or copy the folder into your skills root). Once the skill is listed, ask in natural language, e.g.:

- "Draw a flange, outer diameter 120, 6 M12 bolt holes on an 85 mm pitch circle, output DXF."
- "画一个阶梯轴，三段：直径20长30、直径30长40、直径16长25，带尺寸标注。"

The agent will parse the description, fill in missing dimensions with engineering defaults, generate and run the ezdxf script, render the PNG preview, and hand you the `.dxf` (opens in AutoCAD, SolidWorks, CAXA, CATIA, UG, Onshape).

## Notes & known issues

- Units are millimeters; geometry on layer `0`, dimensions/annotations on layer `DIM`.
- `dim_angular` is drawn manually (arc + text) because ezdxf's `add_angular_dim_2l().render()` crashes with a `ZeroDivisionError` in the curved-dimension renderer.
- 3D support is out of scope for this skill; the paper demonstrates DXF-based 3D models, but the templates here are 2D sketches.

## Citation

If you use or build on this work, please cite the original paper:

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

## License

This repository (skill, templates, helpers, renderer) is released under the MIT License. The paper's content remains the property of its authors; please refer to arXiv:2505.08686 for its license terms.
