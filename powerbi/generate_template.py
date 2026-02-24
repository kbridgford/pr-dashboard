#!/usr/bin/env python3
"""
Power BI Template (.pbit) Generator

Generates Power BI Template (.pbit) files for the Copilot Code Review Impact
Dashboard in two variants:

  - Full:  KPI cards, clustered column charts, and slicers (dashboard-full.pbit)
  - Light: Just the two clustered column charts (dashboard-light.pbit)

Both include a parameterized CSV data source, the full data model with all 26
columns, DAX measures, and a calculated "Review Type" column.

When opened in Power BI Desktop, the user is prompted for the CSV file path
(defaults to data/pull_requests.csv), and the dashboard is ready to use.

Usage:
    python powerbi/generate_template.py            # generates both templates
    python powerbi/generate_template.py --full      # full template only
    python powerbi/generate_template.py --light     # light template only
"""

import json
import zipfile
import hashlib
import os
import argparse


# ============================================================================
# Column Definitions
# ============================================================================
# Each tuple: (csv_column_name, tom_data_type, m_type_expression)

COLUMNS = [
    ("pr_number",            "int64",    "Int64.Type"),
    ("repository",           "string",   "type text"),
    ("title",                "string",   "type text"),
    ("author",               "string",   "type text"),
    ("created_at",           "dateTime", "type datetimezone"),
    ("merged_at",            "dateTime", "type datetimezone"),
    ("closed_at",            "dateTime", "type datetimezone"),
    ("state",                "string",   "type text"),
    ("is_draft",             "boolean",  "type logical"),
    ("days_open",            "double",   "type number"),
    ("has_copilot_review",   "boolean",  "type logical"),
    ("month_year",           "string",   "type text"),
    ("reviewer_count",       "int64",    "Int64.Type"),
    ("copilot_review_count", "int64",    "Int64.Type"),
    ("reviewers",            "string",   "type text"),
    ("merged_by",            "string",   "type text"),
    ("additions",            "int64",    "Int64.Type"),
    ("deletions",            "int64",    "Int64.Type"),
    ("changed_files",        "int64",    "Int64.Type"),
    ("commit_count",         "int64",    "Int64.Type"),
    ("comment_count",        "int64",    "Int64.Type"),
    ("review_decision",      "string",   "type text"),
    ("labels",               "string",   "type text"),
    ("base_branch",          "string",   "type text"),
    ("head_branch",          "string",   "type text"),
    ("first_response_hours", "double",   "type number"),
]


# ============================================================================
# DAX Measures
# ============================================================================
# Each tuple: (measure_name, dax_expression, format_string)

MEASURES = [
    ("Total PRs",
     "COUNTROWS('pull_requests')",
     "0"),
    ("PRs With CCR",
     "CALCULATE(COUNTROWS('pull_requests'), 'pull_requests'[has_copilot_review] = TRUE)",
     "0"),
    ("PRs Without CCR",
     "CALCULATE(COUNTROWS('pull_requests'), 'pull_requests'[has_copilot_review] = FALSE)",
     "0"),
    ("CCR Adoption %",
     "DIVIDE([PRs With CCR], [Total PRs], 0) * 100",
     "0.0"),
    ("Avg Days With CCR",
     "CALCULATE(AVERAGE('pull_requests'[days_open]), 'pull_requests'[has_copilot_review] = TRUE)",
     "0.0"),
    ("Avg Days Without CCR",
     "CALCULATE(AVERAGE('pull_requests'[days_open]), 'pull_requests'[has_copilot_review] = FALSE)",
     "0.0"),
    ("Days Saved",
     "[Avg Days Without CCR] - [Avg Days With CCR]",
     "0.0"),
    ("Total Repos",
     "DISTINCTCOUNT('pull_requests'[repository])",
     "0"),
]


# ============================================================================
# Layout Constants
# ============================================================================

PAGE_WIDTH = 1280
PAGE_HEIGHT = 720

