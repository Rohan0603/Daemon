const vscode = require("vscode");
const WebSocket = require("ws");

let socket;

function activate(context) {
  const token = vscode.workspace.getConfiguration("daemon").get("bridgeToken", "");
  socket = new WebSocket("ws://127.0.0.1:4098");
  socket.on("open", sendContext);
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(sendContext),
    { dispose: () => socket && socket.close() }
  );

  function sendContext() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({
      token,
      type: "EDITOR_CONTEXT",
      context: {
        file: editor.document.uri.fsPath,
        language: editor.document.languageId,
        line: editor.selection.active.line + 1,
        column: editor.selection.active.character + 1
      }
    }));
  }
}

function deactivate() {
  if (socket) socket.close();
}

module.exports = { activate, deactivate };
