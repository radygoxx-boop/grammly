#!/usr/bin/env python3
"""
fetch_questions.py
Notion データベースから全問題を取得して questions.json に書き出す。
GitHub Actions から毎日自動実行される。

必要な環境変数:
  NOTION_API_KEY      : Notion Internal Integration Token
  NOTION_DATABASE_ID  : Grammly 問題データベース v2 の ID
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# ─── 設定 ────────────────────────────────────────────────
API_KEY     = os.environ.get("NOTION_API_KEY", "")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
OUTPUT_FILE = "questions.json"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

CHOICE_MAP = {"A": 0, "B": 1, "C": 2, "D": 3}

# ─── ヘルパー ─────────────────────────────────────────────
def get_text(prop):
    """rich_text / title プロパティからプレーンテキストを取得"""
    if not prop:
        return ""
    for key in ("rich_text", "title"):
        if key in prop and prop[key]:
            return prop[key][0].get("plain_text", "")
    return ""

def get_select(prop):
    """select プロパティから値を取得"""
    if not prop:
        return ""
    return (prop.get("select") or {}).get("name", "")

def get_checkbox(prop):
    """checkbox プロパティから値を取得"""
    if not prop:
        return False
    return prop.get("checkbox", False)

# ─── Notion API: 全ページ取得（ページネーション対応）────────
def fetch_all_pages():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    pages = []
    cursor = None

    while True:
        body = {
            "filter": {
                "property": "公開",
                "checkbox": {"equals": True},
            },
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor

        resp = requests.post(url, headers=HEADERS, json=body, timeout=30)

        if not resp.ok:
            print(f"ERROR: Notion API returned {resp.status_code}: {resp.text}")
            sys.exit(1)

        data = resp.json()
        pages.extend(data.get("results", []))
        print(f"  Fetched {len(pages)} pages so far...")

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return pages

# ─── ページ → 問題オブジェクト変換 ──────────────────────────
def page_to_question(page):
    p = page.get("properties", {})
    unit  = get_select(p.get("単元"))
    level = get_select(p.get("難易度"))
    answer_letter = get_select(p.get("正解", {}))

    return {
        "q":       get_text(p.get("問題文")),
        "ja":      get_text(p.get("和訳")),
        "hint":    get_text(p.get("ヒント")),
        "choices": [
            get_text(p.get("選択肢A")),
            get_text(p.get("選択肢B")),
            get_text(p.get("選択肢C")),
            get_text(p.get("選択肢D")),
        ],
        "answer":  CHOICE_MAP.get(answer_letter, 0),
        "explain": get_text(p.get("解説")),
        "level":   level or "初級",
        "_unit":   unit,
    }

# ─── メイン ──────────────────────────────────────────────
def main():
    if not API_KEY or not DATABASE_ID:
        print("ERROR: NOTION_API_KEY / NOTION_DATABASE_ID が設定されていません")
        sys.exit(1)

    print(f"Fetching from Notion DB: {DATABASE_ID}")
    pages = fetch_all_pages()
    print(f"Total pages fetched: {len(pages)}")

    # 単元ごとにグループ化
    grouped = {}
    skipped = 0
    for page in pages:
        q = page_to_question(page)
        unit = q.pop("_unit", "")
        if not unit or not q["q"]:
            skipped += 1
            continue
        grouped.setdefault(unit, []).append(q)

    if skipped:
        print(f"Skipped {skipped} pages (no unit or empty question)")

    # 単元内を難易度順にソート
    level_order = {"初級": 0, "中級": 1, "上級": 2}
    for unit in grouped:
        grouped[unit].sort(key=lambda x: level_order.get(x.get("level", "初級"), 99))

    # 結果を出力
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "generated_at": now_utc,
        "total": sum(len(v) for v in grouped.values()),
        "questions": grouped,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Written to {OUTPUT_FILE}")
    print(f"   Generated at : {now_utc}")
    print(f"   Units        : {len(grouped)}")
    print(f"   Total Q      : {output['total']}")
    for unit, qs in grouped.items():
        levels = {}
        for q in qs:
            l = q.get("level", "?")
            levels[l] = levels.get(l, 0) + 1
        level_str = " / ".join(f"{k}:{v}" for k, v in sorted(levels.items(), key=lambda x: level_order.get(x[0], 99)))
        print(f"   {unit:16s} {len(qs):3d}問  ({level_str})")

if __name__ == "__main__":
    main()