# Colors
COLOR_WITH_CCR = "#4F81BD"     # Blue
COLOR_WITHOUT_CCR = "#C0504D"  # Red


# ============================================================================
# Helpers
# ============================================================================

def _guid(seed: str) -> str:
    """Generate a deterministic GUID from a seed string."""
    h = hashlib.md5(seed.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _visual_id(name: str) -> str:
    """Generate a deterministic 20-char visual ID."""
    return hashlib.md5(name.encode()).hexdigest()[:20]


def _utf16le_bom(text: str) -> bytes:
    """Encode text as UTF-16 LE with BOM (required by .pbit format)."""
    return b"\xff\xfe" + text.encode("utf-16-le")


def _pbi_literal(value: str) -> dict:
    """Wrap a value in the Power BI literal expression format."""
    return {"expr": {"Literal": {"Value": value}}}


# ============================================================================
# .pbit Component: [Content_Types].xml
# ============================================================================

def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="json" ContentType="application/json" />'
        '<Default Extension="xml" ContentType="application/xml" />'
        "</Types>"
    )


# ============================================================================
# .pbit Component: DataModelSchema (TOM format)
# ============================================================================

def _data_model_schema() -> dict:
    """Build the Tabular Object Model (TOM) data model."""

    # ---- Regular columns from CSV ----
    columns = []
    for col_name, tom_type, _ in COLUMNS:
        col = {
            "name": col_name,
            "dataType": tom_type,
            "sourceColumn": col_name,
            "lineageTag": _guid(f"col_{col_name}"),
            "annotations": [
                {"name": "SummarizationSetBy", "value": "Automatic"},
            ],
        }
        columns.append(col)

    # ---- Calculated column: Review Type ----
    columns.append({
        "type": "calculated",
        "name": "Review Type",
        "dataType": "string",
        "isDataTypeInferred": True,
        "lineageTag": _guid("calc_review_type"),
        "expression": (
            'IF(\'pull_requests\'[has_copilot_review] = TRUE(), '
            '"With Copilot Code Review", '
            '"Without Copilot Code Review")'
        ),
        "annotations": [
            {"name": "SummarizationSetBy", "value": "Automatic"},
        ],
    })

    # ---- DAX measures ----
    measures = []
    for measure_name, expression, fmt in MEASURES:
        measures.append({
            "name": measure_name,
            "expression": expression,
            "formatString": fmt,
            "lineageTag": _guid(f"measure_{measure_name}"),
        })

    # ---- M expression for partition source ----
    type_pairs = ", ".join(
        '{"' + name + '", ' + m_type + "}" for name, _, m_type in COLUMNS
    )
    m_expression = [
        "let",
        "    Source = Csv.Document("
        'File.Contents(CsvFilePath),'
        '[Delimiter=",", Columns='
        + str(len(COLUMNS))
        + ", Encoding=65001, QuoteStyle=QuoteStyle.None]),",
        '    #"Promoted Headers" = Table.PromoteHeaders('
        "Source, [PromoteAllScalars=true]),",
        '    #"Changed Type" = Table.TransformColumnTypes('
        '#"Promoted Headers",{' + type_pairs + "})",
        "in",
        '    #"Changed Type"',
    ]

    # ---- Full TOM schema ----
    return {
        "name": "Model",
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": [
                {
                    "name": "pull_requests",
                    "lineageTag": _guid("pull_requests_table"),
                    "columns": columns,
                    "measures": measures,
                    "partitions": [
                        {
                            "name": "pull_requests",
                            "mode": "import",
                            "source": {
                                "type": "m",
                                "expression": m_expression,
                            },
                        }
                    ],
                    "annotations": [
                        {"name": "PBI_NavigationStepName", "value": "Navigation"},
                        {"name": "PBI_ResultType", "value": "Table"},
                    ],
                }
            ],
            "expressions": [
                {
                    "name": "CsvFilePath",
                    "kind": "m",
                    "expression": [
                        '"data/pull_requests.csv" meta '
                        "[IsParameterQuery=true, "
                        'Type="Text", '
                        "IsParameterQueryRequired=true]"
                    ],
                    "lineageTag": _guid("param_csv_path"),
                    "annotations": [
                        {"name": "PBI_NavigationStepName", "value": "Navigation"},
                        {"name": "PBI_ResultType", "value": "Text"},
                    ],
                }
            ],
            "annotations": [
                {
                    "name": "PBI_QueryOrder",
                    "value": '["pull_requests"]',
                },
                {"name": "PBIDesktopVersion", "value": "2.137.0.0"},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


# ============================================================================
# .pbit Component: Report/Layout — visual builders
# ============================================================================

def _card_visual(name, title, measure_name, x, y, w, h, z=0):
    """Build a visual container dict for a KPI card."""
    vid = _visual_id(name)
    config = {
        "name": vid,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x, "y": y, "width": w, "height": h, "tabOrder": z,
                },
            }
        ],
        "singleVisual": {
            "visualType": "card",
            "projections": {
                "Values": [{"queryRef": f"pull_requests.{measure_name}"}],
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "p", "Entity": "pull_requests", "Type": 0}],
                "Select": [
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "p"}},
                            "Property": measure_name,
                        },
                        "Name": f"pull_requests.{measure_name}",
                    }
                ],
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True,
            "vcObjects": {
                "title": [
                    {
                        "properties": {
                            "show": _pbi_literal("true"),
                            "text": _pbi_literal(f"'{title}'"),
                        }
                    }
                ],
            },
        },
    }
    return {
        "x": float(x), "y": float(y), "z": z,
        "width": float(w), "height": float(h),
        "config": json.dumps(config),
        "filters": "[]",
        "tabOrder": z,
    }


