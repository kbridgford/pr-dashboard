#!/usr/bin/env python3
"""Generate Power BI report section and visual container JSON files for the PR Dashboard.

This script creates the PbixProj Report/ section structure with proper visual
definitions for the dashboard pages. Run once to generate, then compiled via pbi-tools.
"""

import json
import os
import uuid

BASE = os.path.dirname(os.path.abspath(__file__))
SECTIONS_DIR = os.path.join(BASE, "pbixproj-full", "Report", "sections")

# Visual position helpers
def _card(x, y, w=200, h=120):
    return {"x": x, "y": y, "width": w, "height": h}

def _chart(x, y, w=580, h=340):
    return {"x": x, "y": y, "width": w, "height": h}


def _make_visual_config(visual_type, title=None, **extra):
    """Build the config JSON for a visual container."""
    is_chart = visual_type in (
        "clusteredBarChart", "clusteredColumnChart", "lineChart",
        "donutChart", "pieChart", "areaChart", "stackedBarChart",
        "stackedColumnChart", "waterfallChart", "lineClusteredColumnComboChart",
    )
    cfg = {
        "name": uuid.uuid4().hex[:16],
        "layouts": [{"id": 0, "position": extra.get("position", {})}],
        "singleVisual": {
            "visualType": visual_type,
            "projections": extra.get("projections", {}),
            "prototypeQuery": extra.get("prototypeQuery"),
            "drillFilterOtherVisuals": True,
        },
    }
    if is_chart:
        cfg["singleVisual"]["hasDefaultSort"] = True
    if title:
        cfg["singleVisual"]["vcObjects"] = {
            "title": [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                    }
                }
            ]
        }
    return cfg


def _measure_ref(measure_name, table="PRData"):
    """Build a measure reference for projections and queries."""
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": measure_name,
        }
    }


def _column_ref(column_name, table="PRData"):
    """Build a column reference."""
    return {
        "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column_name,
        }
    }


def _proto_query(selects, from_table="PRData", from_alias="p"):
    """Build a minimal prototypeQuery."""
    return {
        "Version": 2,
        "From": [{"Name": from_alias, "Entity": from_table, "Type": 0}],
        "Select": selects,
    }


def _select_measure(measure, alias, from_alias="p"):
    sel = {
        "Measure": {
            "Expression": {"SourceRef": {"Source": from_alias}},
            "Property": measure,
        },
        "Name": alias,
    }
    if alias != measure:
        sel["NativeReferenceName"] = measure
    return sel


def _select_column(column, alias, from_alias="p"):
    sel = {
        "Column": {
            "Expression": {"SourceRef": {"Source": from_alias}},
            "Property": column,
        },
        "Name": alias,
    }
    if alias != column:
        sel["NativeReferenceName"] = column
    return sel


# Convenience: PBI Desktop naming convention for chart queryRefs
def _mref(measure, table="PRData"):
    """Return (queryRef, alias) pair using PRData.MeasureName convention."""
    qr = f"{table}.{measure}"
    return qr, qr


def _cref(column, table="PRData"):
    """Return (queryRef, alias) pair using PRData.ColumnName convention."""
    qr = f"{table}.{column}"
    return qr, qr


