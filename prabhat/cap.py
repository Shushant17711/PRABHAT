"""Render an alert as a Common Alerting Protocol 1.2 message.

CAP is the format the National Disaster Management Authority's alerting system
(SACHET) and most warning dissemination systems ingest.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"

_EVENT = {
    "cyclone": "Cyclone",
    "extreme_rain": "Extreme rainfall",
    "heatwave": "Heat wave",
    "coldwave": "Cold wave",
}
_SEVERITY = {"low": "Minor", "moderate": "Moderate", "severe": "Severe"}


def to_cap(alert: dict, sender: str = "prabhat@localhost") -> str:
    ET.register_namespace("", CAP_NS)

    def sub(parent, tag, text=None):
        el = ET.SubElement(parent, f"{{{CAP_NS}}}{tag}")
        if text is not None:
            el.text = str(text)
        return el

    root = ET.Element(f"{{{CAP_NS}}}alert")
    sub(root, "identifier", alert["alert_id"])
    sub(root, "sender", sender)
    sub(root, "sent", alert["issued_at"].replace("Z", "+00:00"))
    # "Exercise": the input is a synthetic ensemble, so these are not real warnings.
    sub(root, "status", "Exercise")
    sub(root, "msgType", "Alert")
    sub(root, "scope", "Public")

    info = sub(root, "info")
    sub(info, "language", "en-IN")
    sub(info, "category", "Met")
    sub(info, "event", _EVENT.get(alert["hazard"], alert["hazard"]))
    sub(info, "urgency", "Expected" if alert["lead_hour"] <= 72 else "Future")
    sub(info, "severity", _SEVERITY[alert["severity"]])
    sub(info, "certainty", "Likely" if alert["probability"] > 0.5 else "Possible")
    sub(info, "audience", alert["user_class"])
    sub(info, "onset", alert["valid_at"].replace("Z", "+00:00"))
    sub(info, "headline",
        f"{_EVENT.get(alert['hazard'], alert['hazard'])}: "
        f"{alert['probability']:.0%} chance ({alert['impact_field']})")
    sub(info, "instruction", alert["action"])
    for name, value in (("probability", alert["probability"]),
                        ("confidence_mode", alert["confidence_mode"]),
                        ("impact_field", alert["impact_field"])):
        p = sub(info, "parameter")
        sub(p, "valueName", name)
        sub(p, "value", value)
    area = sub(info, "area")
    sub(area, "areaDesc", f"{alert['radius_km']:g} km around the anomaly core")
    lat, lon = alert["centre"]
    sub(area, "circle", f"{lat},{lon} {alert['radius_km']:g}")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
