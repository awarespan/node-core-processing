from node_runtime.media import device_capabilities as caps


def test_reports_physical_capture_devices(monkeypatch):
    monkeypatch.setattr(caps, '_video_devices', lambda: ['/dev/video0'])
    monkeypatch.setattr(caps, '_capture_devices', lambda: ['card 1: USB [USB], device 0: USB Audio [USB Audio]'])
    result = caps.detect_media_capabilities()
    assert result['camera_available'] is True
    assert result['microphone_available'] is True
    assert result['camera_devices'] == ['/dev/video0']


def test_reports_missing_devices_without_guessing(monkeypatch):
    monkeypatch.setattr(caps, '_video_devices', lambda: [])
    monkeypatch.setattr(caps, '_capture_devices', lambda: [])
    result = caps.detect_media_capabilities()
    assert result['camera_available'] is False
    assert result['microphone_available'] is False
    assert result['camera_devices'] == []
    assert result['microphone_devices'] == []