def _column_chart_visual(
    name, title, category_col, value_col, agg_fn, series_col, x, y, w, h, z=0
):
    """Build a visual container dict for a clustered column chart.

    agg_fn values: 0=Sum, 1=Avg, 5=CountNonNull
    """
    vid = _visual_id(name)
    agg_prefix = {0: "Sum", 1: "Avg", 5: "CountNonNull"}.get(agg_fn, "Agg")
    value_ref = f"{agg_prefix}(pull_requests.{value_col})"

    config = {
        "name": vid,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x, "y": y, "width": w, "height": h, "tabOrder": z,
                },
            }
        ],
        "singleVisual": {
            "visualType": "clusteredColumnChart",
            "projections": {
                "Category": [{"queryRef": f"pull_requests.{category_col}"}],
                "Y": [{"queryRef": value_ref}],
                "Series": [{"queryRef": f"pull_requests.{series_col}"}],
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "p", "Entity": "pull_requests", "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "p"}},
                            "Property": category_col,
                        },
                        "Name": f"pull_requests.{category_col}",
                    },
                    {
                        "Aggregation": {
                            "Expression": {
                                "Column": {
                                    "Expression": {
                                        "SourceRef": {"Source": "p"}
                                    },
                                    "Property": value_col,
                                }
                            },
                            "Function": agg_fn,
                        },
                        "Name": value_ref,
                    },
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "p"}},
                            "Property": series_col,
                        },
                        "Name": f"pull_requests.{series_col}",
                    },
                ],
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True,
            "objects": {
                "legend": [
                    {
                        "properties": {
                            "show": _pbi_literal("true"),
                            "position": _pbi_literal("'TopRight'"),
                        }
                    }
                ],
                "labels": [
                    {"properties": {"show": _pbi_literal("true")}}
                ],
            },
            "vcObjects": {
                "title": [
                    {
                        "properties": {
                            "show": _pbi_literal("true"),
                            "text": _pbi_literal(f"'{title}'"),
                        }
                    }
                ],
            },
        },
    }
    return {
        "x": float(x), "y": float(y), "z": z,
        "width": float(w), "height": float(h),
        "config": json.dumps(config),
        "filters": "[]",
        "tabOrder": z,
    }


