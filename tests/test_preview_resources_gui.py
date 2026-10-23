from test_preview_async_gui import window


def test_input_capture_failure_cancels_previous_job_and_clears_pending(window,monkeypatch):
    w=window;w._queue_preview_update();old=w._preview_controller.worker
    original=w.get_parameters
    def fail():raise ValueError('input capture failed')
    monkeypatch.setattr(w,'get_parameters',fail);w._queue_preview_update()
    assert old.cancelled and not w._preview_pending
    assert not w.flow_area_widget.isEnabled() and 'input capture failed' in w.messages.toPlainText()
    old.finish();assert not w._preview_pending and not w._preview_controller.busy
    monkeypatch.setattr(w,'get_parameters',original);w._queue_preview_update()
    assert w._preview_pending;w._preview_controller.worker.finish()
    assert not w._preview_pending and w.flow_area_widget.isEnabled()


def test_execution_error_is_distinguished_from_invalid_geometry(window):
    w=window;w._queue_preview_update();worker=w._preview_controller.worker
    worker.done=True;worker.completed.emit({'overall':'FAIL','error':{'message':'process could not start'}})
    assert 'execution/result failed' in w.messages.toPlainText()
    assert 'process could not start' in w.messages.toPlainText()
    assert 'correct input values' not in w.statusBar().currentMessage()
    assert not w.flow_area_widget.isEnabled() and 'actual' not in w.geometry_sources


def test_owned_job_retention_waits_for_completion_and_honors_diagnostic_mode(window):
    w=window;retention=w._preview_controller.retention;retention.limit=0
    w._queue_preview_update();worker=w._preview_controller.worker;path=worker.job
    assert path.exists();retention.trim(dispose=True);assert path.exists()
    worker.finish();assert not path.exists()
    retention.keep_jobs=True;w._queue_preview_update();worker=w._preview_controller.worker;path=worker.job
    worker.finish();retention.trim(dispose=True);assert (path/'payload.json').is_file()
