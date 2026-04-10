# 动画番剧阅历

这是一个可直接部署到 GitHub Pages 的静态页面，用于勾选已看番剧、导出 `watched_ids.json`，并在浏览器里直接生成长图。

## 在线功能

- 浏览 1998-2026 年番剧列表
- 在浏览器里勾选已观看项目
- 使用 `localStorage` 保存当前浏览器内的勾选状态
- 导出 `watched_ids.json`
- 直接导出图片

## 本地功能

浏览器版已经支持直接导出图片。Python 脚本仍然保留，适合作为离线兜底方案或后续批量生成。

### 封面本地化

如果你想让浏览器导出的图片也稳定带上封面，需要先把第三方封面下载到仓库里：

```bash
python localize_covers.py
```

运行后会：

- 下载远程封面到 `assets/covers/`
- 把 `anime_data.json` 里的 `cover` 改成站内相对路径
- 保留原始远程地址到 `cover_remote`

先用小样本测试也可以：

```bash
python localize_covers.py --limit 20 --output anime_data_local_test.json
```

### 压缩封面体积

本地化后的封面适合继续压缩成 WebP，减小仓库和 GitHub Pages 体积：

```bash
python optimize_covers.py
```

默认会：

- 把 `assets/covers/` 下的封面缩放到较轻量尺寸
- 统一转成 `.webp`
- 改写 `anime_data.json` 中的 `cover` 路径

### 安装依赖

```bash
pip install -r requirements.txt
```

### 生成已看长图

先在页面里导出 `watched_ids.json`，再运行：

```bash
python generate_long_image.py --ids-file watched_ids.json --output anime-long.png
```

### 生成全量长图

```bash
python generate_long_image.py --mode full --output anime-full.png
```

## 部署到 GitHub Pages

1. 创建 GitHub 仓库并把当前项目推到 `main` 分支。
2. 进入仓库 `Settings` -> `Pages`。
3. 在 `Build and deployment` 中把 `Source` 设为 `GitHub Actions`。
4. 推送一次到 `main` 后，仓库中的 `.github/workflows/pages.yml` 会自动发布站点。
5. 发布完成后，访问 `https://<你的用户名>.github.io/<仓库名>/`。

## 注意

- GitHub Pages 只托管静态文件，不支持在站点上直接运行 Python。
- 已看记录保存在访问者自己的浏览器里，不会自动同步到 GitHub。
- 如果你使用 GitHub Free，公开对外访问通常使用公开仓库最稳妥。