def _slicer_visual(name, title, column, x, y, w, h, z=0):
    """Build a visual container dict for a dropdown slicer."""
    vid = _visual_id(name)
    config = {
        "name": vid,
        "layouts": [
            {
                "id": 0,
                "position": {
                    "x": x, "y": y, "width": w, "height": h, "tabOrder": z,
                },
            }
        ],
        "singleVisual": {
            "visualType": "slicer",
            "projections": {
                "Values": [{"queryRef": f"pull_requests.{column}"}],
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "p", "Entity": "pull_requests", "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "p"}},
                            "Property": column,
                        },
                        "Name": f"pull_requests.{column}",
                    }
                ],
            },
            "drillFilterOtherVisuals": True,
            "hasDefaultSort": True,
            "objects": {
                "selection": [
                    {
                        "properties": {
                            "selectAllCheckboxEnabled": _pbi_literal("true"),
                            "singleSelect": _pbi_literal("false"),
                        }
                    }
                ],
            },
            "vcObjects": {
                "title": [
                    {
                        "properties": {
                            "show": _pbi_literal("true"),
                            "text": _pbi_literal(f"'{title}'"),
                        }
                    }
                ],
            },
        },
    }
    return {
        "x": float(x), "y": float(y), "z": z,
        "width": float(w), "height": float(h),
        "config": json.dumps(config),
        "filters": "[]",
        "tabOrder": z,
    }


# ============================================================================
# .pbit Component: Report/Layout — visual sets
# ============================================================================

def _full_visuals() -> list:
    """All visuals: KPI cards + column charts + slicers."""
    return [
        # ---- KPI cards (top row, y=15, h=100) ----
        _card_visual(
            "card_total_prs", "Total PRs", "Total PRs",
            x=20, y=15, w=295, h=100, z=0,
        ),
        _card_visual(
            "card_adoption", "Copilot Adoption %", "CCR Adoption %",
            x=335, y=15, w=295, h=100, z=1,
        ),
        _card_visual(
            "card_days_saved", "Avg Days Saved", "Days Saved",
            x=650, y=15, w=295, h=100, z=2,
        ),
        _card_visual(
            "card_repos", "Repositories", "Total Repos",
            x=965, y=15, w=295, h=100, z=3,
        ),
        # ---- Clustered column charts (middle row, y=130, h=350) ----
        _column_chart_visual(
            "chart_days_open",
            "Days PRs Stay Open (With/Without Copilot Code Review)",
            "month_year", "days_open", 1, "Review Type",  # 1 = Average
            x=20, y=130, w=610, h=350, z=4,
        ),
        _column_chart_visual(
            "chart_pr_count",
            "Number of PRs (With/Without Copilot Code Review)",
            "month_year", "pr_number", 5, "Review Type",  # 5 = CountNonNull
            x=650, y=130, w=610, h=350, z=5,
        ),
        # ---- Slicers (bottom row, y=500, h=80) ----
        _slicer_visual(
            "slicer_date", "Date Range", "month_year",
            x=20, y=500, w=610, h=80, z=6,
        ),
        _slicer_visual(
            "slicer_repo", "Repository", "repository",
            x=650, y=500, w=610, h=80, z=7,
        ),
    ]


def _light_visuals() -> list:
    """Light visuals: just the two clustered column charts, centered."""
    return [
        _column_chart_visual(
            "chart_days_open_light",
            "Days PRs Stay Open (With/Without Copilot Code Review)",
            "month_year", "days_open", 1, "Review Type",  # 1 = Average
            x=20, y=30, w=610, h=450, z=0,
        ),
        _column_chart_visual(
            "chart_pr_count_light",
            "Number of PRs (With/Without Copilot Code Review)",
            "month_year", "pr_number", 5, "Review Type",  # 5 = CountNonNull
            x=650, y=30, w=610, h=450, z=1,
        ),
    ]


