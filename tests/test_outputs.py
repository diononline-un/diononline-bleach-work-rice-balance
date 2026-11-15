import json

from rice.outputs import detect_outputs

KScreen = {
    "outputs": [
        {"name": "DP-1", "connected": True, "enabled": True, "primary": True,
         "geometry": {"x": 0, "y": 0, "width": 5120, "height": 1440}},
        {"name": "HDMI-A-1", "connected": False, "enabled": False, "primary": False,
         "geometry": {"x": 0, "y": 0, "width": 1080, "height": 1920}},
    ]
}


def test_detect_outputs_filters_disconnected():
    outputs = detect_outputs(json.dumps(KScreen))
    assert [output.connector for output in outputs] == ["DP-1"]
    assert outputs[0].width == 5120
