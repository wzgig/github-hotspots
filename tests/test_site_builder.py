import json
from pathlib import Path

from scripts.build_site import build_site


def _report(period: str, run_date: str, count: int, generated_at: str) -> dict:
    return {
        "schema_version": 1,
        "period": period,
        "run_date": run_date,
        "generated_at": generated_at,
        "window_label": run_date,
        "data_quality": "高：测试快照",
        "warnings": ["仅用于离线测试"],
        "methodology": "使用离线样本验证网站构建。",
        "repositories": [
            {
                "rank": rank,
                "full_name": f"example/repo-{rank}",
                "html_url": f"https://github.com/example/repo-{rank}",
                "description": f"第 {rank} 个测试项目",
                "language": "Python",
                "stars": 1_000 - rank,
                "forks": rank,
                "score": 90 - rank,
                "star_delta": 100 - rank,
                "delta_source": "snapshot",
                "summary": {"one_line": f"测试摘要 {rank}"},
            }
            for rank in range(count, 0, -1)
        ],
    }


def _board_repositories(prefix: str, count: int) -> list[dict]:
    return [
        {
            "rank": rank,
            "full_name": f"example/{prefix}-{rank}",
            "html_url": f"https://github.com/example/{prefix}-{rank}",
            "description": f"{prefix} 第 {rank} 个测试项目",
            "language": "Python",
            "stars": 2_000 - rank,
            "forks": rank,
            "score": 95 - rank,
            "star_delta": 200 - rank,
            "delta_source": "snapshot",
            "summary": {"one_line": f"{prefix} 测试摘要 {rank}"},
        }
        for rank in range(count, 0, -1)
    ]


def _write_report(root: Path, period: str, name: str, payload: dict) -> None:
    directory = root / "reports" / period
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_site_selects_latest_reports_and_enforces_limits(tmp_path: Path) -> None:
    _write_report(
        tmp_path,
        "daily",
        "2026-07-10.json",
        _report("daily", "2026-07-10", 1, "2026-07-10T08:00:00+08:00"),
    )
    _write_report(
        tmp_path,
        "daily",
        "2026-07-11.json",
        _report("daily", "2026-07-11", 5, "2026-07-11T08:00:00+08:00"),
    )
    _write_report(
        tmp_path,
        "weekly",
        "2026-W28.json",
        _report("weekly", "2026-07-11", 9, "2026-07-11T08:05:00+08:00"),
    )

    payload = build_site(tmp_path, "https://github.com/example/github-hotspots")

    assert payload["daily"]["run_date"] == "2026-07-11"
    assert payload["schema_version"] == 2
    assert [item["rank"] for item in payload["daily"]["repositories"]] == [1, 2, 3]
    assert len(payload["weekly"]["repositories"]) == 7
    assert payload["site"]["repository_url"] == "https://github.com/example/github-hotspots"
    assert payload["daily"]["repositories"][0]["one_line"] == "测试摘要 1"
    assert payload["daily"]["boards"]["comprehensive"]["label"] == "综合主榜"
    assert (
        payload["daily"]["boards"]["comprehensive"]["repositories"]
        == payload["daily"]["repositories"]
    )
    assert payload["daily"]["boards"]["ai"] == {
        "label": "AI 专题榜",
        "repositories": [],
    }


def test_build_site_normalises_dual_boards_independently(tmp_path: Path) -> None:
    daily = _report("daily", "2026-07-11", 5, "2026-07-11T08:00:00+08:00")
    daily["boards"] = {
        "comprehensive": {
            "label": "综合主榜",
            "repositories": _board_repositories("main-daily", 5),
        },
        "ai": {
            "label": "AI 专题榜",
            "repositories": _board_repositories("ai-daily", 5),
        },
    }
    weekly = _report("weekly", "2026-07-11", 9, "2026-07-11T08:05:00+08:00")
    weekly["boards"] = {
        "comprehensive": {
            "label": "综合主榜",
            "repositories": _board_repositories("main-weekly", 9),
        },
        "ai": {
            "label": "人工智能雷达",
            "repositories": _board_repositories("ai-weekly", 9),
        },
    }
    _write_report(tmp_path, "daily", "2026-07-11.json", daily)
    _write_report(tmp_path, "weekly", "2026-W28.json", weekly)

    payload = build_site(tmp_path, "https://github.com/example/github-hotspots")

    assert [
        item["full_name"] for item in payload["daily"]["boards"]["comprehensive"]["repositories"]
    ] == ["example/main-daily-1", "example/main-daily-2", "example/main-daily-3"]
    assert [item["full_name"] for item in payload["daily"]["repositories"]] == [
        "example/main-daily-1",
        "example/main-daily-2",
        "example/main-daily-3",
    ]
    assert [item["full_name"] for item in payload["daily"]["boards"]["ai"]["repositories"]] == [
        "example/ai-daily-1",
        "example/ai-daily-2",
        "example/ai-daily-3",
    ]
    assert len(payload["weekly"]["boards"]["comprehensive"]["repositories"]) == 7
    assert len(payload["weekly"]["boards"]["ai"]["repositories"]) == 7
    assert payload["weekly"]["boards"]["ai"]["label"] == "人工智能雷达"


def test_build_site_outputs_deterministic_json_and_javascript(tmp_path: Path) -> None:
    _write_report(
        tmp_path,
        "daily",
        "2026-07-11.json",
        _report("daily", "2026-07-11", 3, "2026-07-11T08:00:00+08:00"),
    )
    _write_report(
        tmp_path,
        "weekly",
        "2026-W28.json",
        _report("weekly", "2026-07-11", 7, "2026-07-11T08:05:00+08:00"),
    )

    build_site(tmp_path, "git@github.com:example/github-hotspots.git")
    json_path = tmp_path / "site" / "data" / "site-data.json"
    js_path = tmp_path / "site" / "data" / "site-data.js"
    first_json = json_path.read_bytes()
    first_js = js_path.read_bytes()

    build_site(tmp_path, "git@github.com:example/github-hotspots.git")

    assert json_path.read_bytes() == first_json
    assert js_path.read_bytes() == first_js
    assert json.loads(first_json)["methodology"]["metrics"][0]["weight"] == "50%"
    assert first_js.startswith(b'"use strict";\nwindow.GITHUB_HOTSPOTS_DATA = {')
    assert "追踪开源世界" in first_json.decode("utf-8")