def _report_layout(variant: str = "full") -> dict:
    """Assemble the report layout.

    Args:
        variant: "full" (cards + charts + slicers) or "light" (charts only).
    """
    if variant == "light":
        visuals = _light_visuals()
        page_name = "Copilot Code Review Impact (Light)"
    else:
        visuals = _full_visuals()
        page_name = "Copilot Code Review Impact"

    report_config = {
        "version": "5.50",
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU06",
                "version": "5.50",
                "type": 2,
            }
        },
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "linguisticSchemaSyncVersion": 2,
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": 1,
        },
    }

    page_config = {"visibility": 0, "displayOption": 1}

    return {
        "id": 0,
        "reportId": _guid("pr_dashboard_report"),
        "config": json.dumps(report_config),
        "layoutOptimization": 0,
        "resourcePackages": [],
        "sections": [
            {
                "id": 0,
                "name": "ReportSection",
                "displayName": page_name,
                "filters": "[]",
                "ordinal": 0,
                "config": json.dumps(page_config),
                "displayOption": 1,
                "width": PAGE_WIDTH,
                "height": PAGE_HEIGHT,
                "visualContainers": visuals,
            }
        ],
        "publicCustomVisuals": [],
    }


# ============================================================================
# .pbit Assembly
# ============================================================================

def generate_pbit(output_path: str, variant: str = "full") -> None:
    """Create a .pbit file (ZIP archive with UTF-16 LE encoded JSON).

    Args:
        output_path: Destination file path.
        variant: "full" or "light" — controls which visuals are included.
    """

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml — UTF-8 XML
        zf.writestr("[Content_Types].xml", _content_types_xml())

        # Version — plain text
        zf.writestr("Version", "1.0")

        # DataModelSchema — UTF-16 LE with BOM
        schema = json.dumps(_data_model_schema(), ensure_ascii=False)
        zf.writestr("DataModelSchema", _utf16le_bom(schema))

        # Report/Layout — UTF-16 LE with BOM
        layout = json.dumps(_report_layout(variant), ensure_ascii=False)
        zf.writestr("Report/Layout", _utf16le_bom(layout))

        # Settings — UTF-16 LE with BOM
        zf.writestr("Settings", _utf16le_bom(json.dumps({})))

        # Metadata — UTF-16 LE with BOM
        metadata = json.dumps({"version": "1.0", "type": 2})
        zf.writestr("Metadata", _utf16le_bom(metadata))

        # DiagramLayout — UTF-16 LE with BOM
        diagram = json.dumps({
            "version": "1.0",
            "pages": [],
            "scrollPosition": {"x": 0, "y": 0},
        })
        zf.writestr("DiagramLayout", _utf16le_bom(diagram))

        # Connections — UTF-16 LE with BOM
        conns = json.dumps({"Version": 1, "Connections": []})
        zf.writestr("Connections", _utf16le_bom(conns))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Generated: {output_path} ({size_kb:.1f} KB)")


# ============================================================================
# CLI
# ============================================================================

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(
        description="Generate Power BI Template (.pbit) files for the PR Dashboard"
    )
    parser.add_argument(
        "--output-dir", "-d",
        default=script_dir,
        help="Output directory for .pbit files (default: powerbi/)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--full", action="store_true",
        help="Generate only the full template (cards + charts + slicers)",
    )
    group.add_argument(
        "--light", action="store_true",
        help="Generate only the light template (charts only)",
    )
    args = parser.parse_args()

    # Determine which variants to generate (default: both)
    variants = []
    if args.full:
        variants = ["full"]
    elif args.light:
        variants = ["light"]
    else:
        variants = ["full", "light"]

    for variant in variants:
        output_path = os.path.join(args.output_dir, f"dashboard-{variant}.pbit")
        generate_pbit(output_path, variant)

    print("Open a .pbit file in Power BI Desktop to use the template.")
    print("You will be prompted to enter the path to your CSV data file.")


if __name__ == "__main__":
    main()
