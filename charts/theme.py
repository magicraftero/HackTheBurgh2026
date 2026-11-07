"""Shared, neutral Altair 5 theme. All presentation styling lives here."""

import altair as alt

PALETTE = {
    "rw": "#737373", "ar": "#8a6bb8", "c0": "#2673ac", "c1": "#d05a3c",
    "b0": "#737373", "b1": "#2673ac", "drivers": "#d05a3c",
    "stock": "#2673ac", "market": "#747474", "pipeline": "#8a6bb8",
    "feed": "#a78329", "temperature": "#d05a3c", "losses": "#b54b73", "lice": "#23877d",
    "count": "#2673ac", "avg_kg": "#d05a3c", "actual": "#252b31",
}
PANEL_WIDTH = 680


def _theme():
    return {"width": "container", "height": 300,
            "config": {"font": "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
                       "background": "white", "view": {"stroke": None},
                       "axis": {"labelFontSize": 13, "titleFontSize": 14, "gridColor": "#e6e8eb",
                                "titlePadding": 12, "labelColor": "#39424b", "titleColor": "#252b31"},
                       "legend": {"labelFontSize": 13, "titleFontSize": 14, "orient": "bottom"},
                       "title": {"fontSize": 19, "subtitleFontSize": 12, "anchor": "start",
                                 "offset": 14, "subtitlePadding": 6},
                       "line": {"strokeWidth": 2}, "area": {"opacity": .16},
                       "point": {"size": 45}, "text": {"fontSize": 15},
                       "range": {"category": list(dict.fromkeys(PALETTE.values()))}}}


def register():
    """Register and enable `lice`, using either Altair 5 theme API."""
    if hasattr(alt, "theme"):
        alt.theme.register("lice", enable=True)(_theme)
    else:
        alt.themes.register("lice", _theme)
        alt.themes.enable("lice")


def model_scale(models):
    return alt.Scale(domain=models, range=[PALETTE[name] for name in models])
