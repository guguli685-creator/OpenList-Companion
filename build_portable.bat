@echo off
:: 设置编码为UTF-8，防止控制台中文乱码
chcp 65001 >nul
cls

echo ===================================================
echo       OpenList Companion 便捷便携版打包工具
echo ===================================================
echo.

:: 1. 检查并安装/更新打包依赖
echo 📦 [1/3] 正在检查并准备打包环境库...
pip install pyinstaller pillow requests psutil --upgrade
if %errorlevel% neq 0 (
    echo ❌ 依赖库环境配置失败，请检查 Python 或 pip 是否加入环境变量。
    pause
    exit /b
)

:: 2. 执行 PyInstaller 打包
echo.
echo 🚀 [2/3] 正在开始 PyInstaller 编译 (文件夹模式)...
:: --onedir: 生成文件夹模式 / --windowed: 隐藏控制台黑框 / --clean: 清理缓存
:: 已移除 --icon 外部图标参数，避免因缺少 ico 文件导致编译中断
pyinstaller --noconfirm --onedir --windowed --clean --name="OpenListCompanion" openlist.py
if %errorlevel% neq 0 (
    echo ❌ PyInstaller 编译遇到错误，打包终止。
    pause
    exit /b
)

:: 3. 整合便携包资产
echo.
echo 📂 [3/3] 正在自动整合外部便携资产文件...
set "DIST_DIR=dist\OpenListCompanion"

:: 检查并复制头像素材
if exist openlist.png (
    copy /y openlist.png "%DIST_DIR%\" >nul
    echo ✅ 已成功整合 openlist.png 到便携包目录
) else (
    echo ⚠️ 提示：未在当前目录找到 openlist.png
)

:: 检查并复制 alist 服务核心
if exist alist.exe (
    copy /y alist.exe "%DIST_DIR%\" >nul
    echo ✅ 已成功整合 alist.exe 到便携包目录
) else (
    echo ⚠️ 提示：未在当前目录找到 alist.exe，用户需自行放入程序同级
)

echo.
echo ===================================================
echo 🎉 便携版打包整合成功！
echo 📂 目标文件夹: %DIST_DIR%
echo 💡 分发提示: 直接将 OpenListCompanion 文件夹压缩为 .zip 即可发布。
echo ===================================================
pause