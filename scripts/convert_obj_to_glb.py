"""Blender 后台脚本：把 OBJ 转换成 GLB。

使用：
    blender --background --python scripts/convert_obj_to_glb.py -- \
        --input <obj_path> --output <glb_path>

注意：
- "--" 之后的参数才是给 Python 脚本的，Blender 会忽略它前面的参数。
- 如果系统没装 Blender，请使用 backend/pipelines/optimize_asset.py 内置的 trimesh 回退。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> argparse.Namespace:
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply-transforms", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv)

    try:
        import bpy  # type: ignore
    except Exception as e:
        print(f"[error] 需要在 Blender Python 环境中运行：{e}")
        sys.exit(1)

    obj_path = Path(args.input).resolve()
    glb_path = Path(args.output).resolve()
    glb_path.parent.mkdir(parents=True, exist_ok=True)

    # 清空场景
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 导入 OBJ。Blender 4.x 用 wm.obj_import，3.x 用 import_scene.obj
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=str(obj_path))
    else:
        bpy.ops.import_scene.obj(filepath=str(obj_path))

    if args.apply_transforms:
        for obj in bpy.context.selected_objects:
            obj.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # 选择全部网格用于导出
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
    )

    print(f"[ok] exported {glb_path}")


if __name__ == "__main__":
    main()