# ============================================================
# Page 1: Overview
# ============================================================
def make_overview_page():
    page_dir = os.path.join(SECTIONS_DIR, "000_Overview")
    os.makedirs(page_dir, exist_ok=True)

    section = {
        "id": 0,
        "name": "overview_page",
        "displayName": "PR Overview",
        "ordinal": 0,
        "visualContainers": [],
        "displayOption": 1,
        "width": 1280,
        "height": 720,
    }

    visuals = []

    # --- KPI Cards row ---
    card_defs = [
        ("Total PRs", 20, 20),
        ("Merged PRs", 240, 20),
        ("PRs with Copilot Review", 460, 20),
        ("CCR Adoption %", 680, 20),
        ("Avg Days Open", 900, 20),
        ("Merge Rate %", 1060, 20),
    ]
    for measure, x, y in card_defs:
        pos = _card(x, y, w=200, h=100)
        cfg = _make_visual_config(
            "card",
            title=measure,
            position=pos,
            projections={"Values": [{"queryRef": f"m_{measure}"}]},
            prototypeQuery=_proto_query(
                [_select_measure(measure, f"m_{measure}")]
            ),
        )
        visuals.append({
            "config": json.dumps(cfg),
            "filters": "[]",
            "x": pos["x"], "y": pos["y"],
            "width": pos["width"], "height": pos["height"],
            "tabOrder": len(visuals) * 1000,
        })

    # --- PRs by Month (clustered bar chart) ---
    pos = _chart(20, 140, 610, 280)
    bar_cfg = _make_visual_config(
        "clusteredBarChart",
        title="PRs by Month",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.month_year", "active": True}],
            "Y": [{"queryRef": "PRData.Total PRs"}],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("Total PRs", "PRData.Total PRs"),
        ]),
    )
    visuals.append({
        "config": json.dumps(bar_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- CCR Adoption by Month (line chart) ---
    pos = _chart(650, 140, 610, 280)
    line_cfg = _make_visual_config(
        "lineChart",
        title="CCR Adoption % by Month",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.month_year", "active": True}],
            "Y": [{"queryRef": "PRData.CCR Adoption %"}],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("CCR Adoption %", "PRData.CCR Adoption %"),
        ]),
    )
    visuals.append({
        "config": json.dumps(line_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- PRs by Repository (donut chart) ---
    pos = _chart(20, 440, 610, 260)
    donut_cfg = _make_visual_config(
        "donutChart",
        title="PRs by Repository",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.repository", "active": True}],
            "Y": [{"queryRef": "PRData.Total PRs"}],
        },
        prototypeQuery=_proto_query([
            _select_column("repository", "PRData.repository"),
            _select_measure("Total PRs", "PRData.Total PRs"),
        ]),
    )
    visuals.append({
        "config": json.dumps(donut_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- PRs by Author (table) ---
    pos = _chart(650, 440, 610, 260)
    table_cfg = _make_visual_config(
        "tableEx",
        title="Top Authors",
        position=pos,
        projections={
            "Values": [
                {"queryRef": "PRData.author"},
                {"queryRef": "PRData.Total PRs"},
                {"queryRef": "PRData.Merged PRs"},
                {"queryRef": "PRData.CCR Adoption %"},
            ],
        },
        prototypeQuery=_proto_query([
            _select_column("author", "PRData.author"),
            _select_measure("Total PRs", "PRData.Total PRs"),
            _select_measure("Merged PRs", "PRData.Merged PRs"),
            _select_measure("CCR Adoption %", "PRData.CCR Adoption %"),
        ]),
    )
    visuals.append({
        "config": json.dumps(table_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    section["visualContainers"] = visuals
    with open(os.path.join(page_dir, "section.json"), "w") as f:
        json.dump(section, f, indent=2)
    with open(os.path.join(page_dir, "config.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(page_dir, "filters.json"), "w") as f:
        json.dump([], f)


# ============================================================
# Page 2: Copilot Impact
# ============================================================
def make_copilot_impact_page():
    page_dir = os.path.join(SECTIONS_DIR, "001_CopilotImpact")
    os.makedirs(page_dir, exist_ok=True)

    section = {
        "id": 1,
        "name": "copilot_impact_page",
        "displayName": "Copilot Code Review Impact",
        "ordinal": 1,
        "visualContainers": [],
        "displayOption": 1,
        "width": 1280,
        "height": 720,
    }

    visuals = []

    # --- KPI Cards ---
    card_defs = [
        ("Avg Days Open (With CCR)", 20, 20),
        ("Avg Days Open (Without CCR)", 240, 20),
        ("Days Saved per PR", 460, 20),
        ("Avg First Response Hours (With CCR)", 680, 20),
        ("Avg First Response Hours (Without CCR)", 900, 20),
    ]
    for measure, x, y in card_defs:
        pos = _card(x, y, w=220, h=100)
        cfg = _make_visual_config(
            "card",
            title=measure,
            position=pos,
            projections={"Values": [{"queryRef": f"m_{measure}"}]},
            prototypeQuery=_proto_query(
                [_select_measure(measure, f"m_{measure}")]
            ),
        )
        visuals.append({
            "config": json.dumps(cfg),
            "filters": "[]",
            "x": pos["x"], "y": pos["y"],
            "width": pos["width"], "height": pos["height"],
            "tabOrder": len(visuals) * 1000,
        })

    # --- Cycle Time Comparison bar (With vs Without CCR) ---
    pos = _chart(20, 140, 610, 280)
    bar_cfg = _make_visual_config(
        "clusteredColumnChart",
        title="Avg Days Open: With vs Without Copilot Review",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.month_year", "active": True}],
            "Y": [
                {"queryRef": "PRData.Avg Days Open (With CCR)"},
                {"queryRef": "PRData.Avg Days Open (Without CCR)"},
            ],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("Avg Days Open (With CCR)", "PRData.Avg Days Open (With CCR)"),
            _select_measure("Avg Days Open (Without CCR)", "PRData.Avg Days Open (Without CCR)"),
        ]),
    )
    visuals.append({
        "config": json.dumps(bar_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- First Response Time Comparison ---
    pos = _chart(650, 140, 610, 280)
    line_cfg = _make_visual_config(
        "clusteredColumnChart",
        title="Avg First Response Hours: With vs Without CCR",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.month_year", "active": True}],
            "Y": [
                {"queryRef": "PRData.Avg First Response Hours (With CCR)"},
                {"queryRef": "PRData.Avg First Response Hours (Without CCR)"},
            ],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("Avg First Response Hours (With CCR)", "PRData.Avg First Response Hours (With CCR)"),
            _select_measure("Avg First Response Hours (Without CCR)", "PRData.Avg First Response Hours (Without CCR)"),
        ]),
    )
    visuals.append({
        "config": json.dumps(line_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- Days Saved Trend ---
    pos = _chart(20, 440, 610, 260)
    trend_cfg = _make_visual_config(
        "lineChart",
        title="Days Saved per PR (Trend)",
        position=pos,
        projections={
            "Category": [{"queryRef": "PRData.month_year", "active": True}],
            "Y": [{"queryRef": "PRData.Days Saved per PR"}],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("Days Saved per PR", "PRData.Days Saved per PR"),
        ]),
    )
    visuals.append({
        "config": json.dumps(trend_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- Review count comparison table ---
    pos = _chart(650, 440, 610, 260)
    tbl_cfg = _make_visual_config(
        "tableEx",
        title="Monthly Summary Comparison",
        position=pos,
        projections={
            "Values": [
                {"queryRef": "PRData.month_year"},
                {"queryRef": "PRData.Total PRs"},
                {"queryRef": "PRData.PRs with Copilot Review"},
                {"queryRef": "PRData.CCR Adoption %"},
                {"queryRef": "PRData.Days Saved per PR"},
            ],
        },
        prototypeQuery=_proto_query([
            _select_column("month_year", "PRData.month_year"),
            _select_measure("Total PRs", "PRData.Total PRs"),
            _select_measure("PRs with Copilot Review", "PRData.PRs with Copilot Review"),
            _select_measure("CCR Adoption %", "PRData.CCR Adoption %"),
            _select_measure("Days Saved per PR", "PRData.Days Saved per PR"),
        ]),
    )
    visuals.append({
        "config": json.dumps(tbl_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    section["visualContainers"] = visuals
    with open(os.path.join(page_dir, "section.json"), "w") as f:
        json.dump(section, f, indent=2)
    with open(os.path.join(page_dir, "config.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(page_dir, "filters.json"), "w") as f:
        json.dump([], f)


# ============================================================
# Page 3: PR Details
# ============================================================
def make_pr_details_page():
    page_dir = os.path.join(SECTIONS_DIR, "002_PRDetails")
    os.makedirs(page_dir, exist_ok=True)

    section = {
        "id": 2,
        "name": "pr_details_page",
        "displayName": "PR Details",
        "ordinal": 2,
        "visualContainers": [],
        "displayOption": 1,
        "width": 1280,
        "height": 720,
    }

    visuals = []

    # --- Slicer: Repository ---
    pos = {"x": 20, "y": 20, "width": 250, "height": 100}
    slicer_cfg = _make_visual_config(
        "slicer",
        title="Repository",
        position=pos,
        projections={
            "Values": [{"queryRef": "PRData.repository"}],
        },
        prototypeQuery=_proto_query([
            _select_column("repository", "PRData.repository"),
        ]),
    )
    visuals.append({
        "config": json.dumps(slicer_cfg),
        "filters": "[]",
        "x": pos["x"], "y": pos["y"],
        "width": pos["width"], "height": pos["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- Slicer: State ---
    pos2 = {"x": 290, "y": 20, "width": 200, "height": 100}
    slicer2_cfg = _make_visual_config(
        "slicer",
        title="State",
        position=pos2,
        projections={
            "Values": [{"queryRef": "PRData.state"}],
        },
        prototypeQuery=_proto_query([
            _select_column("state", "PRData.state"),
        ]),
    )
    visuals.append({
        "config": json.dumps(slicer2_cfg),
        "filters": "[]",
        "x": pos2["x"], "y": pos2["y"],
        "width": pos2["width"], "height": pos2["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- Slicer: Has Copilot Review ---
    pos3 = {"x": 510, "y": 20, "width": 200, "height": 100}
    slicer3_cfg = _make_visual_config(
        "slicer",
        title="Has Copilot Review",
        position=pos3,
        projections={
            "Values": [{"queryRef": "PRData.has_copilot_review"}],
        },
        prototypeQuery=_proto_query([
            _select_column("has_copilot_review", "PRData.has_copilot_review"),
        ]),
    )
    visuals.append({
        "config": json.dumps(slicer3_cfg),
        "filters": "[]",
        "x": pos3["x"], "y": pos3["y"],
        "width": pos3["width"], "height": pos3["height"],
        "tabOrder": len(visuals) * 1000,
    })

    # --- Detail Table ---
    pos4 = {"x": 20, "y": 140, "width": 1240, "height": 560}
    detail_cfg = _make_visual_config(
        "tableEx",
        title="Pull Request Details",
        position=pos4,
        projections={
            "Values": [
                {"queryRef": "PRData.pr_number"},
                {"queryRef": "PRData.repository"},
                {"queryRef": "PRData.title"},
                {"queryRef": "PRData.author"},
                {"queryRef": "PRData.state"},
                {"queryRef": "PRData.created_at"},
                {"queryRef": "PRData.days_open"},
                {"queryRef": "PRData.has_copilot_review"},
                {"queryRef": "PRData.reviewer_count"},
                {"queryRef": "PRData.additions"},
                {"queryRef": "PRData.deletions"},
                {"queryRef": "PRData.first_response_hours"},
            ],
        },
        prototypeQuery=_proto_query([
            _select_column("pr_number", "PRData.pr_number"),
            _select_column("repository", "PRData.repository"),
            _select_column("title", "PRData.title"),
            _select_column("author", "PRData.author"),
            _select_column("state", "PRData.state"),
            _select_column("created_at", "PRData.created_at"),
            _select_column("days_open", "PRData.days_open"),
            _select_column("has_copilot_review", "PRData.has_copilot_review"),
            _select_column("reviewer_count", "PRData.reviewer_count"),
            _select_column("additions", "PRData.additions"),
            _select_column("deletions", "PRData.deletions"),
            _select_column("first_response_hours", "PRData.first_response_hours"),
        ]),
    )
    visuals.append({
        "config": json.dumps(detail_cfg),
        "filters": "[]",
        "x": pos4["x"], "y": pos4["y"],
        "width": pos4["width"], "height": pos4["height"],
        "tabOrder": len(visuals) * 1000,
    })

    section["visualContainers"] = visuals
    with open(os.path.join(page_dir, "section.json"), "w") as f:
        json.dump(section, f, indent=2)
    with open(os.path.join(page_dir, "config.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(page_dir, "filters.json"), "w") as f:
        json.dump([], f)


# ============================================================
# Light variant: single page dashboard
# ============================================================
LIGHT_SECTIONS_DIR = os.path.join(BASE, "pbixproj-light", "Report", "sections")


def make_light_dashboard_page():
    """Generate a single-page dashboard for the light variant with 5 cards + 4 charts."""
    page_dir = os.path.join(LIGHT_SECTIONS_DIR, "000_Dashboard")
    os.makedirs(page_dir, exist_ok=True)

    section = {
        "id": 0,
        "name": "dashboard_page",
        "displayName": "PR Dashboard",
        "ordinal": 0,
        "visualContainers": [],
        "displayOption": 1,
        "width": 1280,
        "height": 720,
    }

    visuals = []

    def _add(visual_type, title, pos, projections, proto_selects):
        cfg = _make_visual_config(
            visual_type, title=title,
            position=pos, projections=projections,
            prototypeQuery=_proto_query(proto_selects),
        )
        visuals.append({
            "config": json.dumps(cfg),
            "filters": "[]",
            "x": pos["x"], "y": pos["y"],
            "width": pos["width"], "height": pos["height"],
            "tabOrder": len(visuals) * 1000,
        })

    # --- Row 1: five KPI cards ---
    card_w, card_h = 230, 100
    card_y = 20
    card_gap = 15
    card_x_start = 20
    cards = [
        ("Total PRs", "Total PRs"),
        ("Merged PRs", "Merged PRs"),
        ("PRs with Copilot Review", "PRs with Copilot Review"),
        ("CCR Adoption %", "CCR Adoption %"),
        ("Avg Days Open", "Avg Days Open"),
    ]
    for i, (title, measure) in enumerate(cards):
        x = card_x_start + i * (card_w + card_gap)
        _add("card", title,
             {"x": x, "y": card_y, "width": card_w, "height": card_h},
             {"Values": [{"queryRef": f"m_{measure}"}]},
             [_select_measure(measure, f"m_{measure}")])

    # --- Row 2: two comparison charts ---
    chart_w, chart_h = 600, 280
    chart_y = 140

    # Chart 1: Avg Days Open comparison (with vs without CCR) by month
    _add("clusteredColumnChart", "Avg Days Open: With vs Without Copilot Review",
         {"x": 20, "y": chart_y, "width": chart_w, "height": chart_h},
         {
             "Category": [{"queryRef": "PRData.month_year", "active": True}],
             "Y": [
                 {"queryRef": "PRData.Avg Days Open (With CCR)"},
                 {"queryRef": "PRData.Avg Days Open (Without CCR)"},
             ],
         },
         [
             _select_column("month_year", "PRData.month_year"),
             _select_measure("Avg Days Open (With CCR)", "PRData.Avg Days Open (With CCR)"),
             _select_measure("Avg Days Open (Without CCR)", "PRData.Avg Days Open (Without CCR)"),
         ])

    # Chart 2: Avg First Response Hours comparison by month
    _add("clusteredColumnChart", "Avg First Response Hours: With vs Without CCR",
         {"x": 650, "y": chart_y, "width": chart_w, "height": chart_h},
         {
             "Category": [{"queryRef": "PRData.month_year", "active": True}],
             "Y": [
                 {"queryRef": "PRData.Avg First Response Hours (With CCR)"},
                 {"queryRef": "PRData.Avg First Response Hours (Without CCR)"},
             ],
         },
         [
             _select_column("month_year", "PRData.month_year"),
             _select_measure("Avg First Response Hours (With CCR)", "PRData.Avg First Response Hours (With CCR)"),
             _select_measure("Avg First Response Hours (Without CCR)", "PRData.Avg First Response Hours (Without CCR)"),
         ])

    # --- Row 3: trend + adoption charts ---
    chart_y2 = 440

    # Chart 3: Monthly trend - CCR adoption over time
    _add("lineChart", "Monthly CCR Adoption Trend",
         {"x": 20, "y": chart_y2, "width": chart_w, "height": chart_h},
         {
             "Category": [{"queryRef": "PRData.month_year", "active": True}],
             "Y": [{"queryRef": "PRData.CCR Adoption %"}],
         },
         [
             _select_column("month_year", "PRData.month_year"),
             _select_measure("CCR Adoption %", "PRData.CCR Adoption %"),
         ])

    # Chart 4: Monthly PR volume
    _add("clusteredColumnChart", "Monthly PR Volume",
         {"x": 650, "y": chart_y2, "width": chart_w, "height": chart_h},
         {
             "Category": [{"queryRef": "PRData.month_year", "active": True}],
             "Y": [
                 {"queryRef": "PRData.Total PRs"},
                 {"queryRef": "PRData.PRs with Copilot Review"},
             ],
         },
         [
             _select_column("month_year", "PRData.month_year"),
             _select_measure("Total PRs", "PRData.Total PRs"),
             _select_measure("PRs with Copilot Review", "PRData.PRs with Copilot Review"),
         ])

    section["visualContainers"] = visuals
    with open(os.path.join(page_dir, "section.json"), "w") as f:
        json.dump(section, f, indent=2)
    with open(os.path.join(page_dir, "config.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(page_dir, "filters.json"), "w") as f:
        json.dump([], f)


# ============================================================
# Generate config with activeSectionIndex
# ============================================================
def update_report_config():
    for variant in ["pbixproj-full", "pbixproj-light"]:
        cfg_path = os.path.join(BASE, variant, "Report", "config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        cfg["activeSectionIndex"] = 0
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=2)


if __name__ == "__main__":
    # Full variant: 3 pages
    make_overview_page()
    make_copilot_impact_page()
    make_pr_details_page()
    # Light variant: 1 page
    make_light_dashboard_page()
    # Update configs
    update_report_config()
    print("Report pages generated successfully!")
    print("  Full:")
    print("    - 000_Overview (6 cards, 2 charts, 1 donut, 1 table)")
    print("    - 001_CopilotImpact (5 cards, 2 column charts, 1 line, 1 table)")
    print("    - 002_PRDetails (3 slicers, 1 detail table)")
    print("  Light:")
    print("    - 000_Dashboard (5 cards, 4 charts)")
