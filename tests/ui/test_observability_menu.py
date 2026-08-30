from PyQt6.QtWidgets import QMenu

from src.ui.context_menu import PetContextMenu


def test_context_menu_exposes_observability_links(qapp):
    menu = PetContextMenu()
    observability = next(
        action.menu() for action in menu.actions()
        if action.menu() is not None and action.text().startswith("📊 Observability")
    )

    emitted = []
    menu.signals.observability_requested.connect(emitted.append)
    actions = {action.text(): action for action in observability.actions() if not action.isSeparator()}

    actions["Open Grafana Dashboard"].trigger()
    actions["Open Prometheus"].trigger()
    actions["Open Daemon Metrics"].trigger()
    actions["Open Prometheus Alerts"].trigger()

    assert emitted == [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:9090",
        "http://127.0.0.1:4097/metrics",
        "http://127.0.0.1:9090/alerts",
    ]
    menu.deleteLater()
