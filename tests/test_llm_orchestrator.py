from src.llm.orchestrator import LLMOrchestrator, LLMRequest


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class FakeWorker:
    def __init__(self, request):
        self.request = request
        self.response_ready = FakeSignal()
        self.error_occurred = FakeSignal()
        self.partial_response = FakeSignal()
        self.session_created = FakeSignal()
        self.brain_update_ready = FakeSignal()
        self.started = False
        self.aborted = False
        self.quit_called = False

    def isRunning(self):
        return self.started and not self.quit_called

    def start(self):
        self.started = True

    def abort(self):
        self.aborted = True

    def quit(self):
        self.quit_called = True


def test_submit_routes_common_worker_signals():
    workers = []
    responses = []
    errors = []
    orchestrator = LLMOrchestrator(lambda request: workers.append(FakeWorker(request)) or workers[-1])

    request = LLMRequest("hello", metadata={"mode": "user_input"})
    worker = orchestrator.submit(
        request,
        response_ready=responses.append,
        error_occurred=errors.append,
    )

    worker.response_ready.emit([{"dialogue": "hi"}])
    worker.error_occurred.emit("timeout")
    assert responses == [[{"dialogue": "hi"}]]
    assert errors == ["timeout"]
    assert worker.request == request
    assert orchestrator.active


def test_autonomous_request_is_deferred_while_worker_active():
    workers = []
    orchestrator = LLMOrchestrator(lambda request: workers.append(FakeWorker(request)) or workers[-1])

    first = orchestrator.submit(LLMRequest("first", autonomous=True))
    second = orchestrator.submit(LLMRequest("second", autonomous=True))

    assert first is not None
    assert second is None
    assert len(workers) == 1


def test_user_request_preempts_active_worker_without_waiting():
    workers = []
    orchestrator = LLMOrchestrator(lambda request: workers.append(FakeWorker(request)) or workers[-1])

    first = orchestrator.submit(LLMRequest("autonomous", autonomous=True))
    second = orchestrator.submit(LLMRequest("user"), preempt=True)

    assert first.aborted
    assert first.quit_called
    assert second.request.prompt == "user"
    assert orchestrator.worker is second


def test_cancel_is_idempotent_and_non_blocking():
    workers = []
    orchestrator = LLMOrchestrator(lambda request: workers.append(FakeWorker(request)) or workers[-1])

    worker = orchestrator.submit(LLMRequest("cancel me"))
    orchestrator.cancel()
    orchestrator.cancel()

    assert worker.aborted
    assert worker.quit_called
    assert not orchestrator.active
