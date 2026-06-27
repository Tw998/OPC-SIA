#!/usr/bin/env bash
# API 引擎一键测试 —— 用 Claude API + web_search 自动调研一家公司。
#
# 用法:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   ./run_api.sh "Siemens"                 # 单公司
#   ./run_api.sh --input data/list.csv     # 批量(自动加 --workers 4)
#
# 输出写到 output_api/(不覆盖 manual 引擎的 output/)。

set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${ANTHROPIC_API_KEY:-}" && -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  echo "✗ 没检测到 ANTHROPIC_API_KEY。先设置:"
  echo "    export ANTHROPIC_API_KEY=sk-ant-..."
  exit 1
fi

python3 -c "import anthropic" 2>/dev/null || { echo "正在安装 anthropic..."; python3 -m pip install -q "anthropic>=0.40"; }

OUT="output_api"
if [[ "${1:-}" == "--input" ]]; then
  echo "▶ 批量调研:$2 → $OUT/"
  python3 pipeline.py --input "$2" --engine api --workers 4 --out "$OUT"
else
  COMPANY="${1:-Siemens}"
  echo "▶ 单公司调研:$COMPANY → $OUT/"
  python3 pipeline.py --company "$COMPANY" --engine api --out "$OUT"
fi

echo
echo "✅ 看结果:"
echo "   open $OUT/sales_intelligence.xlsx"
echo "   cat  $OUT/reports/*.md"
