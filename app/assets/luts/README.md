# 内置 LUT 预设（免费使用）

本目录下的 `.cube` 文件由 **Pocket Live Capture 项目自行生成**（见 `app/services/lut_presets.py`），
不依赖第三方 LUT 包，可自由用于个人或商业项目（与主项目 MIT 许可一致）。

## 预设列表

| 文件 | 名称 | 说明 |
|------|------|------|
| 01_soft_portrait.cube | 柔肤人像 | 轻微提亮 + 暖肤 |
| 02_warm_sunset.cube | 暖色日落 | 偏暖金色调 |
| 03_cool_cinematic.cube | 冷色电影 | 偏冷蓝电影感 |
| 04_teal_orange.cube | 青橙大片 | 青橙分离风光/旅行 |
| 05_vintage_film.cube | 复古胶片 | 褪色怀旧 |
| 06_vivid_pop.cube | 鲜活饱和 | 适度提饱和 |
| 07_high_contrast.cube | 高对比 | S 曲线增强对比 |

## 自定义 LUT

可通过应用内「导入 .cube」添加更多 LUT，文件会保存到：

`Pictures/PocketLiveCapture/luts/`

## 重新生成

```bash
python -c "from pathlib import Path; from app.services.lut_presets import generate_builtin_lut_files; generate_builtin_lut_files(Path('app/assets/luts'))"
```
